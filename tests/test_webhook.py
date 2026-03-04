"""Tests for the webhook router and the agent pipeline logic."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient

from main import app
from agent.agent import (
    handle_text_message,
    handle_audio_message,
)
from agent.tools.check_session import (
    build_reply,
    TEMPLATES,
    ALL_COLLECTED_TEMPLATE,
)
from services.conversation import reset_session

client = TestClient(app)


# ── Helper: fake bucket result from Groq ──

def _fake_buckets(all_collected=False):
    if all_collected:
        return {
            "bucket_1_keys": {"grade": "12", "caste": "OBC", "income": 40000},
            "bucket_2_bonus": ["father is a fisherman"],
            "bucket_3_missing": [],
        }
    return {
        "bucket_1_keys": {"grade": "12", "caste": None, "income": 40000},
        "bucket_2_bonus": ["father is a fisherman"],
        "bucket_3_missing": ["caste"],
    }


# ────────────────────────────────────────────
# build_reply (pure Python, deterministic)
# ────────────────────────────────────────────

def test_build_reply_asks_for_first_missing():
    assert build_reply(["caste"]) == TEMPLATES["caste"]
    assert build_reply(["grade", "income"]) == TEMPLATES["grade"]


def test_build_reply_all_collected():
    assert build_reply([]) == ALL_COLLECTED_TEMPLATE


# ────────────────────────────────────────────
# Unit: text handler
# ────────────────────────────────────────────

@pytest.mark.asyncio
@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
async def test_handle_text_message(mock_extract, capsys):
    mock_extract.return_value = _fake_buckets(all_collected=False)
    result = await handle_text_message(text="I am in plus two", from_number="whatsapp:+111")
    assert result["status"] == "ok"
    assert result["bucket_3_missing"] == ["caste"]
    assert result["reply"] == TEMPLATES["caste"]


@pytest.mark.asyncio
@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
async def test_handle_text_all_keys(mock_extract, capsys):
    mock_extract.return_value = _fake_buckets(all_collected=True)
    result = await handle_text_message(text="OBC", from_number="whatsapp:+222")
    assert result["all_keys_collected"] is True
    assert result["reply"] == ALL_COLLECTED_TEMPLATE
    captured = capsys.readouterr()
    assert "All keys collected" in captured.out


# ────────────────────────────────────────────
# Unit: audio handler
# ────────────────────────────────────────────

@pytest.mark.asyncio
@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
@patch("agent.agent.translate_audio", new_callable=AsyncMock)
@patch("agent.agent.fetch_twilio_audio", new_callable=AsyncMock)
async def test_handle_audio_message(mock_fetch, mock_translate, mock_extract, capsys):
    mock_fetch.return_value = (b"fake-audio", "audio/ogg")
    mock_translate.return_value = {"transcript": "I study in plus two", "language_code": "ml-IN"}
    mock_extract.return_value = _fake_buckets(all_collected=False)

    result = await handle_audio_message(
        media_url="https://api.twilio.com/media/1",
        content_type="audio/ogg",
        from_number="whatsapp:+333",
    )
    assert result["status"] == "ok"
    assert result["transcript"] == "I study in plus two"
    assert result["language_code"] == "ml-IN"
    assert result["bucket_3_missing"] == ["caste"]

    mock_fetch.assert_awaited_once()
    mock_translate.assert_awaited_once()


# ────────────────────────────────────────────
# Integration: text route
# ────────────────────────────────────────────

@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
def test_webhook_text_route(mock_extract):
    mock_extract.return_value = _fake_buckets(all_collected=False)
    resp = client.post("/webhook", data={"Body": "Hello", "From": "whatsapp:+444"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "reply" in data


def test_webhook_missing_from_field():
    resp = client.post("/webhook", data={})
    assert resp.status_code == 422


# ────────────────────────────────────────────
# Integration: audio route
# ────────────────────────────────────────────

@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
@patch("agent.agent.translate_audio", new_callable=AsyncMock)
@patch("agent.agent.fetch_twilio_audio", new_callable=AsyncMock)
def test_webhook_audio_route(mock_fetch, mock_translate, mock_extract):
    mock_fetch.return_value = (b"audio", "audio/ogg")
    mock_translate.return_value = {"transcript": "hi", "language_code": "en"}
    mock_extract.return_value = _fake_buckets(all_collected=True)

    resp = client.post(
        "/webhook",
        data={
            "Body": "",
            "From": "whatsapp:+555",
            "NumMedia": "1",
            "MediaUrl0": "https://api.twilio.com/media/99",
            "MediaContentType0": "audio/ogg",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["transcript"] == "hi"
    assert data["all_keys_collected"] is True


@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
def test_webhook_text_when_no_media(mock_extract):
    mock_extract.return_value = _fake_buckets(all_collected=False)
    resp = client.post(
        "/webhook",
        data={"Body": "just text", "From": "whatsapp:+666", "NumMedia": "0"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ────────────────────────────────────────────
# build_reply — fallback for unknown key
# ────────────────────────────────────────────

def test_build_reply_fallback_for_unknown_key():
    """A missing key not in TEMPLATES should get a generic prompt."""
    reply = build_reply(["district"])
    assert reply == "Could you tell me your district?"


def test_build_reply_order_matters():
    """Should ask for the FIRST missing key only."""
    assert build_reply(["income", "caste"]) == TEMPLATES["income"]
    assert build_reply(["caste", "grade"]) == TEMPLATES["caste"]


# ────────────────────────────────────────────
# Multi-turn conversation (session accumulation)
# ────────────────────────────────────────────

@pytest.mark.asyncio
@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
async def test_multi_turn_conversation(mock_extract):
    """Simulate a real 3-message conversation, verify session accumulates."""
    phone = "whatsapp:+multi_turn_test"
    reset_session(phone)

    # Message 1: student provides grade and income
    mock_extract.return_value = {
        "bucket_1_keys": {"grade": "12", "caste": None, "income": 40000},
        "bucket_2_bonus": ["father is a fisherman"],
        "bucket_3_missing": ["caste"],
    }
    r1 = await handle_text_message("I am in plus two, father is fisherman, earns 40k", phone)
    assert r1["bucket_3_missing"] == ["caste"]
    assert r1["reply"] == TEMPLATES["caste"]
    assert r1["all_keys_collected"] is False

    # Message 2: student provides caste
    mock_extract.return_value = {
        "bucket_1_keys": {"grade": None, "caste": "OBC", "income": None},
        "bucket_2_bonus": [],
        "bucket_3_missing": [],
    }
    r2 = await handle_text_message("OBC", phone)
    assert r2["bucket_3_missing"] == []
    assert r2["all_keys_collected"] is True
    assert r2["reply"] == ALL_COLLECTED_TEMPLATE
    # Verify accumulated state from BOTH messages
    assert r2["bucket_1_keys"]["grade"] == "12"
    assert r2["bucket_1_keys"]["caste"] == "OBC"
    assert r2["bucket_1_keys"]["income"] == 40000
    assert "father is a fisherman" in r2["bucket_2_bonus"]

    reset_session(phone)


@pytest.mark.asyncio
@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
async def test_multi_turn_does_not_regress_keys(mock_extract):
    """A later message returning null for a key must NOT erase it."""
    phone = "whatsapp:+no_regress"
    reset_session(phone)

    # Message 1: grade=10
    mock_extract.return_value = {
        "bucket_1_keys": {"grade": "10", "caste": None, "income": None},
        "bucket_2_bonus": [],
        "bucket_3_missing": ["caste", "income"],
    }
    r1 = await handle_text_message("I'm in 10th standard", phone)
    assert r1["bucket_1_keys"]["grade"] == "10"

    # Message 2: caste=SC but grade=null (Groq didn't see grade this time)
    mock_extract.return_value = {
        "bucket_1_keys": {"grade": None, "caste": "SC", "income": None},
        "bucket_2_bonus": [],
        "bucket_3_missing": ["grade", "income"],
    }
    r2 = await handle_text_message("SC category", phone)
    # grade must NOT be overwritten to null
    assert r2["bucket_1_keys"]["grade"] == "10"
    assert r2["bucket_1_keys"]["caste"] == "SC"
    assert r2["bucket_3_missing"] == ["income"]

    reset_session(phone)


@pytest.mark.asyncio
@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
async def test_multi_turn_bpl_income_zero(mock_extract):
    """BPL income=0 should count as collected, not treated as missing."""
    phone = "whatsapp:+bpl_test"
    reset_session(phone)

    mock_extract.return_value = {
        "bucket_1_keys": {"grade": "8", "caste": "SC", "income": 0},
        "bucket_2_bonus": ["BPL family"],
        "bucket_3_missing": [],
    }
    result = await handle_text_message("I am BPL, 8th grade, SC", phone)
    assert result["all_keys_collected"] is True
    assert result["bucket_1_keys"]["income"] == 0
    assert result["reply"] == ALL_COLLECTED_TEMPLATE

    reset_session(phone)


# ────────────────────────────────────────────
# Audio handler edge cases
# ────────────────────────────────────────────

@pytest.mark.asyncio
@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
@patch("agent.agent.translate_audio", new_callable=AsyncMock)
@patch("agent.agent.fetch_twilio_audio", new_callable=AsyncMock)
async def test_audio_uses_actual_ct_when_content_type_empty(
    mock_fetch, mock_translate, mock_extract
):
    """When content_type param is empty, handler should fall back to Twilio's actual_ct."""
    mock_fetch.return_value = (b"audio", "audio/amr")
    mock_translate.return_value = {"transcript": "test", "language_code": "ml-IN"}
    mock_extract.return_value = _fake_buckets(all_collected=False)

    result = await handle_audio_message(
        media_url="https://api.twilio.com/media/1",
        content_type="",  # empty — should use actual_ct from Twilio
        from_number="whatsapp:+ct_fallback",
    )
    assert result["status"] == "ok"
    # Sarvam should have received "audio/amr" (the actual content type)
    mock_translate.assert_awaited_once_with(b"audio", "audio/amr")

    reset_session("whatsapp:+ct_fallback")


