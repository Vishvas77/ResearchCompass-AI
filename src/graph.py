import os
import sys
import re

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from langgraph.graph import StateGraph, START, END

from src.state import SessionState
from src.router import classify_intent, llm_classify_intent, format_help
from src.faculty_loader import get_or_build_retriever
from src.rag_retriever import hybrid_match, format_hybrid_results
from src.detail_retriever import find_faculty_by_name, format_detail_result, get_next_unshown
from src.paper_searcher import search_papers, format_paper_results
from src.gap_analyzer import analyze_gap, format_gap_result
from src.collab_matcher import find_collaborators, format_collab_result
from src.project_suggester import suggest_projects, format_project_suggestions
from src.workload_checker import check_workload, format_workload_result, list_busy_faculty
from src.faculty_loader import load_faculty_profiles
from src.email_generator import email_generator_node
from src.email_approval import email_approval_node
from src.human_validator import human_validator_node


_vectorstore = None
_retriever = None


def _ensure_retriever():
    global _vectorstore, _retriever
    if _retriever is None:
        _vectorstore, _retriever = get_or_build_retriever()
    return _vectorstore, _retriever


def router_node(state: SessionState) -> dict:
    query = state.get("user_query", "")
    mode = state.get("user_mode", "STUDENT")
    iteration = state.get("iteration_count", 0)
    session_stage = state.get("session_stage", "")

    if session_stage == "APPROVE_EMAIL":
        return {
            "session_stage": "APPROVE_EMAIL",
            "last_node": "ROUTER",
            "node_history": ["EMAIL_APPROVAL"],
        }

    intent = llm_classify_intent(query, mode)

    if intent == "HELP":
        return {
            "session_stage": intent,
            "last_node": "ROUTER",
            "node_history": [intent],
        }

    return {
        "session_stage": intent,
        "last_node": "ROUTER",
        "node_history": [intent],
    }


def mode_switcher_node(state: SessionState) -> dict:
    query = state.get("user_query", "")
    current_mode = state.get("user_mode", "STUDENT")

    if "professor" in query.lower():
        new_mode = "PROFESSOR"
    elif "student" in query.lower():
        new_mode = "STUDENT"
    else:
        new_mode = current_mode

    return {
        "user_mode": new_mode,
        "session_stage": "AFTER_MODE_SWITCH",
        "last_node": "MODE_SWITCHER",
        "shown_faculty_ids": [],
        "shortlisted_faculty": [],
        "selected_faculty": None,
        "email_draft": "",
        "pending_confirmation": False,
        "email_sent": False,
    }


def match_node(state: SessionState) -> dict:
    query = state.get("user_query", "")
    mode = state.get("user_mode", "STUDENT")
    shown = state.get("shown_faculty_ids", [])
    iteration = state.get("iteration_count", 0)

    results = hybrid_match(query, top_k=3, exclude_ids=shown)

    for r in results:
        if r["id"] not in shown:
            shown.append(r["id"])

    return {
        "shortlisted_faculty": results,
        "shown_faculty_ids": shown,
        "session_stage": "AFTER_MATCH",
        "last_node": "RAG_RETRIEVER",
    }


def detail_node(state: SessionState) -> dict:
    query = state.get("user_query", "")
    mode = state.get("user_mode", "STUDENT")
    shown = state.get("shown_faculty_ids", [])
    iteration = state.get("iteration_count", 0)

    search_query = query
    for prefix in [
        "tell me about ", "detail ", "details about ",
        "profile of ", "who is ",
    ]:
        if query.lower().startswith(prefix):
            search_query = query[len(prefix):].strip()
            break

    result = find_faculty_by_name(search_query)

    if result["found"] and not result["ambiguous"]:
        profile = (result["exact_matches"] + result["partial_matches"])[0]
        fid = profile["id"]
        if fid not in shown:
            shown.append(fid)

    return {
        "shown_faculty_ids": shown,
        "session_stage": "AFTER_DETAIL",
        "last_node": "DETAIL_RETRIEVER",
        "_detail_result": result,
    }


