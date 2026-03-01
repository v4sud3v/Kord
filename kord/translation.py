"""
Translation module — Speech-to-text and Malayalam ↔ English translation.

Responsibilities:
  - Download audio from a Twilio media URL.
  - Transcribe Malayalam audio via Bhashini or OpenAI Whisper.
  - Translate transcribed Malayalam text to English for the LLM.

Swap the provider constant below to switch between backends.
"""

from __future__ import annotations

PROVIDER = "whisper"  # "whisper" | "bhashini"


def transcribe_audio(media_url: str, auth: tuple[str, str] | None = None) -> str:
    """
    Download audio from *media_url* (Twilio-hosted .ogg) and return
    the Malayalam transcription as plain text.

    *auth* is a (username, password) tuple used to authenticate the
    download request against Twilio's media API.

    TODO: implement Whisper / Bhashini call.
    """
    raise NotImplementedError("transcribe_audio is not yet implemented")


def translate_to_english(malayalam_text: str) -> str:
    """
    Translate Malayalam plain text to English using the configured provider.

    TODO: implement translation call.
    """
    raise NotImplementedError("translate_to_english is not yet implemented")


def translate_to_malayalam(english_text: str) -> str:
    """
    Translate an English string back to Malayalam so it can be sent to the user.

    TODO: implement translation call.
    """
    raise NotImplementedError("translate_to_malayalam is not yet implemented")
