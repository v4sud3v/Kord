"""Twilio audio fetching service."""

import os

import httpx


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