def alternate_node(state: SessionState) -> dict:
    shortlisted = state.get("shortlisted_faculty", [])
    shown = state.get("shown_faculty_ids", [])

    next_faculty = get_next_unshown(shortlisted, shown)

    if next_faculty is None:
        all_ids = {f["id"] for f in shortlisted} if shortlisted else set()
        shown_set = set(shown)
        if shortlisted and all_ids.issubset(shown_set):
            return {
                "session_stage": "ALL_SHOWN",
                "last_node": "DETAIL_RETRIEVER",
                "_alternate_message": (
                    f"All {len(shortlisted)} matched faculty have been shown. "
                    f"Try a different query."
                ),
            }
        return {
            "session_stage": "AFTER_ALTERNATE",
            "last_node": "DETAIL_RETRIEVER",
            "_alternate_message": "No more unshown faculty available. Try a new search.",
        }

    fid = next_faculty["id"]
    if fid not in shown:
        shown.append(fid)

    return {
        "shown_faculty_ids": shown,
        "session_stage": "AFTER_ALTERNATE",
        "last_node": "DETAIL_RETRIEVER",
        "_alternate_faculty": next_faculty,
    }


def project_node(state: SessionState) -> dict:
    query = state.get("user_query", "")
    mode = state.get("user_mode", "STUDENT")
    iteration = state.get("iteration_count", 0)
    shortlisted = state.get("shortlisted_faculty", [])
    gaps = state.get("identified_gaps", [])

    suggestions = suggest_projects(query, shortlisted, gaps)

    return {
        "project_suggestions": suggestions,
        "session_stage": "AFTER_PROJECTS",
        "last_node": "PROJECT_SUGGESTER",
    }


def paper_node(state: SessionState) -> dict:
    query = state.get("user_query", "")
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


def map_node(state: SessionState) -> dict:
    query = state.get("user_query", "")
    mode = state.get("user_mode", "PROFESSOR")
    shown = state.get("shown_faculty_ids", [])
    iteration = state.get("iteration_count", 0)

    results = hybrid_match(query, top_k=5, exclude_ids=shown)

    for r in results:
        if r["id"] not in shown:
            shown.append(r["id"])

    return {
        "shortlisted_faculty": results,
        "shown_faculty_ids": shown,
        "session_stage": "AFTER_MAP",
        "last_node": "RAG_RETRIEVER",
    }


def gap_node(state: SessionState) -> dict:
    query = state.get("user_query", "")
    mode = state.get("user_mode", "PROFESSOR")
    iteration = state.get("iteration_count", 0)
    retrieved = state.get("retrieved_papers", [])

    paper_result = {
        "query": query,
        "papers": retrieved,
        "source": state.get("_paper_result", {}).get("source", ""),
    }
    result = analyze_gap(query, paper_result)

    return {
        "identified_gaps": result["gaps"],
        "session_stage": "AFTER_GAP_ANALYSIS",
        "last_node": "GAP_ANALYZER",
        "_gap_result": result,
    }


