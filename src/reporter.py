import os
import sys

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)


def generate_report(state: dict) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append("             ACADEMIMATCH — SESSION REPORT")
    lines.append("=" * 72)

    mode = state.get("user_mode", "STUDENT")
    iteration = state.get("iteration_count", 0)
    lines.append(f"Mode: {mode}")
    lines.append(f"Total turns: {iteration}")
    lines.append("-" * 72)

    selected = state.get("selected_faculty", {})
    if selected:
        lines.append("SELECTED FACULTY:")
        lines.append(f"  Name: {selected.get('name', 'N/A')}")
        lines.append(f"  Department: {selected.get('department', 'N/A')}")
        areas = ", ".join(selected.get("research_areas", []))
        lines.append(f"  Research Areas: {areas}")
        lines.append(f"  Email: {selected.get('email', 'N/A')}")
        score = selected.get("hybrid_pct", selected.get("collaboration_score", "N/A"))
        if isinstance(score, float):
            score = f"{score:.1f}%"
        lines.append(f"  Match Score: {score}")
        lines.append("-" * 72)
    else:
        shortlisted = state.get("shortlisted_faculty", [])
        if shortlisted:
            lines.append(f"SHORTLISTED FACULTY ({len(shortlisted)} candidates):")
            for i, f in enumerate(shortlisted[:5], 1):
                pct = f.get("hybrid_pct", "?")
                lines.append(
                    f"  {i}. {f.get('name', '?')} "
                    f"({f.get('department', '?')}) — {pct}%"
                )
            lines.append("-" * 72)

    papers = state.get("retrieved_papers", [])
    if papers:
        lines.append(f"RETRIEVED PAPERS: {len(papers)} found")
        sorted_papers = sorted(papers, key=lambda x: x.get("citations", 0), reverse=True)
        for i, p in enumerate(sorted_papers[:5], 1):
            lines.append(
                f"  {i}. {p.get('title', '?')} "
                f"({p.get('year', '?')}, {p.get('citations', 0)} citations)"
            )
        lines.append("-" * 72)

    gaps = state.get("identified_gaps", [])
    if gaps:
        lines.append(f"IDENTIFIED GAPS: {len(gaps)} found")
        for g in gaps[:5]:
            lines.append(
                f"  - {g.get('subtopic', '?')}: "
                f"{g.get('paper_count', 0)} papers, "
                f"{g.get('faculty_count', 0)} faculty covering"
            )
        lines.append("-" * 72)

    projects = state.get("project_suggestions", [])
    if projects:
        lines.append(f"PROJECT SUGGESTIONS: {len(projects)} generated")
        for i, p in enumerate(projects[:5], 1):
            lines.append(f"  {i}. {p.get('title', '?')} [{p.get('difficulty', '?')}]")
        lines.append("-" * 72)

    email_status = "NOT SENT"
    if state.get("email_sent"):
        email_status = "SENT [SIMULATED]"
    elif state.get("email_draft"):
        email_status = "DRAFT GENERATED (not sent)"
    lines.append(f"EMAIL STATUS: {email_status}")

    collab_score = state.get("collaboration_score", 0.0)
    if collab_score > 0:
        lines.append(f"COLLABORATION SCORE: {collab_score:.4f}")

    workload = state.get("faculty_workload", {})
    if workload:
        lines.append("FACULTY WORKLOAD:")
        for name, load in list(workload.items())[:5]:
            lines.append(f"  - {name}: {load}")

    shown_count = len(state.get("shown_faculty_ids", []))
    if shown_count > 0:
        lines.append(f"FACULTY PROFILES VIEWED: {shown_count}")

    lines.append("=" * 72)
    return "\n".join(lines)


def reporter_node(state: dict) -> dict:
    report = generate_report(state)
    return {
        "session_stage": "AFTER_REPORT",
        "last_node": "REPORTER",
        "_report": report,
    }


if __name__ == "__main__":
    sample_state = {
        "user_mode": "STUDENT",
        "iteration_count": 8,
        "selected_faculty": {
            "name": "Dr. Priya Sharma",
            "department": "CSE",
            "research_areas": ["NLP", "LLMs"],
            "email": "priya.sharma@university.edu",
            "hybrid_pct": 68.7,
        },
        "shortlisted_faculty": [
            {"name": "Dr. Priya Sharma", "department": "CSE", "hybrid_pct": 68.7},
            {"name": "Dr. Meera Kapoor", "department": "CSE", "hybrid_pct": 25.3},
        ],
        "retrieved_papers": [
            {"title": "Attention Is All You Need", "year": 2017, "citations": 135000},
            {"title": "GPT-3: Language Models are Few-Shot Learners", "year": 2020, "citations": 22000},
        ],
        "identified_gaps": [
            {"subtopic": "multimodal reasoning", "paper_count": 4, "faculty_count": 0},
        ],
        "project_suggestions": [
            {"title": "NLP Survey Project", "difficulty": "Intermediate"},
        ],
        "email_draft": "Subject: Research Interest...",
        "email_sent": True,
        "collaboration_score": 0.454,
        "faculty_workload": {"Dr. Priya Sharma": "3/6"},
        "shown_faculty_ids": ["prof_01", "prof_02"],
    }
    print(generate_report(sample_state))
