import pytest

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app
from app.routes.webhook import handle_incoming_message, handle_audio_message

client = TestClient(app)

# ────────────────────────────────────────────
# Unit tests: text handler
# ────────────────────────────────────────────

def test_handle_incoming_message_returns_ok(capsys):
    result = handle_incoming_message(body="Hey", from_number="whatsapp:+9999999999")
    assert result == {"status": "ok"}
    captured = capsys.readouterr()
    assert "whatsapp:+9999999999" in captured.out
    assert "Hey" in captured.out


# ────────────────────────────────────────────
# Unit tests: audio handler
# ────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.routes.webhook.translate_audio", new_callable=AsyncMock)
@patch("app.routes.webhook.fetch_twilio_audio", new_callable=AsyncMock)
async def test_handle_audio_message_returns_translation(mock_fetch, mock_translate, capsys):
    mock_fetch.return_value = (b"fake-audio-bytes", "audio/ogg")
    mock_translate.return_value = {
        "transcript": "namaste",
        "language_code": "hi-IN",
    }

    result = await handle_audio_message(
        media_url="https://api.twilio.com/media/123",
        content_type="audio/ogg",
        from_number="whatsapp:+9999999999",
    )

    assert result["status"] == "ok"
    assert result["transcript"] == "namaste"
    assert result["language_code"] == "hi-IN"

    mock_fetch.assert_awaited_once_with("https://api.twilio.com/media/123")
    mock_translate.assert_awaited_once()

    captured = capsys.readouterr()
    assert "[Sarvam] Transcript" in captured.out
    assert "namaste" in captured.out


# ────────────────────────────────────────────
# Integration tests: text route
# ────────────────────────────────────────────

def test_webhook_route_returns_ok():
    response = client.post(
        "/webhook",
        data={"Body": "Hello", "From": "whatsapp:+9999999999"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_route_missing_fields():
    response = client.post("/webhook", data={})
    assert response.status_code == 422


# ────────────────────────────────────────────
# Integration tests: audio route
# ────────────────────────────────────────────

@patch("app.routes.webhook.translate_audio", new_callable=AsyncMock)
@patch("app.routes.webhook.fetch_twilio_audio", new_callable=AsyncMock)
def test_webhook_audio_route(mock_fetch, mock_translate):
    mock_fetch.return_value = (b"fake-audio", "audio/ogg")
    mock_translate.return_value = {
        "transcript": "hola",
        "language_code": "es",
    }

    response = client.post(
        "/webhook",
        data={
            "Body": "",
            "From": "whatsapp:+9999999999",
            "NumMedia": "1",
            "MediaUrl0": "https://api.twilio.com/media/456",
            "MediaContentType0": "audio/ogg",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["transcript"] == "hola"
    assert data["language_code"] == "es"


@patch("app.routes.webhook.translate_audio", new_callable=AsyncMock)
@patch("app.routes.webhook.fetch_twilio_audio", new_callable=AsyncMock)
def test_webhook_text_when_no_media(mock_fetch, mock_translate):
    """When NumMedia=0, the text handler is used even if MediaUrl0 is absent."""
    response = client.post(
        "/webhook",
        data={
            "Body": "just text",
            "From": "whatsapp:+9999999999",
            "NumMedia": "0",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_fetch.assert_not_awaited()
    mock_translate.assert_not_awaited()