def collab_node(state: SessionState) -> dict:
    query = state.get("user_query", "")
    mode = state.get("user_mode", "PROFESSOR")
    iteration = state.get("iteration_count", 0)
    shown = state.get("shown_faculty_ids", [])

    target_name = query
    for prefix in [
        "could i collaborate with ", "collaborate with ",
        "can i work with ", "find collaborators for ",
    ]:
        if target_name.lower().startswith(prefix):
            target_name = target_name[len(prefix):].strip()
            break

    if target_name.lower().startswith("dr. "):
        target_name = target_name[4:].strip()

    result = find_collaborators(target_name)

    shortlisted = []
    for m in result.get("matches", []):
        entry = {
            "id": m["id"],
            "name": m["name"],
            "department": m["department"],
            "research_areas": m.get("research_areas", []),
            "keywords": m.get("keywords_unique_to_pair", []),
            "bio": "",
            "papers": 0,
            "citations": 0,
            "current_projects": m.get("current_projects", 0),
            "max_projects": m.get("max_projects", 0),
            "email": m.get("email", "unknown@university.edu"),
            "hybrid_pct": round(m.get("collaboration_score", 0) * 100, 1),
            "vector_score": m.get("complementarity", 0),
            "keyword_score": m.get("kw_adjacency", 0),
            "hybrid_score": m.get("collaboration_score", 0),
            "matched_keywords": [],
            "n_matched": 0,
            "n_query_kw": 0,
            "score_breakdown": f"collab_score: {m.get('collaboration_score', 0):.4f}",
        }
        shortlisted.append(entry)
        if m["id"] not in shown:
            shown.append(m["id"])

    return {
        "shortlisted_faculty": shortlisted,
        "shown_faculty_ids": shown,
        "collaboration_score": result.get("collaboration_score", 0.0),
        "faculty_workload": {
            m["name"]: m.get("workload_ratio", "?")
            for m in result.get("matches", [])
        },
        "session_stage": "AFTER_COLLAB_MATCH",
        "last_node": "COLLAB_MATCHER",
        "_collab_result": result,
    }


def workload_node(state: SessionState) -> dict:
    query = state.get("user_query", "")
    mode = state.get("user_mode", "PROFESSOR")
    iteration = state.get("iteration_count", 0)

    # Detect "who is busy" / workload list queries (including least/most variations)
    busy_patterns = [
        r"\b(who|whom)\s+(is|are|all)\s+(busy|full|at\s+capacity|overloaded|maxed)\b",
        r"\b(show|list|display)\s+(all\s+)?(workloads?|capacity)\b",
        r"\b(everyone|everybody|all)\s+(workload|capacity|busy)\b",
        r"\b(how|what)\s+(busy|loaded|full)\s+(is|are)\s+(everyone|everybody|all|faculty|professors?|the\s+faculty)\b",
        r"\bwho('?s|s| is)\s+(the\s+)?(most\s+)?(busy|loaded|full)\b",
        r"\b(least|most|fewest)\s+(busy|projects?|loaded|capacity|workload)\b",
        r"\bwho('?s|s| is| are)\s+(the\s+)?(least|most)\s+(busy|loaded)\b",
        r"\bwho\s+(is\s+)?(working\s+on|doing)\s+(the\s+)?(most|least)\s+projects?\b",
    ]
    is_busy_query = any(re.search(p, query.lower()) for p in busy_patterns)

    if is_busy_query:
        result = list_busy_faculty()
        ql = query.lower()
        is_least = bool(re.search(r"\b(least|fewest|lowest)\b", ql))
        is_most_projects = bool(re.search(r"\b(most|maximum)\s+(projects?|loaded)\b", ql) or
                                re.search(r"\b(working\s+on|doing)\s+(the\s+)?(most)\b", ql))
        apply_sort = is_least or is_most_projects
        if apply_sort:
            if is_least:
                result["all"].sort(key=lambda x: (x["load_ratio"], x["name"]))
            else:
                result["all"].sort(key=lambda x: (-x["load_ratio"], x["name"]))
        return {
            "faculty_workload": {r["name"]: f"{r['current_projects']}/{r['max_projects']}" for r in result["all"]},
            "session_stage": "AFTER_WORKLOAD_LIST",
            "last_node": "WORKLOAD_CHECKER",
            "_workload_result": result,
            "_workload_sort": "least" if is_least else ("most_projects" if is_most_projects else "busiest"),
        }

    # Extract name for single-person query
    name = query
    for prefix in ["check workload of ", "workload of ", "capacity of ", "how busy is "]:
        if name.lower().startswith(prefix):
            name = name[len(prefix):].strip()
            break

    result = check_workload(name)

    return {
        "faculty_workload": {
            result.get("target_name", ""): f"{result.get('current_projects', 0)}/{result.get('max_projects', 0)}"
        },
        "session_stage": "AFTER_WORKLOAD_CHECK",
        "last_node": "WORKLOAD_CHECKER",
        "_workload_result": result,
    }


