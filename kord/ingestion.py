"""
Ingestion module — Twilio webhook parsing and session state management.

Responsibilities:
  - Parse incoming Twilio WhatsApp messages (text or audio).
  - Track user sessions by phone number in SQLite.
  - Return a normalised message dict for the rest of the pipeline.
"""

from __future__ import annotations

from typing import Any


# In-memory session store for early development.
# Replace with SQLite-backed store in Step 3.
_sessions: dict[str, dict[str, Any]] = {}


def parse_twilio_payload(form_data: dict[str, str]) -> dict[str, Any]:
    """
    Extract the fields Kord cares about from the raw Twilio form payload.

    Returns a dict with:
      - phone:      sender's WhatsApp number
      - body:       text body (empty string if voice note)
      - media_url:  URL of attached media (None if text-only)
      - media_type: MIME type of media  (None if text-only)
    """
    return {
        "phone": form_data.get("From", ""),
        "body": form_data.get("Body", ""),
        "media_url": form_data.get("MediaUrl0"),
        "media_type": form_data.get("MediaContentType0"),
    }


def get_session(phone: str) -> dict[str, Any]:
    """Return the current session for a user, creating a fresh one if needed."""
    if phone not in _sessions:
        _sessions[phone] = {
            "phone": phone,
            "profile": {"age": None, "grade": None, "caste": None, "income": None},
            "step": "collecting",
        }
    return _sessions[phone]


def save_session(phone: str, session: dict[str, Any]) -> None:
    """Persist session updates back to the store."""
    _sessions[phone] = session
