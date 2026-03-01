import os
import httpx

from sarvamai import AsyncSarvamAI


def get_sarvam_api_key() -> str:
    key = os.getenv("SARVAM_API_KEY", "")
    if not key:
        raise RuntimeError("SARVAM_API_KEY environment variable is not set")
    return key


def get_twilio_credentials() -> tuple[str, str]:
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if not sid or not token:
        raise RuntimeError(
            "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables must be set"
        )
    return sid, token


async def fetch_twilio_audio(media_url: str) -> tuple[bytes, str]:
    """
    Stream audio bytes from a Twilio media URL without saving to disk.
    Authenticates with Twilio HTTP Basic Auth.
    Returns (audio_bytes, content_type).
    """
    sid, token = get_twilio_credentials()
    async with httpx.AsyncClient(auth=(sid, token), follow_redirects=True) as client:
        resp = await client.get(media_url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "audio/ogg")
        return resp.content, content_type


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