def list_node(state: SessionState) -> dict:
    """List all 15 faculty members with department and areas."""
    profiles = load_faculty_profiles()
    mode = state.get("user_mode", "STUDENT")
    iteration = state.get("iteration_count", 0)
    shown = state.get("shown_faculty_ids", [])

    shortlisted = []
    for p in profiles:
        entry = {
            "id": p["id"], "name": p["name"], "department": p["department"],
            "research_areas": p.get("research_areas", []),
            "keywords": p.get("keywords", []),
            "papers": p.get("papers", 0), "citations": p.get("citations", 0),
            "current_projects": p.get("current_projects", 0),
            "max_projects": p.get("max_projects", 0),
            "email": p.get("email", ""),
            "hybrid_pct": 100.0, "vector_score": 1.0, "keyword_score": 1.0,
            "hybrid_score": 1.0, "matched_keywords": [], "n_matched": 0,
            "n_query_kw": 0, "score_breakdown": "list-all",
        }
        shortlisted.append(entry)
        if p["id"] not in shown:
            shown.append(p["id"])

    return {
        "shortlisted_faculty": shortlisted,
        "shown_faculty_ids": shown,
        "session_stage": "AFTER_LIST",
        "last_node": "LIST_NODE",
    }


def topics_node(state: SessionState) -> dict:
    """Show all distinct research areas/topics available."""
    profiles = load_faculty_profiles()
    mode = state.get("user_mode", "STUDENT")
    iteration = state.get("iteration_count", 0)

    area_map = {}
    for p in profiles:
        dept = p.get("department", "?")
        for area in p.get("research_areas", []):
            area_map.setdefault(area, []).append(p["name"])

    return {
        "session_stage": "AFTER_TOPICS",
        "last_node": "TOPICS_NODE",
        "_topics_result": {
            "area_map": area_map,
            "total_areas": len(area_map),
            "total_faculty": len(profiles),
        },
    }


def select_node(state: SessionState) -> dict:
    query = state.get("user_query", "")
    shortlisted = state.get("shortlisted_faculty", [])
    iteration = state.get("iteration_count", 0)

    if not shortlisted:
        return {
            "session_stage": "NO_FACULTY_TO_SELECT",
            "last_node": "FACULTY_SELECTOR",
            "_select_message": "No faculty results to select from. Run a search first.",
        }

    numbers = [c for c in query if c.isdigit()]
    index = int("".join(numbers)) if numbers else None

    if index is None or index < 1 or index > len(shortlisted):
        return {
            "session_stage": "INVALID_SELECT",
            "last_node": "FACULTY_SELECTOR",
            "_select_message": (
                f"Select a number between 1 and {len(shortlisted)}. "
                f"You said: \"{query}\""
            ),
        }

    selected = shortlisted[index - 1]
    return {
        "selected_faculty": selected,
        "session_stage": "AFTER_SELECT",
        "last_node": "FACULTY_SELECTOR",
    }


