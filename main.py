"""
Kord — FastAPI entry point.

All routes live here. The actual work is delegated to the kord/ package:
  kord.ingestion   → parse Twilio payload, manage sessions
  kord.translation → audio transcription + Malayalam ↔ English translation
  kord.extraction  → LLM entity extraction (age, grade, caste, income)
  kord.matcher     → scholarship eligibility logic
  kord.output      → build reply text, generate PDF, send WhatsApp reply
"""

from __future__ import annotations

from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse

from kord import extraction, ingestion, matcher, output

app = FastAPI(title="Kord", version="0.1.0")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Main webhook — Twilio posts here on every incoming WhatsApp message
# ---------------------------------------------------------------------------


@app.post("/webhook", tags=["webhook"])
async def webhook(request: Request) -> PlainTextResponse:
    """
    Receive an incoming WhatsApp message from Twilio and return a TwiML reply.

    Flow (text-only path — voice wraps around this in Step 5):
      1. Parse the Twilio form payload.
      2. Load the user's session (create one if first contact).
      3. Extract profile fields from the message text via the LLM.
      4. Check whether all required fields are collected.
      5. If complete → run eligibility matcher and build success reply.
         If incomplete → ask for the next missing field.
      6. Persist the updated session and return the reply.
    """
    form = dict(await request.form())
    message = ingestion.parse_twilio_payload(form)

    phone = message["phone"]
    text = message["body"]

    # Step 2 — load session
    session = ingestion.get_session(phone)
    profile = session["profile"]

    # Step 3 — extract fields from the incoming text
    if text:
        updates = extraction.extract_profile_fields(text)
        profile = extraction.merge_profile(profile, updates)
        session["profile"] = profile

    # Step 4+5 — decide what to reply
    missing = extraction.missing_fields(profile)

    if missing:
        reply = output.build_reply_text(eligible=[], missing=missing)
    else:
        eligible = matcher.check_eligibility(profile)
        reply = output.build_reply_text(eligible=eligible, missing=[])

    # Step 6 — save and respond
    ingestion.save_session(phone, session)

    # Return plain text; Twilio accepts non-TwiML responses fine for testing.
    return PlainTextResponse(reply)

