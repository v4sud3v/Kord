"""Webhook router — the entire Kord logic in one clean flow.

Flow:
  1. Twilio POSTs audio/text to /webhook
  2. If audio → Sarvam translates it to English text
  3. Text → Groq sorts it into 3 buckets (JSON)   ← AI stops here
  4. Python merges buckets into the student's session
  5. Python checks bucket_3_missing:
       NOT EMPTY → pick a hardcoded template, ask for what's missing
       EMPTY     → all keys collected, ready to search scholarships
"""

from typing import Optional

from fastapi import APIRouter, Form

from services.twilio import fetch_twilio_audio
from services.sarvam import translate_audio
from services.groq_llm import extract_buckets
from services.conversation import get_session

router = APIRouter()


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


def _build_reply(missing: list[str]) -> str:
    """Pick a deterministic reply based on what's still missing."""
    if not missing:
        return ALL_COLLECTED_TEMPLATE
    # Ask for the first missing key (one question at a time)
    return TEMPLATES.get(missing[0], f"Could you tell me your {missing[0]}?")


# ── Handlers ──────────────────────────────────────────────────────────────

async def handle_text_message(text: str, from_number: str) -> dict:
    """Process a plain text WhatsApp message through the bucket pipeline."""
    print(f"[text] {from_number}: {text}")
    return await _run_bucket_pipeline(text, from_number)


async def handle_audio_message(
    media_url: str, content_type: str, from_number: str
) -> dict:
    """Fetch audio → Sarvam translation → bucket pipeline."""
    # Step 1: Fetch audio from Twilio
    print(f"[audio] {from_number} — fetching from Twilio...")
    audio_bytes, actual_ct = await fetch_twilio_audio(media_url)
    ct = content_type or actual_ct

    # Step 2: Sarvam translates audio → English text
    print(f"[audio] Sending {len(audio_bytes)} bytes ({ct}) to Sarvam...")
    sarvam_result = await translate_audio(audio_bytes, ct)

    transcript = sarvam_result.get("transcript", "")
    language = sarvam_result.get("language_code", "")
    print(f"[sarvam] transcript: {transcript}")
    print(f"[sarvam] language:   {language}")

    # Step 3-5: Bucket pipeline
    result = await _run_bucket_pipeline(transcript, from_number)
    result["transcript"] = transcript
    result["language_code"] = language
    return result


async def _run_bucket_pipeline(text: str, phone: str) -> dict:
    """
    Core logic — the 3 clean steps after translation:

    Step 3: Groq sorts text → 3 buckets (AI done, shuts off)
    Step 4: Python merges into session
    Step 5: Python checks bucket_3_missing → deterministic reply
    """
    # Step 3 — Groq extraction (the ONLY AI call)
    buckets = await extract_buckets(text)
    _print_buckets(buckets)

    # Step 4 — merge into this student's session
    session = get_session(phone)
    session.merge(buckets)

    # Step 5 — deterministic decision
    reply = _build_reply(session.bucket_3_missing)

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


def _print_buckets(buckets: dict) -> None:
    """Pretty-print a single Groq extraction."""
    print("\n" + "-" * 50)
    print("  GROQ EXTRACTION")
    print("-" * 50)
    for k, v in buckets.get("bucket_1_keys", {}).items():
        tag = f"✅ {v}" if v else "— null"
        print(f"  {k:>6}: {tag}")
    bonus = buckets.get("bucket_2_bonus", [])
    print(f"  bonus:  {bonus if bonus else '[]'}")
    missing = buckets.get("bucket_3_missing", [])
    print(f"  missing: {missing if missing else '[]'}")
    print("-" * 50)


# ── Route ─────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def webhook(
    Body: str = Form(""),
    From: str = Form(...),
    NumMedia: int = Form(0),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
):
    if NumMedia > 0 and MediaUrl0:
        return await handle_audio_message(
            media_url=MediaUrl0,
            content_type=MediaContentType0 or "",
            from_number=From,
        )
    return await handle_text_message(text=Body, from_number=From)
