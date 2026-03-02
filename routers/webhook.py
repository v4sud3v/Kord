from typing import Optional

from fastapi import APIRouter, Form

from services.twilio import fetch_twilio_audio
from services.sarvam import translate_audio
from services.nlp import process_transcript, print_nlp_results

router = APIRouter()


def handle_incoming_message(body: str, from_number: str) -> dict:
    """Process an incoming WhatsApp text message and return a response payload."""
    print(f"Message from {from_number}: {body}")
    return {"status": "ok"}


async def handle_audio_message(media_url: str, content_type: str, from_number: str) -> dict:
    """
    Fetch audio from Twilio, send it to Sarvam for translation,
    run the NLP pipeline (tokenize → extract → embed), and print everything.
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

    # ── NLP Pipeline: tokenize → extract details → embed ──
    nlp_result = process_transcript(transcript)
    print_nlp_results(nlp_result)

    return {
        "status": "ok",
        "transcript": transcript,
        "language_code": language,
        "tokens": nlp_result["tokens"],
        "cleaned_tokens": nlp_result["cleaned_tokens"],
        "extracted_details": nlp_result["details"],
        "embedding_shape": list(nlp_result["embedding"].shape),
    }


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
    return handle_incoming_message(body=Body, from_number=From)
