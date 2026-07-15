import os
import sys
import json
import re
import requests

from dotenv import load_dotenv

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from src.faculty_loader import load_faculty_profiles

load_dotenv()

FALLBACK_PATH = os.path.join(_proj_root, "data", "fallback_papers.json")

TAVILY_URL = "https://api.tavily.com/search"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


def _load_fallback_papers() -> dict:
    with open(FALLBACK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _pick_fallback_area(query: str) -> dict:
    fallback = _load_fallback_papers()
    ql = query.lower()

    area_map = [
        ("nlp", "NLP"),
        ("language model", "NLP"),
        ("llm", "NLP"),
        ("transformer", "NLP"),
        ("computer vision", "Computer Vision"),
        ("image", "Computer Vision"),
        ("video", "Computer Vision"),
        ("cyber", "Cybersecurity"),
        ("security", "Cybersecurity"),
        ("iot", "IoT"),
        ("embedded", "IoT"),
        ("sensor", "IoT"),
        ("edge", "IoT"),
        ("cloud", "Cloud Computing"),
        ("kubernetes", "Cloud Computing"),
        ("microservice", "Cloud Computing"),
        ("serverless", "Cloud Computing"),
        ("reinforcement", "Reinforcement Learning"),
        ("rl", "Reinforcement Learning"),
        ("5g", "5G"),
        ("mimo", "5G"),
        ("wireless", "5G"),
        ("signal processing", "5G"),
        ("ai ", "AI_general"),
        ("artificial intelligence", "AI_general"),
        ("machine learning", "AI_general"),
    ]

    for keyword, area in area_map:
        if keyword in ql:
            return fallback.get(area, fallback["AI_general"])

    return fallback["AI_general"]


def _tavily_search(query: str) -> dict:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        resp = requests.post(
            TAVILY_URL,
            json={
                "query": f"latest research trends in {query} 2024 2025",
                "search_depth": "advanced",
                "max_results": 8,
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def _semantic_scholar_search(query: str, limit: int = 10) -> list[dict]:
    try:
        params = {
            "query": query,
            "limit": limit,
            "fields": "title,year,citationCount,authors,abstract",
        }
        resp = requests.get(SEMANTIC_SCHOLAR_URL, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            papers = []
            for p in data:
                authors = p.get("authors", [])
                author_names = [a.get("name", "") for a in authors[:3]]
                papers.append({
                    "title": p.get("title", "Unknown"),
                    "year": p.get("year", 0),
                    "citations": p.get("citationCount", 0),
                    "authors": author_names,
                    "abstract": (p.get("abstract") or "")[:200],
                })
            return papers
    except Exception:
        pass
    return []


def _synthesize_themes(papers: list[dict], query: str) -> str:
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(api_key=openai_key, model="gpt-4.1-mini")
            paper_text = "\n".join(
                f"- {p['title']} ({p['year']}, {p['citations']} citations)"
                for p in papers[:10]
            )
            prompt = (
                f"Given this research area: \"{query}\"\n\n"
                f"Recent papers:\n{paper_text}\n\n"
                f"Write a 3-4 sentence synthesis of the main research themes "
                f"visible in these papers. Group papers into 2-3 thematic clusters. "
                f"Return ONLY the synthesis paragraph, no preamble."
            )
            return llm.invoke(prompt).content.strip()
        except Exception:
            pass

    themes = {}
    for p in papers:
        t = p.get("theme", "general")
        themes.setdefault(t, []).append(p)

    lines = ["Recent research clusters around the following themes:"]
    for theme, theme_papers in themes.items():
        top = sorted(theme_papers, key=lambda x: x["citations"], reverse=True)[:2]
        top_titles = [f"{p['title']} ({p['year']})" for p in top]
        lines.append(f"- {theme}: {', '.join(top_titles)}")
    return "\n".join(lines)


def search_papers(query: str, use_tavily: bool = False) -> dict:
    s2_papers = _semantic_scholar_search(query)
    used_real_api = "Semantic Scholar"

    if use_tavily:
        tavily_data = _tavily_search(query)
        if tavily_data:
            used_real_api = "Tavily + Semantic Scholar"
    else:
        tavily_data = None

    if not s2_papers:
        fallback_area = _pick_fallback_area(query)
        papers = fallback_area.get("papers", [])
        synthesis = fallback_area.get("trend_synthesis", "")
        source = "[USING FALLBACK] Semantic Scholar unavailable"
    else:
        papers = s2_papers
        synthesis = _synthesize_themes(papers, query)
        source = f"[USING {used_real_api}]"

    return {
        "query": query,
        "papers": papers,
        "synthesis": synthesis,
        "source": source,
        "paper_count": len(papers),
        "used_fallback": not bool(s2_papers),
    }


def format_paper_results(result: dict, iteration_count: int = 0, mode: str = "PROFESSOR") -> str:
    lines = []
    lines.append("=" * 72)
    lines.append(f"[NODE: PAPER_SEARCHER] [MODE: {mode}] [ITER: {iteration_count}]")
    lines.append("-" * 72)
    lines.append(f"Query: \"{result['query']}\"")
    lines.append(f"Source: {result['source']}")
    lines.append(f"Papers found: {result['paper_count']}")
    lines.append("-" * 72)
    lines.append("TREND SYNTHESIS:")
    for syn_line in result["synthesis"].split("\n"):
        lines.append(f"  {syn_line.strip()}")
    lines.append("-" * 72)
    lines.append("SUPPORTING PAPERS:")
    sorted_papers = sorted(result["papers"], key=lambda x: x.get("citations", 0), reverse=True)
    for i, p in enumerate(sorted_papers[:10], 1):
        year = p.get("year", "?")
        cites = p.get("citations", 0)
        title = p.get("title", "Unknown")
        theme = p.get("theme", "")
        theme_str = f" [{theme}]" if theme else ""
        lines.append(f"  {i}. {title} ({year}, {cites} citations){theme_str}")
        authors = p.get("authors", [])
        if authors:
            lines.append(f"     Authors: {', '.join(authors[:3])}")
    lines.append("=" * 72)
    return "\n".join(lines)


def paper_search(state: dict) -> dict:
    query = state.get("refined_query") or state.get("user_query", "")
    mode = state.get("user_mode", "PROFESSOR")
    iteration = state.get("iteration_count", 0)

    result = search_papers(query)

    return {
        "trending_topics": [result["synthesis"]],
        "retrieved_papers": result["papers"],
        "session_stage": "AFTER_PAPER_SEARCH",
        "last_node": "PAPER_SEARCHER",
        "_paper_result": result,
    }


if __name__ == "__main__":
    test_queries = [
        "NLP large language models",
        "computer vision medical imaging",
        "cybersecurity federated learning",
        "reinforcement learning multi-agent",
    ]
    for q in test_queries:
        result = search_papers(q)
        print(format_paper_results(result))
        print()
