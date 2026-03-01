from fastapi import APIRouter, Form
from typing import Optional

from app.services import fetch_twilio_audio, translate_audio

router = APIRouter()


def handle_incoming_message(body: str, from_number: str) -> dict:
    """Process an incoming WhatsApp text message and return a response payload."""
    print(f"Message from {from_number}: {body}")
    return {"status": "ok"}


async def handle_audio_message(
    media_url: str, content_type: str, from_number: str
) -> dict:
    """
    Fetch audio from Twilio, send it to Sarvam for translation,
    and print the result. No file is saved to disk.
    """
    print(f"Audio message from {from_number} — fetching from Twilio...")
    audio_bytes, actual_ct = await fetch_twilio_audio(media_url)
    # prefer the content-type Twilio declared in the form field
    ct = content_type or actual_ct

    print(f"Sending {len(audio_bytes)} bytes ({ct}) to Sarvam for translation...")
    result = await translate_audio(audio_bytes, ct)

    transcript = result.get("transcript", "")
    language = result.get("language_code", "")

    print(f"[Sarvam] Transcript    : {transcript}")
    print(f"[Sarvam] Language code : {language}")

    return {
        "status": "ok",
        "transcript": transcript,
        "language_code": language,
    }


@router.post("/webhook")
async def webhook(
    Body: str = Form(""),
    From: str = Form(...),
    NumMedia: int = Form(0),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
):
    # If the message contains audio media, translate it
    if NumMedia > 0 and MediaUrl0:
        return await handle_audio_message(
            media_url=MediaUrl0,
            content_type=MediaContentType0 or "",
            from_number=From,
        )

    # Otherwise treat it as a plain text message
    return handle_incoming_message(body=Body, from_number=From)