def chat_node(state: SessionState) -> dict:
    query = state.get("user_query", "").strip().lower()
    mode = state.get("user_mode", "STUDENT")

    greetings = {"hi","hey","hello","yo","sup","good morning","good afternoon","good evening"}
    thanks_words = {"thanks","thank you","thx","ty","appreciate it","appreciate that","cool","nice","great","awesome","wow"}
    identity_q = {"who are you","what are you","what do you do","your name","what can you do","whats your name","what's your name"}
    how_are_you = {"how are you","how r u","how are u","how's it going","hows it going","whats up","what's up"}

    query_stripped = query.rstrip(".!? ")

    if query_stripped in greetings:
        reply = f"Hey there! I'm AcademiMatch, your research matchmaker. I can help you find professors, explore research topics, or suggest projects. What can I help with?"
    elif query_stripped in how_are_you:
        reply = "I'm running smoothly! Ready to help you find professors, explore research, or brainstorm ideas. What are you looking for?"
    elif query_stripped in thanks_words:
        reply = "Happy to help! Anything else you'd like to explore?"
    elif query_stripped in identity_q:
        reply = f"I'm AcademiMatch — a research matching agent. I know 15 professors across CSE & ECE with 58 research areas. You're in {mode} mode right now. Ask me to find faculty, suggest projects, or analyze research trends!"
    else:
        replies = {
            "student": [
                "I can help you find professors by research area — just ask 'who works on NLP?' or 'I'm looking for someone in ML.'",
                "Want to see all 15 professors? Say 'list all professors' or 'show all faculty.'",
                "Curious about available research topics? Try 'what topics are there?' or 'research areas.'",
                "If you find someone interesting, say 'tell me about Dr. Sharma' for their full profile.",
                "Need project ideas? Ask 'what project could I do?' and I'll suggest some based on matched faculty.",
            ],
            "professor": [
                "Looking for research trends? Try 'what's trending in AI' or 'latest papers in cybersecurity.'",
                "Want to find collaborators? Say 'who could I collaborate with on NLP?' or 'can I work with Dr. Sharma?'",
                "Curious about gaps in our research coverage? Ask 'what are we missing?' or 'what gaps exist?'",
                "Check anyone's workload — say 'how busy is Dr. Iyer?' or 'who has capacity?'",
                "Need to contact someone? Select a faculty member first, then say 'email' to draft a message.",
            ],
        }
        import random
        reply = random.choice(replies.get("student" if mode == "STUDENT" else "professor", replies["student"]))

    return {
        "session_stage": "AFTER_CHAT",
        "last_node": "CHAT_NODE",
        "_chat_reply": reply,
    }


def stats_node(state: SessionState) -> dict:
    """Handle 'who has the most X' type comparative queries."""
    query = state.get("user_query", "").lower()
    shortlisted = state.get("shortlisted_faculty", [])
    iteration = state.get("iteration_count", 0)

    if "score" in query and shortlisted:
        # Show top match from last search
        top = shortlisted[0]
        return {
            "session_stage": "AFTER_STATS",
            "last_node": "STATS_NODE",
            "_stats_result": {
                "type": "top_score",
                "title": f"Top match: {top['name']} at {top['hybrid_pct']}%",
                "items": [f"{r['name']} ({r['hybrid_pct']}%)" for r in shortlisted[:5]],
            },
        }

    # Show top cited / most papers
    profiles = load_faculty_profiles()
    if "citation" in query or "cited" in query:
        ranked = sorted(profiles, key=lambda p: p.get("citations", 0), reverse=True)
        items = [f"{p['name']}: {p.get('citations', 0):,} citations" for p in ranked[:5]]
        return {
            "session_stage": "AFTER_STATS",
            "last_node": "STATS_NODE",
            "_stats_result": {
                "type": "top_cited",
                "title": f"Most cited: {ranked[0]['name']} ({ranked[0].get('citations', 0):,} citations)",
                "items": items,
            },
        }

    if "paper" in query or "publication" in query or "published" in query:
        ranked = sorted(profiles, key=lambda p: p.get("papers", 0), reverse=True)
        items = [f"{p['name']}: {p.get('papers', 0)} papers" for p in ranked[:5]]
        return {
            "session_stage": "AFTER_STATS",
            "last_node": "STATS_NODE",
            "_stats_result": {
                "type": "top_papers",
                "title": f"Most published: {ranked[0]['name']} ({ranked[0].get('papers', 0)} papers)",
                "items": items,
            },
        }

    # Default: show overall stats
    return {
        "session_stage": "AFTER_STATS",
        "last_node": "STATS_NODE",
        "_stats_result": {
            "type": "overall",
            "title": "Faculty statistics",
            "items": [
                f"Most cited: {max(profiles, key=lambda p: p.get('citations',0))['name']}",
                f"Most published: {max(profiles, key=lambda p: p.get('papers',0))['name']}",
                f"Busiest: {max(profiles, key=lambda p: p.get('current_projects',0))['name']}",
            ],
        },
    }


