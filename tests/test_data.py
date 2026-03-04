"""Tests for the data layer (Supabase-backed)."""

from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest

from data.models import Scholarship, ScrapeMeta


# ── Model tests ───────────────────────────────────────────────

def test_scholarship_tags_json_roundtrip():
    """Tags should serialize to JSON and back."""
    s = Scholarship(name="Test", source="myscheme", tags=["Kerala", "SC"])
    json_str = s.tags_json()
    assert json_str == '["Kerala", "SC"]'
    assert Scholarship.tags_from_json(json_str) == ["Kerala", "SC"]


def test_scholarship_tags_from_json_handles_bad_input():
    assert Scholarship.tags_from_json("not json") == []
    assert Scholarship.tags_from_json(None) == []
    assert Scholarship.tags_from_json("") == []


def test_scholarship_defaults():
    s = Scholarship(name="Test", source="myscheme")
    assert s.description == ""
    assert s.eligibility_grade is None
    assert s.eligibility_caste is None
    assert s.eligibility_income_max is None
    assert s.tags == []
    assert s.id is None


def test_scrape_meta_defaults():
    meta = ScrapeMeta(
        source="myscheme",
        last_scraped_at=datetime.utcnow(),
        record_count=10,
    )
    assert meta.status == "ok"


# ── DB function tests (mocked Supabase) ──────────────────────


def _mock_supabase_client():
    """Create a mock Supabase client with chainable table methods."""
    client = MagicMock()

    # Make table().method().method() chainable
    table = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[])
    chain.eq.return_value = chain
    chain.or_.return_value = chain
    chain.limit.return_value = chain
    table.select.return_value = chain
    table.delete.return_value = chain
    table.insert.return_value = chain
    table.upsert.return_value = chain
    client.table.return_value = table

    return client, table, chain


@patch("data.db._get_client")
def test_init_db_verifies_connection(mock_get_client):
    """init_db should try to query scrape_meta as a health check."""
    from data.db import init_db

    client, table, chain = _mock_supabase_client()
    mock_get_client.return_value = client

    init_db()

    client.table.assert_called_with("scrape_meta")
    table.select.assert_called_with("source")


@patch("data.db._get_client")
def test_upsert_scholarships_deletes_then_inserts(mock_get_client):
    """upsert should delete existing source records then insert new ones."""
    from data.db import upsert_scholarships

    client, table, chain = _mock_supabase_client()
    mock_get_client.return_value = client

    scholarships = [
        Scholarship(name="Test 1", source="myscheme", tags=["Kerala"]),
        Scholarship(name="Test 2", source="myscheme", tags=["SC"]),
    ]

    upsert_scholarships("myscheme", scholarships)

    # Should delete existing myscheme records
    table.delete.assert_called()
    # Should insert new records
    table.insert.assert_called()
    # Should upsert scrape_meta
    table.upsert.assert_called()


@patch("data.db._get_client")
def test_get_scrape_meta_returns_none_when_never_scraped(mock_get_client):
    """get_scrape_meta should return None for unknown sources."""
    from data.db import get_scrape_meta

    client, table, chain = _mock_supabase_client()
    chain.execute.return_value = MagicMock(data=[])
    mock_get_client.return_value = client

    result = get_scrape_meta("unknown_source")
    assert result is None


@patch("data.db._get_client")
def test_get_scrape_meta_returns_meta(mock_get_client):
    """get_scrape_meta should parse row data correctly."""
    from data.db import get_scrape_meta

    client, table, chain = _mock_supabase_client()
    chain.execute.return_value = MagicMock(data=[{
        "source": "myscheme",
        "last_scraped_at": "2026-03-04T10:00:00",
        "record_count": 15,
        "status": "ok",
    }])
    mock_get_client.return_value = client

    result = get_scrape_meta("myscheme")
    assert result is not None
    assert result.source == "myscheme"
    assert result.record_count == 15
    assert result.status == "ok"


@patch("data.db._get_client")
def test_query_scholarships_applies_filters(mock_get_client):
    """query_scholarships should build correct PostgREST filters."""
    from data.db import query_scholarships

    client, table, chain = _mock_supabase_client()
    chain.execute.return_value = MagicMock(data=[
        {
            "id": 1,
            "source": "myscheme",
            "name": "Test Scholarship",
            "description": "A test",
            "eligibility_grade": "12",
            "eligibility_caste": "SC",
            "eligibility_income_max": 200000,
            "benefits": "₹10,000/year",
            "url": "https://example.com",
            "tags": ["Kerala", "SC"],
            "last_updated": "2026-03-04T10:00:00",
        }
    ])
    mock_get_client.return_value = client

    results = query_scholarships(grade="12", caste="SC", income=150000)

    assert len(results) == 1
    assert results[0].name == "Test Scholarship"
    assert results[0].tags == ["Kerala", "SC"]

    # Verify or_ filters were applied (3 calls: grade, caste, income)
    assert chain.or_.call_count == 3


@patch("data.db._get_client")
def test_query_scholarships_sorts_by_tag_relevance(mock_get_client):
    """Scholarships with matching bonus tags should come first."""
    from data.db import query_scholarships

    client, table, chain = _mock_supabase_client()
    chain.execute.return_value = MagicMock(data=[
        {
            "id": 1, "source": "myscheme", "name": "No Tags",
            "description": "", "eligibility_grade": None,
            "eligibility_caste": None, "eligibility_income_max": None,
            "benefits": "", "url": "", "tags": [],
            "last_updated": "2026-03-04T10:00:00",
        },
        {
            "id": 2, "source": "egrantz", "name": "Kerala SC",
            "description": "", "eligibility_grade": None,
            "eligibility_caste": "SC", "eligibility_income_max": None,
            "benefits": "", "url": "", "tags": ["Kerala", "SC", "girl child"],
            "last_updated": "2026-03-04T10:00:00",
        },
    ])
    mock_get_client.return_value = client

    results = query_scholarships(bonus_tags=["girl child", "Kerala"])

    # The scholarship with matching tags should be first
    assert results[0].name == "Kerala SC"
    assert results[1].name == "No Tags"
