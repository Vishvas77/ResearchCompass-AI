import os
import sys

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)


def can_send_email(state: dict, user_reply: str) -> bool:
    """
    HARD GATE — the single function controlling whether an email can be sent.

    email_sent may ONLY become True when ALL of these hold:
      1. state["pending_confirmation"] == True
         (set by email_generator.py, cleared on every new turn by main.py)
      2. user_reply.strip().upper() == "YES"
         (case-insensitive, must be the exact string "YES")

    NOTHING ELSE can flip email_sent to True.
    Not "send", not "maybe", not an empty draft, not session_stage.
    """
    return state.get("pending_confirmation", False) and user_reply.strip().upper() == "YES"


def approve_email(state: dict) -> dict:
    """
    Processes an email approval attempt.

    Returns email_sent = True ONLY if can_send_email() passes.
    All other paths set email_sent = False.
    """
    user_reply = state.get("user_query", "")
    email_draft = state.get("email_draft", "")
    pending = state.get("pending_confirmation", False)

    if not email_draft:
        return {
            "email_approved": False,
            "email_sent": False,
            "pending_confirmation": False,
            "session_stage": "NO_DRAFT",
            "last_node": "EMAIL_APPROVAL",
            "_email_message": (
                "No email draft exists. Use 'email' to generate one first."
            ),
        }

    if user_reply.strip().upper() in ("EDIT", "NO", "CANCEL"):
        return {
            "email_approved": False,
            "email_sent": False,
            "pending_confirmation": False,
            "session_stage": "EMAIL_CANCELLED",
            "last_node": "EMAIL_APPROVAL",
        }

    if can_send_email(state, user_reply):
        return {
            "email_approved": True,
            "email_sent": True,
            "pending_confirmation": False,
            "session_stage": "EMAIL_SENT",
            "last_node": "EMAIL_APPROVAL",
        }

    return {
        "email_approved": False,
        "email_sent": False,
        "pending_confirmation": False,
        "session_stage": "EMAIL_NOT_SENT",
        "last_node": "EMAIL_APPROVAL",
        "_email_message": (
            f"Email NOT sent. The hard gate requires both "
            f"pending_confirmation=True AND user_reply=='YES'. "
            f"Got pending_confirmation={pending}, user_reply='{user_reply}'."
        ),
    }


def email_approval_node(state: dict) -> dict:
    return approve_email(state)


if __name__ == "__main__":
    def test(name, state, reply):
        state["user_query"] = reply
        result = approve_email(state)
        sent = result["email_sent"]
        status = "PASS" if (not sent) == should_fail else "FAIL"
        print(f"[{status}] {name}: email_sent={sent} (should_be={not should_fail})")

    # Test 1: pending=True + YES = sent
    should_fail = False
    test("Valid YES",
         {"pending_confirmation": True, "email_draft": "Draft here", "user_query": ""},
         "YES")

    # Test 2: pending=False + YES = NOT sent
    should_fail = True
    test("No pending, YES",
         {"pending_confirmation": False, "email_draft": "Draft here", "user_query": ""},
         "YES")

    # Test 3: pending=True + "send" = NOT sent (not "YES")
    should_fail = True
    test("Pending, 'send' instead of YES",
         {"pending_confirmation": True, "email_draft": "Draft here", "user_query": ""},
         "send")

    # Test 4: pending=True + "maybe" = NOT sent
    should_fail = True
    test("Pending, 'maybe'",
         {"pending_confirmation": True, "email_draft": "Draft here", "user_query": ""},
         "maybe")

    # Test 5: pending=True + no draft = NOT sent
    should_fail = True
    test("Pending, no draft",
         {"pending_confirmation": True, "email_draft": "", "user_query": ""},
         "YES")

    # Test 6: pending=True + "yes" lowercase = sent
    should_fail = False
    test("Valid 'yes' lowercase",
         {"pending_confirmation": True, "email_draft": "Draft here", "user_query": ""},
         "yes")

    # Test 7: pending=True + " YES " (extra spaces) = sent
    should_fail = False
    test("Valid 'YES' with spaces",
         {"pending_confirmation": True, "email_draft": "Draft here", "user_query": ""},
         " YES ")

    # Test 8: pending=True + "NO" = NOT sent
    should_fail = True
    test("Pending, explicit NO",
         {"pending_confirmation": True, "email_draft": "Draft here", "user_query": ""},
         "NO")