def report_node(state: SessionState) -> dict:
    return {
        "session_stage": "AFTER_REPORT",
        "last_node": "REPORTER",
    }


def _make_graph() -> StateGraph:
    builder = StateGraph(SessionState)

    builder.add_node("ROUTER", router_node)
    builder.add_node("MODE_SWITCHER", mode_switcher_node)
    builder.add_node("RAG_RETRIEVER", match_node)
    builder.add_node("DETAIL_RETRIEVER", detail_node)
    builder.add_node("SHOW_ALTERNATE", alternate_node)
    builder.add_node("PROJECT_SUGGESTER", project_node)
    builder.add_node("FACULTY_SELECTOR", select_node)
    builder.add_node("EMAIL_GENERATOR", email_generator_node)
    builder.add_node("EMAIL_APPROVAL", email_approval_node)
    builder.add_node("PAPER_SEARCHER", paper_node)
    builder.add_node("GAP_ANALYZER", gap_node)
    builder.add_node("COLLAB_MATCHER", collab_node)
    builder.add_node("WORKLOAD_CHECKER", workload_node)
    builder.add_node("LIST_NODE", list_node)
    builder.add_node("TOPICS_NODE", topics_node)
    builder.add_node("CHAT_NODE", chat_node)
    builder.add_node("STATS_NODE", stats_node)
    builder.add_node("HUMAN_VALIDATOR", human_validator_node)
    builder.add_node("REPORTER", report_node)

    builder.add_edge(START, "ROUTER")

    builder.add_conditional_edges(
        "ROUTER",
        lambda s: s.get("session_stage", "MATCH"),
        {
            "MODE_SWITCH": "MODE_SWITCHER",
            "MATCH": "RAG_RETRIEVER",
            "DETAIL": "DETAIL_RETRIEVER",
            "ALTERNATE": "SHOW_ALTERNATE",
            "PROJECT": "PROJECT_SUGGESTER",
            "SELECT": "FACULTY_SELECTOR",
            "EMAIL": "EMAIL_GENERATOR",
            "TREND": "PAPER_SEARCHER",
            "MAP": "RAG_RETRIEVER",
            "COLLAB": "COLLAB_MATCHER",
            "GAP": "GAP_ANALYZER",
            "WORKLOAD": "WORKLOAD_CHECKER",
            "LIST": "LIST_NODE",
            "TOPICS": "TOPICS_NODE",
            "CHAT": "CHAT_NODE",
            "STATS": "STATS_NODE",
            "HELP": END,
            "EXIT": END,
            "APPROVE_EMAIL": "EMAIL_APPROVAL",
        },
    )

    builder.add_edge("MODE_SWITCHER", END)
    builder.add_edge("RAG_RETRIEVER", END)
    builder.add_edge("DETAIL_RETRIEVER", END)
    builder.add_edge("SHOW_ALTERNATE", END)
    builder.add_edge("PROJECT_SUGGESTER", END)
    builder.add_edge("FACULTY_SELECTOR", END)
    builder.add_edge("EMAIL_GENERATOR", END)
    builder.add_edge("EMAIL_APPROVAL", END)
    builder.add_edge("PAPER_SEARCHER", END)
    builder.add_edge("GAP_ANALYZER", END)
    builder.add_edge("COLLAB_MATCHER", END)
    builder.add_edge("WORKLOAD_CHECKER", END)
    builder.add_edge("LIST_NODE", END)
    builder.add_edge("TOPICS_NODE", END)
    builder.add_edge("CHAT_NODE", END)
    builder.add_edge("STATS_NODE", END)
    builder.add_edge("HUMAN_VALIDATOR", END)
    builder.add_edge("REPORTER", END)

    return builder


def build_graph():
    builder = _make_graph()
    graph = builder.compile()
    return graph


if __name__ == "__main__":
    graph = build_graph()
    try:
        graph.get_graph().draw_mermaid_png(
            output_file_path=os.path.join(_proj_root, "graph.png")
        )
        print("Graph saved to graph.png")
    except Exception as e:
        print(f"Graph visualization skipped: {e}")
