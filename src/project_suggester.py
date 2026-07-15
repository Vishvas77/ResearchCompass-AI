import os
import sys

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from src.faculty_loader import load_faculty_profiles


def _llm_generate_suggestions(
    query: str,
    faculty: list[dict],
    gaps: list[dict],
) -> list[dict]:
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            import json
            llm = ChatOpenAI(api_key=openai_key, model="gpt-4.1-mini")
            faculty_summary = "\n".join(
                f"- {p['name']}: {', '.join(p.get('research_areas', []))}"
                for p in faculty[:5]
            )
            gap_summary = "\n".join(
                f"- {g.get('subtopic', 'unknown')}"
                for g in (gaps or [])[:3]
            ) or "no identified gaps"
            prompt = (
                f"Student query: \"{query}\"\n\n"
                f"Available faculty expertise:\n{faculty_summary}\n\n"
                f"Identified research gaps:\n{gap_summary}\n\n"
                f"Generate 3-5 project ideas that a student could work on. "
                f"Each project must be grounded in at least one faculty member's "
                f"actual research area or address an identified gap. "
                f"Return as JSON array with fields: "
                f"title, description, related_faculty (list of names), "
                f"required_skills (list), difficulty (Beginner/Intermediate/Advanced)."
            )
            resp = llm.invoke(prompt).content
            import re
            match = re.search(r"\[.*\]", resp, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass

    suggestions = []
    for i, prof in enumerate(faculty[:5]):
        areas = prof.get("research_areas", [])
        if not areas:
            continue
        primary = areas[0]
        title = f"Exploring {primary.capitalize()}: A Survey and Implementation Project"
        description = (
            f"Conduct a literature survey of recent advances in {primary}, "
            f"implement a baseline model or prototype, and evaluate on a "
            f"small dataset. This project builds foundational knowledge in "
            f"{prof['name']}'s research domain."
        )
        related = [prof["name"]]
        skills = ["Python", "literature review", "experimental design"]
        if "deep learning" in " ".join(areas).lower() or "machine learning" in " ".join(areas).lower():
            skills.extend(["PyTorch", "data preprocessing"])

        suggestions.append({
            "title": title,
            "description": description,
            "related_faculty": related,
            "required_skills": skills,
            "difficulty": "Intermediate",
        })

    if gaps:
        for gap in gaps[:2]:
            subtopic = gap.get("subtopic", "emerging area")
            suggestions.append({
                "title": f"Addressing the {subtopic.title()} Research Gap",
                "description": (
                    f"This project targets the identified gap in {subtopic} "
                    f"where {gap.get('paper_count', 'N')} recent papers indicate "
                    f"growing importance but {gap.get('faculty_count', 0)} faculty "
                    f"currently cover it. The student would survey the literature, "
                    f"identify the most promising approach, and prototype a solution."
                ),
                "related_faculty": gap.get("faculty_covering", []),
                "required_skills": ["Python", "literature review", "research methodology"],
                "difficulty": "Advanced",
            })

    return suggestions[:5]


def suggest_projects(
    query: str,
    faculty: list[dict] | None = None,
    gaps: list[dict] | None = None,
) -> list[dict]:
    if faculty is None or len(faculty) == 0:
        faculty = load_faculty_profiles()
    if gaps is None:
        gaps = []

    return _llm_generate_suggestions(query, faculty, gaps)


def format_project_suggestions(
    suggestions: list[dict],
    query: str,
    iteration_count: int = 0,
    mode: str = "STUDENT",
) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append(f"[NODE: PROJECT_SUGGESTER] [MODE: {mode}] [ITER: {iteration_count}]")
    lines.append("-" * 72)
    lines.append(f"Based on query: \"{query}\"")
    lines.append(f"Projects generated: {len(suggestions)}")
    lines.append("-" * 72)

    for i, proj in enumerate(suggestions, 1):
        title = proj.get("title", "Untitled")
        desc = proj.get("description", "")
        faculty_names = proj.get("related_faculty", [])
        skills = proj.get("required_skills", [])
        difficulty = proj.get("difficulty", "Unknown")

        lines.append(f"PROJECT {i}: {title}")
        lines.append("-" * 40)
        lines.append(f"  Difficulty: {difficulty}")
        lines.append(f"  Faculty: {', '.join(faculty_names)}")
        lines.append(f"  Skills: {', '.join(skills)}")
        lines.append(f"  Description: {desc}")
        lines.append("")

    lines.append("=" * 72)
    return "\n".join(lines)


def project_suggest(state: dict) -> dict:
    query = state.get("refined_query") or state.get("user_query", "")
    mode = state.get("user_mode", "STUDENT")
    iteration = state.get("iteration_count", 0)
    shortlisted = state.get("shortlisted_faculty", [])
    gaps = state.get("identified_gaps", [])

    if not shortlisted:
        profiles = load_faculty_profiles()
        suggestions = suggest_projects(query, profiles[:5], gaps)
    else:
        suggestions = suggest_projects(query, shortlisted, gaps)

    return {
        "project_suggestions": suggestions,
        "session_stage": "AFTER_PROJECTS",
        "last_node": "PROJECT_SUGGESTER",
        "_project_suggestions": suggestions,
    }


if __name__ == "__main__":
    profiles = load_faculty_profiles()
    nlp_faculty = [p for p in profiles if "NLP" in str(p.get("research_areas", []))]

    suggestions = suggest_projects("what project could I do on NLP", nlp_faculty, [])
    print(format_project_suggestions(suggestions, "what project could I do on NLP"))

    sample_gaps = [
        {
            "subtopic": "multimodal reasoning",
            "paper_count": 4,
            "total_papers": 10,
            "faculty_count": 0,
            "total_faculty": 15,
            "faculty_covering": [],
        },
    ]
    suggestions2 = suggest_projects(
        "what project could I do on AI",
        nlp_faculty + profiles[:1],
        sample_gaps,
    )
    print(format_project_suggestions(suggestions2, "what project could I do on AI"))
