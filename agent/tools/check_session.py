"""Tool: Check session state and build deterministic reply.

Merges a Groq extraction into the student's session and decides
what to ask next (or declares all keys collected and matches scholarships).
"""

from services.conversation import get_session
from agent.tools.match_scholarships import match_scholarships


# ── Hardcoded reply templates (deterministic, no AI tokens wasted) ────────

TEMPLATES = {
    "grade": (
        "Got it! Just to find the perfect scheme — "
        "what class/standard are you currently studying in?"
    ),
    "caste": (
        "Thanks! One more thing — what is your caste category? "
        "(like SC, ST, OBC, General, EWS)"
    ),
    "income": (
        "Almost there! Could you tell me your family's "
        "approximate yearly income?"
    ),
}

ALL_COLLECTED_TEMPLATE = (
    "I have everything I need! Searching for scholarships that match "
    "your profile now..."
)


def build_reply(missing: list[str], match_count: int = 0) -> str:
    """Pick a deterministic reply based on what's still missing."""
    if not missing:
        if match_count > 0:
            return (
                f"Great news! I found {match_count} scholarship(s) that match "
                f"your profile. Here are your results:"
            )
        return (
            "I have everything I need but couldn't find matching scholarships "
            "right now. The database may still be loading — please try again shortly."
        )
    # Ask for the first missing key (one question at a time)
    return TEMPLATES.get(missing[0], f"Could you tell me your {missing[0]}?")


def check_session(phone: str, buckets: dict) -> dict:
    """
    Merge extraction into session, build reply, return full state.

    This is the deterministic post-AI step: no LLM calls, just
    Python merging dicts and picking a template.
    When all keys are collected, queries the scholarship database.
    """
    session = get_session(phone)
    session.merge(buckets)

    matched = []

    if session.all_keys_collected:
        print(f"\n✅ All keys collected for {phone}!")
        print(f"   Keys:  {session.bucket_1_keys}")
        print(f"   Bonus: {session.bucket_2_bonus}")
        print(f"   → Querying scholarship database...\n")

        try:
            matched = match_scholarships(
                bucket_1_keys=dict(session.bucket_1_keys),
                bucket_2_bonus=list(session.bucket_2_bonus),
            )
        except Exception as e:
            print(f"   ⚠ Scholarship matching failed: {e}")
            matched = []
    else:
        print(f"\n⏳ Missing for {phone}: {session.bucket_3_missing}")

    reply = build_reply(session.bucket_3_missing, len(matched))

    if not session.all_keys_collected:
        print(f"   → Asking: {reply}\n")

    return {
        "status": "ok",
        "reply": reply,
        "bucket_1_keys": dict(session.bucket_1_keys),
        "bucket_2_bonus": list(session.bucket_2_bonus),
        "bucket_3_missing": list(session.bucket_3_missing),
        "all_keys_collected": session.all_keys_collected,
        "matched_scholarships": matched,
    }
