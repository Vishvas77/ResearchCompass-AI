import os
import sys

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)


VALID_ACTIONS = {"YES", "NO", "REFINE", "SHOW_ALTERNATE"}


def should_pause(state: dict) -> bool:
    stage = state.get("session_stage", "")
    pauseable_stages = {
        "AFTER_MATCH", "AFTER_MAP", "AFTER_DETAIL",
        "AFTER_ALTERNATE", "AFTER_PAPER_SEARCH",
        "AFTER_COLLAB_MATCH", "AFTER_PROJECTS",
    }
    return stage in pauseable_stages


def parse_user_feedback(user_reply: str) -> str:
    cleaned = user_reply.strip().upper()

    if cleaned in ("YES", "Y"):
        return "YES"
    if cleaned in ("NO", "N"):
        return "NO"
    if cleaned in ("REFINE", "RE", "R"):
        return "REFINE"
    for alt in ("SHOW_ALTERNATE", "SHOW ALTERNATE", "ALTERNATE", "ALT",
                 "ANOTHER", "NEXT", "MORE", "OTHER"):
        if cleaned == alt:
            return "SHOW_ALTERNATE"

    if "ALTERNATE" in cleaned or "ANOTHER" in cleaned:
        return "SHOW_ALTERNATE"
    if "REFINE" in cleaned:
        return "REFINE"

    return "UNRECOGNIZED"


def human_validate(state: dict, user_reply: str) -> dict:
    action = parse_user_feedback(user_reply)

    if action == "YES":
        return {
            "human_feedback": "YES",
            "session_stage": "VALIDATED",
            "last_node": "HUMAN_VALIDATOR",
        }

    if action == "NO":
        return {
            "human_feedback": "NO",
            "session_stage": "REJECTED",
            "last_node": "HUMAN_VALIDATOR",
        }

    if action == "REFINE":
        return {
            "human_feedback": "REFINE",
            "session_stage": "REFINE_MODE",
            "last_node": "HUMAN_VALIDATOR",
        }

    if action == "SHOW_ALTERNATE":
        shown = state.get("shown_faculty_ids", [])
        shortlisted = state.get("shortlisted_faculty", [])

        for candidate in shortlisted:
            if candidate["id"] not in shown:
                shown.append(candidate["id"])
                return {
                    "human_feedback": "SHOW_ALTERNATE",
                    "session_stage": "AFTER_ALTERNATE",
                    "shown_faculty_ids": shown,
                    "_alternate_faculty": candidate,
                    "last_node": "HUMAN_VALIDATOR",
                }

        return {
            "human_feedback": "SHOW_ALTERNATE",
            "session_stage": "ALL_SHOWN",
            "last_node": "HUMAN_VALIDATOR",
            "_alternate_message": "All faculty in this set have been shown.",
        }

    return {
        "human_feedback": f"UNRECOGNIZED: {user_reply}",
        "session_stage": "AWAIT_FEEDBACK",
        "last_node": "HUMAN_VALIDATOR",
        "_validator_message": (
            f"Unrecognized response: \"{user_reply}\". "
            f"Valid: YES, NO, REFINE, SHOW_ALTERNATE."
        ),
    }


def human_validator_node(state: dict) -> dict:
    user_reply = state.get("user_query", "")
    action = parse_user_feedback(user_reply)

    if action == "YES":
        return {
            "human_feedback": "YES",
            "session_stage": "VALIDATED",
            "last_node": "HUMAN_VALIDATOR",
        }

    if action == "NO":
        return {
            "human_feedback": "NO",
            "session_stage": "REJECTED",
            "last_node": "HUMAN_VALIDATOR",
        }

    if action == "REFINE":
        return {
            "human_feedback": "REFINE",
            "session_stage": "REFINE_MODE",
            "last_node": "HUMAN_VALIDATOR",
        }

    if action == "SHOW_ALTERNATE":
        shown = state.get("shown_faculty_ids", [])
        shortlisted = state.get("shortlisted_faculty", [])

        for candidate in shortlisted:
            if candidate["id"] not in shown:
                shown.append(candidate["id"])
                return {
                    "human_feedback": "SHOW_ALTERNATE",
                    "session_stage": "AFTER_ALTERNATE",
                    "shown_faculty_ids": shown,
                    "_alternate_faculty": candidate,
                    "last_node": "HUMAN_VALIDATOR",
                }

        return {
            "human_feedback": "SHOW_ALTERNATE",
            "session_stage": "ALL_SHOWN",
            "last_node": "HUMAN_VALIDATOR",
            "_alternate_message": "All faculty in this set have been shown.",
        }

    return {
        "human_feedback": f"UNRECOGNIZED: {user_reply}",
        "session_stage": "AWAIT_FEEDBACK",
        "last_node": "HUMAN_VALIDATOR",
        "_validator_message": (
            f"Unrecognized: \"{user_reply}\". "
            f"Options: YES, NO, REFINE, SHOW_ALTERNATE"
        ),
    }


if __name__ == "__main__":
    state = {"shown_faculty_ids": [], "shortlisted_faculty": [
        {"id": "prof_01", "name": "Dr. A", "department": "CSE", "research_areas": ["NLP"]},
        {"id": "prof_03", "name": "Dr. B", "department": "CSE", "research_areas": ["CV"]},
    ]}

    for reply in ["YES", "NO", "refine", "show another", "alt", "garbage"]:
        result = human_validate(state, reply)
        print(f"'{reply}' -> {result['session_stage']} ({result.get('human_feedback', '')})")
