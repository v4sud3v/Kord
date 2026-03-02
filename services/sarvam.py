"""Sarvam AI speech-to-text + translation service."""

import os

from sarvamai import AsyncSarvamAI


def get_sarvam_api_key() -> str:
    key = os.getenv("SARVAM_API_KEY", "")
    if not key:
        raise RuntimeError("SARVAM_API_KEY environment variable is not set")
    return key


def _codec_from_content_type(content_type: str) -> str:
    """Map common audio MIME types to Sarvam SDK codec strings."""
    mapping = {
        "audio/ogg": "ogg",
        "audio/opus": "opus",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/mp4": "mp4",
        "audio/wav": "wav",
        "audio/x-wav": "x-wav",
        "audio/amr": "amr",
        "audio/flac": "flac",
        "audio/webm": "webm",
        "audio/aac": "aac",
    }
    mime = content_type.split(";")[0].strip().lower()
    return mapping.get(mime, "ogg")


async def translate_audio(audio_bytes: bytes, content_type: str) -> dict:
    """
    Send audio bytes to Sarvam speech-to-text-translate API via the SDK.
    Returns a dict with transcript, language_code, etc.
    """
    api_key = get_sarvam_api_key()
    codec = _codec_from_content_type(content_type)

    client = AsyncSarvamAI(api_subscription_key=api_key)
    response = await client.speech_to_text.translate(
        file=("audio." + codec, audio_bytes, content_type),
        model="saaras:v2.5",
        input_audio_codec=codec,
    )

    return {
        "transcript": response.transcript,
        "language_code": response.language_code,
    }
