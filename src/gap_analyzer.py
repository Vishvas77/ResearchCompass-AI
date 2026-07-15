import os
import sys
import json

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from dotenv import load_dotenv

from src.faculty_loader import load_faculty_profiles
from src.paper_searcher import search_papers, _load_fallback_papers, _pick_fallback_area

load_dotenv()


def _llm_extract_subtopics(papers: list[dict], query: str) -> list[dict]:
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(api_key=openai_key, model="gpt-4.1-mini")
            paper_list = "\n".join(
                f"- {p.get('title','')} ({p.get('year','')})"
                for p in papers[:15]
            )
            prompt = (
                f"Given the research area \"{query}\" and these papers:\n{paper_list}\n\n"
                f"Extract 5-8 recurring sub-topics/themes. For each sub-topic, state:\n"
                f"1. The sub-topic name\n"
                f"2. How many of these papers relate to it\n"
                f"Return as JSON array: [{{\"subtopic\": \"...\", \"paper_count\": N}}, ...]"
            )
            resp = llm.invoke(prompt).content
            import re
            match = re.search(r"\[.*\]", resp, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass

    subtopic_map = {}
    for p in papers:
        theme = p.get("theme", "general")
        subtopic_map[theme] = subtopic_map.get(theme, 0) + 1
    return [
        {"subtopic": k, "paper_count": v}
        for k, v in sorted(subtopic_map.items(), key=lambda x: x[1], reverse=True)
    ]


def analyze_gap(
    query: str,
    paper_result: dict | None = None,
) -> dict:
    if paper_result is None:
        paper_result = search_papers(query)

    papers = paper_result.get("papers", [])
    subtopics = _llm_extract_subtopics(papers, query)

    profiles = load_faculty_profiles()

    gaps = []
    covered = []

    for st in subtopics:
        subtopic_name = st["subtopic"].lower()
        paper_count = st["paper_count"]
        matching_faculty = []
        for p in profiles:
            fk_text = " ".join(p.get("keywords", [])).lower()
            areas_text = " ".join(p.get("research_areas", [])).lower()
            combined = fk_text + " " + areas_text
            subtopic_words = set(subtopic_name.replace("-", " ").replace("_", " ").split())
            match_count = sum(1 for w in subtopic_words if w in combined)
            if match_count >= max(1, len(subtopic_words) // 2 + 1):
                matching_faculty.append(p["name"])

        total_faculty = len(profiles)
        covered_count = len(matching_faculty)

        gap_entry = {
            "subtopic": st["subtopic"],
            "paper_count": paper_count,
            "total_papers": len(papers),
            "faculty_covering": matching_faculty,
            "faculty_count": covered_count,
            "total_faculty": total_faculty,
            "is_gap": covered_count == 0,
        }
        if covered_count == 0:
            gaps.append(gap_entry)
        else:
            covered.append(gap_entry)

    return {
        "query": query,
        "gaps": gaps,
        "covered": covered,
        "total_subtopics": len(subtopics),
        "gap_count": len(gaps),
        "source": paper_result.get("source", ""),
    }


def format_gap_result(result: dict, iteration_count: int = 0, mode: str = "PROFESSOR") -> str:
    lines = []
    lines.append("=" * 72)
    lines.append(f"[NODE: GAP_ANALYZER] [MODE: {mode}] [ITER: {iteration_count}]")
    lines.append("-" * 72)
    lines.append(f"Research area: \"{result['query']}\"")
    lines.append(f"Sub-topics analyzed: {result['total_subtopics']}")
    lines.append(f"Identified gaps: {result['gap_count']}")
    lines.append("-" * 72)

    if result["gaps"]:
        lines.append("UNCOVERED AREAS (gaps where no faculty has expertise):")
        for gap in result["gaps"]:
            lines.append(
                f"  - {gap['subtopic']}: {gap['paper_count']} of "
                f"{gap['total_papers']} trending papers; "
                f"0 of {gap['total_faculty']} faculty cover it"
            )

    if result["covered"]:
        lines.append("-" * 40)
        lines.append("COVERED AREAS:")
        for cov in result["covered"]:
            names = ", ".join(cov["faculty_covering"][:3])
            if len(cov["faculty_covering"]) > 3:
                names += f" (+{len(cov['faculty_covering']) - 3} more)"
            lines.append(
                f"  - {cov['subtopic']}: {cov['paper_count']} of "
                f"{cov['total_papers']} papers; "
                f"{cov['faculty_count']} of {cov['total_faculty']} faculty "
                f"cover it ({names})"
            )

    lines.append("=" * 72)
    return "\n".join(lines)


def gap_analyze(state: dict) -> dict:
    query = state.get("refined_query") or state.get("user_query", "")
    iteration = state.get("iteration_count", 0)
    mode = state.get("user_mode", "PROFESSOR")
    papers = state.get("retrieved_papers", [])

    paper_result = {
        "query": query,
        "papers": papers,
        "source": state.get("_paper_result", {}).get("source", ""),
    }
    result = analyze_gap(query, paper_result)

    return {
        "identified_gaps": result["gaps"],
        "session_stage": "AFTER_GAP_ANALYSIS",
        "last_node": "GAP_ANALYZER",
        "_gap_result": result,
    }


if __name__ == "__main__":
    queries = [
        "NLP large language models",
        "computer vision robotics",
        "cloud computing microservices",
        "reinforcement learning",
    ]
    for q in queries:
        result = analyze_gap(q)
        print(format_gap_result(result))
        print()
