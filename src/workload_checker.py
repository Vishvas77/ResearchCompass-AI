import os
import sys

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from src.faculty_loader import load_faculty_profiles


def list_busy_faculty() -> dict:
    """Return a list of all faculty sorted by workload (busiest first)."""
    profiles = load_faculty_profiles()
    results = []
    for p in profiles:
        current = p.get("current_projects", 0)
        max_p = p.get("max_projects", 0)
        load_ratio = current / max(max_p, 1)
        if current >= max_p:
            status = "AT CAPACITY"
        elif load_ratio >= 0.8:
            status = "NEARLY FULL"
        elif load_ratio >= 0.5:
            status = "MODERATE"
        else:
            status = "AVAILABLE"
        results.append({
            "name": p["name"],
            "department": p["department"],
            "research_areas": p.get("research_areas", []),
            "current_projects": current,
            "max_projects": max_p,
            "load_ratio": round(load_ratio, 2),
            "status": status,
            "at_capacity": current >= max_p,
        })
    results.sort(key=lambda x: (-x["load_ratio"], x["name"]))
    return {
        "found": True,
        "mode": "list_all",
        "total": len(results),
        "at_capacity": [r for r in results if r["at_capacity"]],
        "nearly_full": [r for r in results if r["status"] == "NEARLY FULL"],
        "available": [r for r in results if r["status"] in ("AVAILABLE", "MODERATE")],
        "all": results,
    }


def check_workload(target_name: str) -> dict:
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
        }

    current = target.get("current_projects", 0)
    max_p = target.get("max_projects", 0)
    load_ratio = current / max(max_p, 1)

    at_capacity = current >= max_p
    if at_capacity:
        status = "AT CAPACITY"
    elif load_ratio >= 0.8:
        status = "NEARLY FULL"
    elif load_ratio >= 0.5:
        status = "MODERATELY LOADED"
    else:
        status = "AVAILABLE"

    alternatives = []
    if at_capacity or load_ratio >= 0.8:
        for p in profiles:
            if p["id"] == target["id"]:
                continue
            p_current = p.get("current_projects", 0)
            p_max = p.get("max_projects", 0)
            if p_current >= p_max:
                continue

            target_areas = " ".join(target.get("research_areas", [])).lower()
            cand_areas = " ".join(p.get("research_areas", [])).lower()
            t_words = set(target_areas.replace(",", "").split())
            c_words = set(cand_areas.replace(",", "").split())
            common = t_words & c_words
            if common:
                alternatives.append({
                    "name": p["name"],
                    "department": p["department"],
                    "research_areas": p.get("research_areas", []),
                    "current_projects": p_current,
                    "max_projects": p_max,
                    "load_ratio": round(p_current / max(p_max, 1), 2),
                    "overlap_words": sorted(common),
                })

        alternatives.sort(key=lambda x: (
            len(x["overlap_words"]),
            -x["load_ratio"],
        ), reverse=True)

    return {
        "target_name": target["name"],
        "found": True,
        "department": target.get("department", ""),
        "current_projects": current,
        "max_projects": max_p,
        "load_ratio": round(load_ratio, 2),
        "status": status,
        "at_capacity": at_capacity,
        "need_alternative": at_capacity or load_ratio >= 0.8,
        "alternatives": alternatives[:5],
    }


def format_workload_result(
    result: dict,
    iteration_count: int = 0,
    mode: str = "STUDENT",
) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append(f"[NODE: WORKLOAD_CHECKER] [MODE: {mode}] [ITER: {iteration_count}]")
    lines.append("-" * 72)

    if not result["found"]:
        lines.append(result["message"])
        lines.append("=" * 72)
        return "\n".join(lines)

    lines.append(f"Faculty: {result['target_name']}")
    lines.append(f"Department: {result['department']}")
    lines.append("-" * 40)
    lines.append(
        f"Project Load: {result['current_projects']}/{result['max_projects']}"
    )
    lines.append(f"Status: {result['status']}")

    if result["at_capacity"]:
        lines.append(
            f"WARNING: {result['target_name']} is at maximum capacity "
            f"({result['max_projects']}/{result['max_projects']}) and cannot "
            f"take on new projects."
        )
    elif result["load_ratio"] >= 0.8:
        lines.append(
            f"NOTE: {result['target_name']} is nearly at capacity. "
            f"New projects may face resource constraints."
        )

    if result["need_alternative"] and result["alternatives"]:
        lines.append("-" * 40)
        lines.append("LESS-LOADED ALTERNATIVES IN RELATED AREAS:")
        for i, alt in enumerate(result["alternatives"], 1):
            areas = ", ".join(alt["research_areas"])
            lines.append(
                f"  {i}. {alt['name']} ({alt['department']}) — "
                f"Load: {alt['current_projects']}/{alt['max_projects']}"
            )
            lines.append(f"     Areas: {areas}")
            lines.append(
                f"     Overlap: {', '.join(alt['overlap_words'][:4])}"
            )
    elif result["need_alternative"] and not result["alternatives"]:
        lines.append("  No less-loaded alternatives found in related areas.")

    lines.append("=" * 72)
    return "\n".join(lines)


def workload_check(state: dict) -> dict:
    iteration = state.get("iteration_count", 0)
    mode = state.get("user_mode", "STUDENT")

    selected = state.get("selected_faculty") or state.get("shortlisted_faculty", [{}])[0]
    name = selected.get("name", state.get("user_query", ""))

    result = check_workload(name)

    return {
        "faculty_workload": {
            result.get("target_name", ""): f"{result.get('current_projects', 0)}/{result.get('max_projects', 0)}"
        },
        "session_stage": "AFTER_WORKLOAD_CHECK",
        "last_node": "WORKLOAD_CHECKER",
        "_workload_result": result,
    }


if __name__ == "__main__":
    tests = [
        "Kavita Iyer",
        "Arjun Mehta",
        "Tanya Mukherjee",
        "Neha Agarwal",
        "Priya Sharma",
    ]
    for name in tests:
        result = check_workload(name)
        print(format_workload_result(result))
        print()
