"""Tests for app/services (Sarvam + Twilio audio helpers)."""

import os
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from services.sarvam import get_sarvam_api_key, translate_audio, _codec_from_content_type
from services.twilio import get_twilio_credentials, fetch_twilio_audio


# ────────────────────────────────────────────
# get_sarvam_api_key
# ────────────────────────────────────────────

def test_get_sarvam_api_key_returns_key(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-key-123")
    assert get_sarvam_api_key() == "test-key-123"


def test_get_sarvam_api_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SARVAM_API_KEY"):
        get_sarvam_api_key()


# ────────────────────────────────────────────
# get_twilio_credentials
# ────────────────────────────────────────────

def test_get_twilio_credentials_returns_tuple(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACxxx")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok123")
    assert get_twilio_credentials() == ("ACxxx", "tok123")


def test_get_twilio_credentials_raises_when_missing(monkeypatch):
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="TWILIO_ACCOUNT_SID"):
        get_twilio_credentials()


# ────────────────────────────────────────────
# _codec_from_content_type
# ────────────────────────────────────────────

@pytest.mark.parametrize(
    "ct, expected",
    [
        ("audio/ogg", "ogg"),
        ("audio/ogg; codecs=opus", "ogg"),
        ("audio/mpeg", "mp3"),
        ("audio/wav", "wav"),
        ("audio/amr", "amr"),
        ("audio/mp4", "mp4"),
        ("audio/x-wav", "x-wav"),
        ("video/mp4", "ogg"),  # unknown → fallback
    ],
)
def test_codec_from_content_type(ct, expected):
    assert _codec_from_content_type(ct) == expected


# ────────────────────────────────────────────
# fetch_twilio_audio
# ────────────────────────────────────────────

@pytest.mark.asyncio
@patch("services.twilio.httpx.AsyncClient")
async def test_fetch_twilio_audio(MockClient, monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACxxx")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok123")

    mock_resp = MagicMock()
    mock_resp.content = b"audio-bytes"
    mock_resp.headers = {"content-type": "audio/ogg"}
    mock_resp.raise_for_status = MagicMock()

    instance = AsyncMock()
    instance.get.return_value = mock_resp
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=False)
    MockClient.return_value = instance

    audio, ct = await fetch_twilio_audio("https://api.twilio.com/media/123")
    assert audio == b"audio-bytes"
    assert ct == "audio/ogg"
    instance.get.assert_awaited_once_with("https://api.twilio.com/media/123")
    # Verify auth credentials were passed
    MockClient.assert_called_once_with(auth=("ACxxx", "tok123"), follow_redirects=True)


# ────────────────────────────────────────────
# translate_audio
# ────────────────────────────────────────────

@pytest.mark.asyncio
@patch("services.sarvam.AsyncSarvamAI")
async def test_translate_audio(MockSarvam, monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.transcript = "hola"
    mock_response.language_code = "es"

    mock_client = MagicMock()
    mock_client.speech_to_text.translate = AsyncMock(return_value=mock_response)
    MockSarvam.return_value = mock_client

    result = await translate_audio(b"fake-audio", "audio/ogg")
    assert result["transcript"] == "hola"
    assert result["language_code"] == "es"
    mock_client.speech_to_text.translate.assert_awaited_once()
