import os
import sys

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from src.faculty_loader import load_faculty_profiles


def find_faculty_by_name(
    name_query: str,
    profiles: list[dict] | None = None,
) -> dict:
    if profiles is None:
        profiles = load_faculty_profiles()

    exact_matches = []
    partial_matches = []

    clean_query = name_query.strip().lower()

    for profile in profiles:
        name_lower = profile["name"].lower()
        if clean_query == name_lower:
            exact_matches.append(profile)
            continue
        if clean_query in name_lower:
            partial_matches.append(profile)
            continue
        last_name = name_lower.split()[-1]
        if len(last_name) > 2 and last_name in clean_query:
            partial_matches.append(profile)
            continue
        first_name = name_lower.split()[1] if name_lower.startswith("dr. ") else name_lower.split()[0]
        if len(first_name) > 2 and first_name in clean_query:
            partial_matches.append(profile)

    return {
        "query": name_query,
        "exact_matches": exact_matches,
        "partial_matches": partial_matches,
        "all_matches": exact_matches + partial_matches,
        "ambiguous": len(exact_matches) + len(partial_matches) > 1,
        "found": len(exact_matches) + len(partial_matches) > 0,
    }


def format_detail_result(result: dict, iteration_count: int = 0, mode: str = "STUDENT") -> str:
    lines = []
    lines.append("=" * 72)
    lines.append(f"[NODE: DETAIL_RETRIEVER] [MODE: {mode}] [ITER: {iteration_count}]")
    lines.append("-" * 72)

    if not result["found"]:
        lines.append(f"No faculty found matching \"{result['query']}\".")
        lines.append("Try the full name (e.g. \"Dr. Priya Sharma\") or just the last name.")
        lines.append("=" * 72)
        return "\n".join(lines)

    if result["ambiguous"]:
        lines.append(f"Multiple matches for \"{result['query']}\". Which one?")
        lines.append("-" * 40)
        all_matches = result["exact_matches"] + result["partial_matches"]
        for i, p in enumerate(all_matches, 1):
            areas = ", ".join(p.get("research_areas", []))
            lines.append(f"  {i}. {p['name']} ({p['department']}) — {areas}")
        lines.append("-" * 40)
        lines.append(">>> [WAITING FOR INPUT]")
        lines.append("=" * 72)
        return "\n".join(lines)

    profile = (result["exact_matches"] + result["partial_matches"])[0]
    lines.extend(_format_full_profile(profile))
    lines.append("=" * 72)
    return "\n".join(lines)


def _format_full_profile(profile: dict) -> list[str]:
    lines = []
    name = profile["name"]
    dept = profile["department"]
    areas = ", ".join(profile.get("research_areas", []))
    keywords = ", ".join(profile.get("keywords", []))
    bio = profile.get("bio", "")
    papers = profile.get("papers", 0)
    citations = profile.get("citations", 0)
    current = profile.get("current_projects", 0)
    max_p = profile.get("max_projects", 0)
    email = profile.get("email", "")

    lines.append(f"Faculty: {name}")
    lines.append(f"Department: {dept}")
    lines.append("-" * 40)
    lines.append(f"Research Areas: {areas}")
    lines.append(f"Keywords: {keywords}")
    lines.append("-" * 40)
    lines.append(f"Bio:")
    import re
    paragraphs = re.split(r"(?<=[a-z])\.\s+", bio)
    for paragraph in paragraphs:
        stripped = paragraph.strip()
        if stripped:
            if not stripped.endswith("."):
                stripped += "."
            lines.append(f"  {stripped}")
    lines.append("-" * 40)
    lines.append(f"Publications: {papers}")
    lines.append(f"Citations: {citations}")
    lines.append(f"Project Load: {current}/{max_p}")
    lines.append(f"Email: {email}")
    return lines


def get_next_unshown(
    shortlisted: list[dict],
    shown_ids: list[str],
) -> dict | None:
    for candidate in shortlisted:
        if candidate["id"] not in shown_ids:
            return candidate
    return None


def detail_retrieve(state: dict) -> dict:
    query = state.get("user_query", "")
    mode = state.get("user_mode", "STUDENT")
    iteration = state.get("iteration_count", 0)
    shown = state.get("shown_faculty_ids", [])
    shortlisted = state.get("shortlisted_faculty", [])

    search_query = query
    for prefix in ["tell me about ", "detail ", "details ", "about "]:
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
        "shortlisted_faculty": shortlisted,
        "shown_faculty_ids": shown,
        "session_stage": "AFTER_DETAIL",
        "last_node": "DETAIL_RETRIEVER",
        "_detail_result": result,
    }


def show_alternate(state: dict) -> dict:
    shortlisted = state.get("shortlisted_faculty", [])
    shown = state.get("shown_faculty_ids", [])
    mode = state.get("user_mode", "STUDENT")
    iteration = state.get("iteration_count", 0)

    next_faculty = get_next_unshown(shortlisted, shown)

    if next_faculty is None:
        all_ids = {f["id"] for f in shortlisted}
        shown_set = set(shown)
        if all_ids.issubset(shown_set):
            return {
                "session_stage": "ALL_SHOWN",
                "last_node": "DETAIL_RETRIEVER",
                "_alternate_message": (
                    f"[DETAIL_RETRIEVER] All {len(shortlisted)} matched faculty "
                    f"have been shown. Try a different query."
                ),
            }
        return {
            "shortlisted_faculty": [],
            "session_stage": "AFTER_DETAIL",
            "last_node": "DETAIL_RETRIEVER",
            "_alternate_message": "No more unshown faculty available.",
        }

    fid = next_faculty["id"]
    if fid not in shown:
        shown.append(fid)

    return {
        "shortlisted_faculty": shortlisted,
        "shown_faculty_ids": shown,
        "session_stage": "AFTER_DETAIL",
        "last_node": "DETAIL_RETRIEVER",
        "_alternate_faculty": next_faculty,
    }


if __name__ == "__main__":
    test_queries = [
        "Priya Sharma",
        "tell me about Dr. Priya Sharma",
        "Sharma",
        "Mehta",
        "Dr. John Doe",
        "Kapoor",
    ]
    for q in test_queries:
        result = find_faculty_by_name(q)
        print(format_detail_result(result))
        print()

    profiles = load_faculty_profiles()
    shortlisted_sim = [
        {
            "id": "prof_01",
            "name": "Dr. Priya Sharma",
            "department": "CSE",
            "research_areas": ["NLP", "LLMs"],
        },
        {
            "id": "prof_03",
            "name": "Dr. Arjun Mehta",
            "department": "CSE",
            "research_areas": ["CV", "medical imaging"],
        },
        {
            "id": "prof_05",
            "name": "Dr. Kavita Iyer",
            "department": "ECE",
            "research_areas": ["IoT", "embedded"],
        },
    ]

    shown = ["prof_01", "prof_03"]
    alt = get_next_unshown(shortlisted_sim, shown)
    print(f"Next unshown after {shown}: {alt['name'] if alt else 'None'}")

    shown2 = ["prof_01", "prof_03", "prof_05"]
    alt2 = get_next_unshown(shortlisted_sim, shown2)
    print(f"Next unshown after {shown2}: {alt2['name'] if alt2 else 'None'}")
