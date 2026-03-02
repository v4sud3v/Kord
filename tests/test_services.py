"""Tests for services: Sarvam, Twilio, Groq bucket extraction, Conversation."""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from services.sarvam import get_sarvam_api_key, translate_audio, _codec_from_content_type
from services.twilio import get_twilio_credentials, fetch_twilio_audio
from services.groq_llm import get_groq_api_key, extract_buckets, REQUIRED_KEYS
from services.conversation import Session, get_session, reset_session


# ────────────────────────────────────────────
# Sarvam
# ────────────────────────────────────────────

def test_get_sarvam_api_key_returns_key(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-key-123")
    assert get_sarvam_api_key() == "test-key-123"


def test_get_sarvam_api_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SARVAM_API_KEY"):
        get_sarvam_api_key()


@pytest.mark.asyncio
@patch("services.sarvam.AsyncSarvamAI")
async def test_translate_audio(MockSarvam, monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    mock_response = MagicMock()
    mock_response.transcript = "hello world"
    mock_response.language_code = "ml-IN"
    mock_client = MagicMock()
    mock_client.speech_to_text.translate = AsyncMock(return_value=mock_response)
    MockSarvam.return_value = mock_client

    result = await translate_audio(b"fake-audio", "audio/ogg")
    assert result["transcript"] == "hello world"
    assert result["language_code"] == "ml-IN"


# ────────────────────────────────────────────
# Twilio
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
    MockClient.assert_called_once_with(auth=("ACxxx", "tok123"), follow_redirects=True)


# ────────────────────────────────────────────
# Groq — extract_buckets
# ────────────────────────────────────────────

def test_get_groq_api_key_returns_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    assert get_groq_api_key() == "gsk_test"


def test_get_groq_api_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        get_groq_api_key()


@pytest.mark.asyncio
@patch("services.groq_llm.AsyncGroq")
async def test_extract_buckets_parses_response(MockGroq, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    fake = json.dumps({
        "bucket_1_keys": {"grade": "12", "caste": None, "income": 40000},
        "bucket_2_bonus": ["father is a fisherman"],
        "bucket_3_missing": ["caste"],
    })

    mock_choice = MagicMock()
    mock_choice.message.content = fake
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    MockGroq.return_value = mock_client

    result = await extract_buckets("I am studying in plus two, father is fisherman, earns 40000")
    assert result["bucket_1_keys"]["grade"] == "12"
    assert result["bucket_1_keys"]["income"] == 40000
    assert result["bucket_1_keys"]["caste"] is None
    assert "father is a fisherman" in result["bucket_2_bonus"]
    assert result["bucket_3_missing"] == ["caste"]


@pytest.mark.asyncio
@patch("services.groq_llm.AsyncGroq")
async def test_extract_buckets_handles_bad_json(MockGroq, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    mock_choice = MagicMock()
    mock_choice.message.content = "not json"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    MockGroq.return_value = mock_client

    result = await extract_buckets("hello")
    assert result["bucket_1_keys"]["grade"] is None
    assert result["bucket_3_missing"] == list(REQUIRED_KEYS)


# ────────────────────────────────────────────
# Conversation Session
# ────────────────────────────────────────────

def test_session_merge_fills_keys():
    s = Session()
    s.merge({
        "bucket_1_keys": {"grade": "10", "caste": "OBC", "income": None},
        "bucket_2_bonus": ["disabled"],
    })
    assert s.bucket_1_keys["grade"] == "10"
    assert s.bucket_1_keys["caste"] == "OBC"
    assert s.bucket_1_keys["income"] is None
    assert "disabled" in s.bucket_2_bonus
    assert s.bucket_3_missing == ["income"]
    assert not s.all_keys_collected


def test_session_merge_does_not_overwrite_with_null():
    s = Session()
    s.merge({"bucket_1_keys": {"grade": "10", "caste": None, "income": None}})
    s.merge({"bucket_1_keys": {"grade": None, "caste": "SC", "income": None}})
    # grade should NOT be overwritten to null
    assert s.bucket_1_keys["grade"] == "10"
    assert s.bucket_1_keys["caste"] == "SC"


def test_session_deduplicates_bonus():
    s = Session()
    s.merge({"bucket_2_bonus": ["disabled"]})
    s.merge({"bucket_2_bonus": ["disabled", "girl child"]})
    assert s.bucket_2_bonus == ["disabled", "girl child"]


def test_session_all_keys_collected():
    s = Session()
    s.merge({
        "bucket_1_keys": {"grade": "12", "caste": "General", "income": 100000},
    })
    assert s.all_keys_collected is True
    assert s.bucket_3_missing == []


def test_get_and_reset_session():
    phone = "whatsapp:+test_reset"
    session = get_session(phone)
    session.merge({"bucket_1_keys": {"grade": "10", "caste": None, "income": None}})
    assert get_session(phone).bucket_1_keys["grade"] == "10"

    reset_session(phone)
    assert get_session(phone).bucket_1_keys["grade"] is None


def test_session_income_zero_is_valid():
    """BPL income normalised to 0 must NOT be treated as missing."""
    s = Session()
    s.merge({"bucket_1_keys": {"grade": "10", "caste": "SC", "income": 0}})
    assert s.bucket_1_keys["income"] == 0
    assert s.bucket_3_missing == []
    assert s.all_keys_collected is True


def test_session_merge_empty_extraction():
    """An empty extraction dict should not crash or clear existing data."""
    s = Session()
    s.merge({"bucket_1_keys": {"grade": "12", "caste": None, "income": None}})
    s.merge({})
    assert s.bucket_1_keys["grade"] == "12"
    assert s.bucket_3_missing == ["caste", "income"]


def test_session_merge_only_bonus():
    """Extracting only bonus details shouldn't affect core keys."""
    s = Session()
    s.merge({"bucket_2_bonus": ["single parent", "girl child"]})
    assert s.bucket_2_bonus == ["single parent", "girl child"]
    assert s.bucket_1_keys == {"grade": None, "caste": None, "income": None}
    assert s.bucket_3_missing == ["grade", "caste", "income"]


def test_session_accumulates_bonus_across_merges():
    """Bonus items from multiple messages should all accumulate."""
    s = Session()
    s.merge({"bucket_2_bonus": ["disabled"]})
    s.merge({"bucket_2_bonus": ["girl child"]})
    s.merge({"bucket_2_bonus": ["orphan"]})
    assert s.bucket_2_bonus == ["disabled", "girl child", "orphan"]


def test_session_isolation():
    """Two phone numbers get independent sessions."""
    phone_a = "whatsapp:+isolation_a"
    phone_b = "whatsapp:+isolation_b"
    reset_session(phone_a)
    reset_session(phone_b)

    sa = get_session(phone_a)
    sa.merge({"bucket_1_keys": {"grade": "10", "caste": None, "income": None}})

    sb = get_session(phone_b)
    sb.merge({"bucket_1_keys": {"grade": None, "caste": "OBC", "income": None}})

    assert get_session(phone_a).bucket_1_keys["grade"] == "10"
    assert get_session(phone_a).bucket_1_keys["caste"] is None
    assert get_session(phone_b).bucket_1_keys["caste"] == "OBC"
    assert get_session(phone_b).bucket_1_keys["grade"] is None

    reset_session(phone_a)
    reset_session(phone_b)


def test_session_missing_recomputed_after_each_merge():
    """bucket_3_missing should shrink as keys are filled across merges."""
    s = Session()
    assert s.bucket_3_missing == ["grade", "caste", "income"]

    s.merge({"bucket_1_keys": {"grade": "8", "caste": None, "income": None}})
    assert s.bucket_3_missing == ["caste", "income"]

    s.merge({"bucket_1_keys": {"grade": None, "caste": "ST", "income": None}})
    assert s.bucket_3_missing == ["income"]

    s.merge({"bucket_1_keys": {"grade": None, "caste": None, "income": 50000}})
    assert s.bucket_3_missing == []
    assert s.all_keys_collected is True


# ────────────────────────────────────────────
# Groq — extract_buckets structural guarantees
# ────────────────────────────────────────────

@pytest.mark.asyncio
@patch("services.groq_llm.AsyncGroq")
async def test_extract_buckets_fills_missing_fields(MockGroq, monkeypatch):
    """If Groq returns valid JSON but missing keys, setdefault fills them."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    # Partial JSON — no bucket_2_bonus or bucket_3_missing
    fake = json.dumps({"bucket_1_keys": {"grade": "12"}})

    mock_choice = MagicMock()
    mock_choice.message.content = fake
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    MockGroq.return_value = mock_client

    result = await extract_buckets("some text")
    # Structural guarantee: all three buckets exist
    assert "bucket_1_keys" in result
    assert "bucket_2_bonus" in result
    assert "bucket_3_missing" in result
    # Missing core keys should have None defaults
    assert result["bucket_1_keys"].get("caste") is None
    assert result["bucket_1_keys"].get("income") is None
    assert result["bucket_1_keys"]["grade"] == "12"


@pytest.mark.asyncio
@patch("services.groq_llm.AsyncGroq")
async def test_extract_buckets_completely_empty_json(MockGroq, monkeypatch):
    """Even an empty JSON object {} should return a safe structure."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    mock_choice = MagicMock()
    mock_choice.message.content = "{}"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    MockGroq.return_value = mock_client

    result = await extract_buckets("some text")
    assert result["bucket_1_keys"]["grade"] is None
    assert result["bucket_1_keys"]["caste"] is None
    assert result["bucket_1_keys"]["income"] is None
    assert result["bucket_2_bonus"] == []
    assert result["bucket_3_missing"] == []

