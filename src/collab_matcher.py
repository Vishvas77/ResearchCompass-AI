import os
import sys

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from src.faculty_loader import load_faculty_profiles


def _keyword_set(profile: dict) -> set:
    return set(k.lower() for k in profile.get("keywords", []))


def _complementarity_score(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    sym_diff = a.symmetric_difference(b)
    intersection = a.intersection(b)
    union = a.union(b)
    complementarity = len(sym_diff) / max(len(union), 1)
    overlap_penalty = len(intersection) / max(len(union), 1)
    raw = complementarity - 0.5 * overlap_penalty
    return max(0.0, min(1.0, raw))


def _workload_penalty(profile: dict) -> float:
    current = profile.get("current_projects", 0)
    max_p = profile.get("max_projects", 1)
    if max_p == 0:
        return 1.0
    load_ratio = current / max_p
    if load_ratio >= 1.0:
        return 1.0
    if load_ratio >= 0.8:
        return 0.75
    if load_ratio >= 0.5:
        return 0.4
    return 0.0


def _soft_area_match(a: dict, b: dict) -> float:
    ra_a = [r.lower() for r in a.get("research_areas", [])]
    ra_b = [r.lower() for r in b.get("research_areas", [])]
    if not ra_a or not ra_b:
        return 0.0

    matches = 0
    for area_a in ra_a:
        a_words = set(area_a.split())
        for area_b in ra_b:
            b_words = set(area_b.split())
            common = a_words & b_words
            if common:
                weight = len(common) / max(len(a_words), len(b_words))
                matches += weight
                break

    return min(1.0, matches / max(len(ra_a), 1))


def _keyword_adjacency_score(a: set, b: set, profiles: list[dict]) -> float:
    related_bonus = 0.0
    for kw_a in a:
        for kw_b in b:
            if kw_a == kw_b:
                continue
            a_words = set(kw_a.replace("-", " ").split())
            b_words = set(kw_b.replace("-", " ").split())
            if a_words & b_words:
                related_bonus += 0.02
    return min(0.3, related_bonus)


def find_collaborators(
    target_name: str,
    expertise_area: str | None = None,
) -> dict:
    profiles = load_faculty_profiles()

    target = None
    for p in profiles:
        if target_name.lower() in p["name"].lower():
            target = p
            break

    if target is None:
        return {
            "target_name": target_name,
            "found": False,
            "message": f"No faculty found matching \"{target_name}\".",
            "matches": [],
            "collaboration_score": 0.0,
        }

    target_keywords = _keyword_set(target)
    candidates = []

    for p in profiles:
        if p["id"] == target["id"]:
            continue

        cand_keywords = _keyword_set(p)
        comp_score = _complementarity_score(target_keywords, cand_keywords)
        area_similarity = _soft_area_match(target, p)
        kw_adjacency = _keyword_adjacency_score(target_keywords, cand_keywords, profiles)
        dept_bonus = 0.1 if p["department"] == target["department"] else 0.0

        collab_score = 0.35 * comp_score + 0.25 * area_similarity + 0.2 * kw_adjacency + dept_bonus
        if expertise_area and any(
            expertise_area.lower() in ra.lower()
            for ra in p.get("research_areas", [])
        ):
            collab_score += 0.1

        workload = _workload_penalty(p)
        effective_score = collab_score * (1.0 - 0.3 * workload)
        effective_score = round(min(1.0, effective_score), 4)

        keywords_diff = target_keywords.symmetric_difference(cand_keywords)
        keywords_shared = target_keywords.intersection(cand_keywords)

        candidates.append({
            "id": p["id"],
            "name": p["name"],
            "department": p["department"],
            "research_areas": p.get("research_areas", []),
            "current_projects": p.get("current_projects", 0),
            "max_projects": p.get("max_projects", 0),
            "email": p.get("email", ""),
            "at_capacity": p.get("current_projects", 0) >= p.get("max_projects", 1),
            "complementarity": round(comp_score, 4),
            "area_similarity": round(area_similarity, 4),
            "kw_adjacency": round(kw_adjacency, 4),
            "collaboration_score": effective_score,
            "keywords_shared": sorted(keywords_shared),
            "keywords_unique_to_pair": sorted(keywords_diff)[:10],
            "workload_ratio": (
                f"{p.get('current_projects', 0)}/{p.get('max_projects', 0)}"
            ),
            "workload_penalty_applied": workload > 0,
        })

    candidates.sort(
        key=lambda x: (not x["at_capacity"], x["collaboration_score"]),
        reverse=True,
    )

    return {
        "target_name": target_name,
        "found": True,
        "target_profile": target,
        "matches": candidates[:5],
        "collaboration_score": candidates[0]["collaboration_score"] if candidates else 0.0,
    }


def format_collab_result(result: dict, iteration_count: int = 0, mode: str = "PROFESSOR") -> str:
    lines = []
    lines.append("=" * 72)
    lines.append(f"[NODE: COLLAB_MATCHER] [MODE: {mode}] [ITER: {iteration_count}]")
    lines.append("-" * 72)

    if not result["found"]:
        lines.append(result["message"])
        lines.append("=" * 72)
        return "\n".join(lines)

    target = result["target_profile"]
    lines.append(f"Target: {target['name']} ({target['department']})")
    lines.append(f"Expertise: {', '.join(target.get('research_areas', []))}")
    lines.append("-" * 72)
    lines.append("COLLABORATION CANDIDATES (complementary expertise + workload-aware):")
    lines.append(
        "Scoring: 0.35*complementarity + 0.25*area_sim "
        "+ 0.2*kw_adjacency + dept_bonus, x workload penalty"
    )
    lines.append("-" * 40)

    for i, m in enumerate(result["matches"], 1):
        pct = round(m["collaboration_score"] * 100, 1)
        cap_flag = " [AT CAPACITY]" if m["at_capacity"] else ""
        lines.append(
            f"{i}. {m['name']} ({m['department']}) — {pct}%{cap_flag}"
        )
        lines.append(
            f"   Areas: {', '.join(m['research_areas'])}"
        )
        lines.append(
            f"   Workload: {m['workload_ratio']}"
            + (" (deprioritized)" if m["workload_penalty_applied"] else "")
        )
        if m["keywords_shared"]:
            lines.append(
                f"   Overlapping keywords: {', '.join(m['keywords_shared'][:5])}"
            )
        lines.append(
            f"   Complementary keywords: "
            f"{', '.join(m['keywords_unique_to_pair'][:5])}"
            + ("..." if len(m.get('keywords_unique_to_pair', [])) > 5 else "")
        )
        lines.append(
            f"   Comp: {m['complementarity']:.4f} | "
            f"Area Sim: {m['area_similarity']:.4f} | "
            f"KW Adj: {m['kw_adjacency']:.4f}"
        )

    lines.append("-" * 72)
    if any(m["at_capacity"] for m in result["matches"]):
        at_cap = [m["name"] for m in result["matches"] if m["at_capacity"]]
        lines.append(
            f"Note: {', '.join(at_cap)} at full capacity — "
            f"consider lighter collaboration scope."
        )
    lines.append("=" * 72)
    return "\n".join(lines)


def collab_match(state: dict) -> dict:
    target_name = state.get("user_query", "")
    for prefix in [
        "could i collaborate with ", "collaborate with ",
        "can i work with ", "find collaborators for ",
    ]:
        if target_name.lower().startswith(prefix):
            target_name = target_name[len(prefix):].strip()
            break

    if target_name.lower().startswith("dr. "):
        target_name = target_name[4:].strip()

    iteration = state.get("iteration_count", 0)
    mode = state.get("user_mode", "PROFESSOR")

    result = find_collaborators(target_name)

    return {
        "collaboration_score": result.get("collaboration_score", 0.0),
        "faculty_workload": {
            m["name"]: m["workload_ratio"]
            for m in result.get("matches", [])
        },
        "session_stage": "AFTER_COLLAB_MATCH",
        "last_node": "COLLAB_MATCHER",
        "_collab_result": result,
    }


if __name__ == "__main__":
    tests = [
        ("Priya Sharma", "NLP"),
        ("Arjun Mehta", None),
        ("Kavita Iyer", "IoT"),
        ("Vikram Reddy", "cybersecurity"),
    ]
    for name, area in tests:
        result = find_collaborators(name, area)
        print(format_collab_result(result))
        print()
