"""Agent orchestrator — calls tools in sequence to process messages.

This is the agent's brain. It decides which tools to call and in what order.
The flow is:

  Audio path:  fetch_audio → translate_audio → extract_buckets → check_session
  Text path:   extract_buckets → check_session

Same logic as before, just reads like "the agent calling its tools."
"""

from agent.tools.fetch_audio import fetch_twilio_audio
from agent.tools.translate_audio import translate_audio
from agent.tools.extract_buckets import extract_buckets
from agent.tools.check_session import check_session


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


async def handle_text_message(text: str, from_number: str) -> dict:
    """Process a plain text WhatsApp message through the bucket pipeline."""
    print(f"[text] {from_number}: {text}")
    return await _run_bucket_pipeline(text, from_number)


async def handle_audio_message(
    media_url: str, content_type: str, from_number: str
) -> dict:
    """Fetch audio → Sarvam translation → bucket pipeline."""
    # Tool 1: Fetch audio from Twilio
    print(f"[audio] {from_number} — fetching from Twilio...")
    audio_bytes, actual_ct = await fetch_twilio_audio(media_url)
    ct = content_type or actual_ct

    # Tool 2: Sarvam translates audio → English text
    print(f"[audio] Sending {len(audio_bytes)} bytes ({ct}) to Sarvam...")
    sarvam_result = await translate_audio(audio_bytes, ct)

    transcript = sarvam_result.get("transcript", "")
    language = sarvam_result.get("language_code", "")
    print(f"[sarvam] transcript: {transcript}")
    print(f"[sarvam] language:   {language}")

    # Tools 3-4: Bucket pipeline
    result = await _run_bucket_pipeline(transcript, from_number)
    result["transcript"] = transcript
    result["language_code"] = language
    return result


async def _run_bucket_pipeline(text: str, phone: str) -> dict:
    """
    Core logic — the 2 tool calls after translation:

    Tool 3: Groq sorts text → 3 buckets (AI done, shuts off)
    Tool 4: Check session — merge + deterministic reply
    """
    # Tool 3 — Groq extraction (the ONLY AI call)
    buckets = await extract_buckets(text)
    _print_buckets(buckets)

    # Tool 4 — check session (merge + reply)
    return check_session(phone, buckets)