@pytest.mark.asyncio
@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
@patch("agent.agent.translate_audio", new_callable=AsyncMock)
@patch("agent.agent.fetch_twilio_audio", new_callable=AsyncMock)
async def test_audio_empty_transcript(mock_fetch, mock_translate, mock_extract):
    """If Sarvam returns empty transcript, pipeline should still work."""
    mock_fetch.return_value = (b"silent-audio", "audio/ogg")
    mock_translate.return_value = {"transcript": "", "language_code": ""}
    mock_extract.return_value = {
        "bucket_1_keys": {"grade": None, "caste": None, "income": None},
        "bucket_2_bonus": [],
        "bucket_3_missing": ["grade", "caste", "income"],
    }

    result = await handle_audio_message(
        media_url="https://api.twilio.com/media/silent",
        content_type="audio/ogg",
        from_number="whatsapp:+silent",
    )
    assert result["status"] == "ok"
    assert result["transcript"] == ""
    assert result["bucket_3_missing"] == ["grade", "caste", "income"]

    reset_session("whatsapp:+silent")


# ────────────────────────────────────────────
# Integration: edge cases
# ────────────────────────────────────────────

@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
def test_webhook_audio_with_no_media_url(mock_extract):
    """NumMedia=1 but no MediaUrl0 should fall back to text handler."""
    mock_extract.return_value = _fake_buckets(all_collected=False)
    resp = client.post(
        "/webhook",
        data={"Body": "fallback text", "From": "whatsapp:+777", "NumMedia": "1"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@patch("agent.agent.extract_buckets", new_callable=AsyncMock)
def test_webhook_empty_body(mock_extract):
    """Empty body text should still be accepted and processed."""
    mock_extract.return_value = {
        "bucket_1_keys": {"grade": None, "caste": None, "income": None},
        "bucket_2_bonus": [],
        "bucket_3_missing": ["grade", "caste", "income"],
    }
    resp = client.post("/webhook", data={"Body": "", "From": "whatsapp:+888"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["bucket_3_missing"] == ["grade", "caste", "income"]