import os
import sys

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)


def generate_email(state: dict) -> dict:
    """
    Generates a mode-specific email draft for the selected faculty member.
    Sets pending_confirmation = True as a prerequisite for sending.

    Student mode: research interest / seeking guidance
    Professor mode: collaboration opportunity / joint research proposal
    """
    mode = state.get("user_mode", "STUDENT")
    selected = state.get("selected_faculty", {})
    query = state.get("user_query", "")

    if not selected:
        return {
            "session_stage": "NO_FACULTY_SELECTED",
            "last_node": "EMAIL_GENERATOR",
            "_email_message": "Select a faculty member first (e.g., 'select 1').",
        }

    faculty_name = selected.get("name", "Faculty Member")
    faculty_area = ", ".join(selected.get("research_areas", []))
    faculty_email = selected.get("email", "")

    if mode == "STUDENT":
        subject = f"Research Interest: {query[:50]}"
        draft = (
            f"Subject: {subject}\n"
            f"To: {faculty_email}\n\n"
            f"Dear {faculty_name},\n\n"
            f"I have been following your research in {faculty_area} "
            f"with great interest. I would be grateful for the opportunity "
            f"to discuss potential research guidance under your supervision.\n\n"
            f"I am available to meet at your convenience to discuss this further.\n\n"
            f"Thank you for your consideration.\n\n"
            f"Best regards,\n"
            f"[Student Name]"
        )
    else:
        subject = f"Collaboration Opportunity: {faculty_area}"
        draft = (
            f"Subject: {subject}\n"
            f"To: {faculty_email}\n\n"
            f"Dear {faculty_name},\n\n"
            f"Your work in {faculty_area} aligns well with complementary "
            f"research directions in my group. Given recent developments "
            f"in this area, I believe a joint research initiative would "
            f"benefit both our teams.\n\n"
            f"I would like to propose a meeting to discuss a potential "
            f"collaboration — possibly a joint paper, grant proposal, "
            f"or shared student supervision.\n\n"
            f"Would you be available for a brief discussion next week?\n\n"
            f"Best regards,\n"
            f"[Professor Name]"
        )

    return {
        "email_draft": draft,
        "pending_confirmation": True,
        "session_stage": "AWAITING_EMAIL_CONFIRMATION",
        "last_node": "EMAIL_GENERATOR",
    }


def email_generator_node(state: dict) -> dict:
    return generate_email(state)
