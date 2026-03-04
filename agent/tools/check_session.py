"""Tool: Check session state and build deterministic reply.

Merges a Groq extraction into the student's session and decides
what to ask next (or declares all keys collected).
"""

from services.conversation import get_session


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


def build_reply(missing: list[str]) -> str:
    """Pick a deterministic reply based on what's still missing."""
    if not missing:
        return ALL_COLLECTED_TEMPLATE
    # Ask for the first missing key (one question at a time)
    return TEMPLATES.get(missing[0], f"Could you tell me your {missing[0]}?")


def check_session(phone: str, buckets: dict) -> dict:
    """
    Merge extraction into session, build reply, return full state.

    This is the deterministic post-AI step: no LLM calls, just
    Python merging dicts and picking a template.
    """
    session = get_session(phone)
    session.merge(buckets)

    reply = build_reply(session.bucket_3_missing)

    if session.all_keys_collected:
        print(f"\n✅ All keys collected for {phone}!")
        print(f"   Keys:  {session.bucket_1_keys}")
        print(f"   Bonus: {session.bucket_2_bonus}")
        print(f"   → Ready to query scholarship database.\n")
    else:
        print(f"\n⏳ Missing for {phone}: {session.bucket_3_missing}")
        print(f"   → Asking: {reply}\n")

    return {
        "status": "ok",
        "reply": reply,
        "bucket_1_keys": dict(session.bucket_1_keys),
        "bucket_2_bonus": list(session.bucket_2_bonus),
        "bucket_3_missing": list(session.bucket_3_missing),
        "all_keys_collected": session.all_keys_collected,
    }
