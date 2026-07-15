import os
import sys
import re
from typing import Optional

from langchain_chroma import Chroma
from dotenv import load_dotenv

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from src.faculty_loader import (
    _get_embedding_model,
    CHROMA_PATH,
    FACULTY_DIR,
    load_faculty_profiles,
)

load_dotenv()


def _extract_query_keywords(query: str) -> list[str]:
    stop_words = {
        "who", "what", "where", "when", "why", "how", "is", "are", "was",
        "were", "be", "been", "being", "have", "has", "had", "do", "does",
        "did", "will", "would", "shall", "should", "may", "might", "must",
        "can", "could", "a", "an", "the", "in", "on", "at", "to", "for",
        "of", "with", "and", "or", "not", "no", "i", "me", "my", "we",
        "our", "you", "your", "it", "its", "they", "them", "their",
        "about", "works", "work", "find", "search", "looking", "look",
        "tell", "show", "give", "anyone", "somebody", "someone",
        "research", "like", "related", "professor", "faculty",
    }
    tokens = re.findall(r"[a-zA-Z]+", query.lower())
    keywords = [t for t in tokens if t not in stop_words and len(t) > 1]
    return keywords


def _keyword_overlap_score(query: str, faculty_profile: dict) -> float:
    qk = set(_extract_query_keywords(query))
    fk_raw = faculty_profile.get("keywords", [])
    fk = set(k.lower() for k in fk_raw)

    if not qk or not fk:
        return 0.0

    matched = qk & fk
    return len(matched) / len(qk)


def _normalize_chromadb_distance(distance: float) -> float:
    similarity = 1.0 / (1.0 + distance)
    return similarity


ALPHA = 0.6
BETA = 0.4

DEFAULT_K = 3


def hybrid_match(
    query: str,
    top_k: int = DEFAULT_K,
    exclude_ids: Optional[list[str]] = None,
) -> list[dict]:
    exclude_ids = exclude_ids or []

    profiles = {p["id"]: p for p in load_faculty_profiles()}

    embedding_model = _get_embedding_model()
    vectorstore = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embedding_model,
        collection_name="faculty",
    )

    fetch_k = top_k + len(exclude_ids) + 15
    raw_results = vectorstore.similarity_search_with_score(query, k=fetch_k)

    scored = []
    for doc, distance in raw_results:
        fid = doc.metadata.get("id", "")
        if fid in exclude_ids:
            continue

        profile = profiles.get(fid, {})
        vector_score = _normalize_chromadb_distance(distance)
        kw_score = _keyword_overlap_score(query, profile)
        hybrid_score = ALPHA * vector_score + BETA * kw_score

        qk = _extract_query_keywords(query)
        fk = [k.lower() for k in profile.get("keywords", [])]
        matched_kw = [w for w in qk if w in fk]
        n_matched = len(matched_kw)
        n_query_kw = len(qk)

        scored.append({
            "id": fid,
            "name": profile.get("name", ""),
            "department": profile.get("department", ""),
            "research_areas": profile.get("research_areas", []),
            "keywords": profile.get("keywords", []),
            "bio": profile.get("bio", ""),
            "papers": profile.get("papers", 0),
            "citations": profile.get("citations", 0),
            "current_projects": profile.get("current_projects", 0),
            "max_projects": profile.get("max_projects", 0),
            "email": profile.get("email", ""),
            "vector_score": round(vector_score, 4),
            "keyword_score": round(kw_score, 4),
            "hybrid_score": round(hybrid_score, 4),
            "hybrid_pct": round(hybrid_score * 100, 1),
            "matched_keywords": matched_kw,
            "n_matched": n_matched,
            "n_query_kw": n_query_kw,
            "score_breakdown": (
                f"({ALPHA} * {vector_score:.4f}) + "
                f"({BETA} * {kw_score:.4f}) = {hybrid_score:.4f}"
            ),
        })

        if len(scored) >= top_k:
            break

    scored.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return scored


def format_hybrid_results(
    results: list[dict],
    query: str,
    iteration_count: int = 0,
    mode: str = "STUDENT",
) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append(f"[NODE: RAG_RETRIEVER] [MODE: {mode}] [ITER: {iteration_count}]")
    lines.append("-" * 72)
    lines.append(f"Query: \"{query}\"")
    lines.append(f"Scoring: {ALPHA} * vector_similarity + {BETA} * keyword_overlap")
    lines.append(f"Results: {len(results)} faculty matched")
    lines.append("-" * 72)

    for i, r in enumerate(results, 1):
        pct = r["hybrid_pct"]
        areas = ", ".join(r["research_areas"])
        lines.append(
            f"{i}. {r['name']} ({r['department']}) — {pct}%"
        )
        lines.append(f"   Areas: {areas}")
        lines.append(
            f"   Papers: {r['papers']} | Citations: {r['citations']} | "
            f"Load: {r['current_projects']}/{r['max_projects']}"
        )
        lines.append(
            f"   Score breakdown: {r['score_breakdown']}"
        )
        lines.append(
            f"   Keyword match: {r['n_matched']} of "
            f"{r['n_query_kw']} query keywords matched "
            f"({r['matched_keywords']})"
        )

    lines.append("=" * 72)
    return "\n".join(lines)


def rag_retrieve(state: dict) -> dict:
    query = state.get("refined_query") or state.get("user_query", "")
    mode = state.get("user_mode", "STUDENT")
    shown = state.get("shown_faculty_ids", [])
    iteration = state.get("iteration_count", 0)

    results = hybrid_match(query, top_k=DEFAULT_K, exclude_ids=shown)

    for r in results:
        if r["id"] not in shown:
            shown.append(r["id"])

    return {
        "shortlisted_faculty": results,
        "shown_faculty_ids": shown,
        "session_stage": "AFTER_RETRIEVAL",
        "last_node": "RAG_RETRIEVER",
    }


if __name__ == "__main__":
    queries = [
        "who works on NLP and language models",
        "computer vision medical imaging",
        "IoT sensor networks",
        "signal processing 5G MIMO",
        "cloud Kubernetes microservices",
    ]
    for q in queries:
        results = hybrid_match(q, top_k=3)
        print(format_hybrid_results(results, q))
        print()
