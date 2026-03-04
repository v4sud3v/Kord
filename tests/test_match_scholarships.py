"""Tests for the match_scholarships agent tool."""

from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest

from data.models import Scholarship


def _make_scholarship(**kwargs):
    defaults = {
        "name": "Test Scholarship",
        "source": "myscheme",
        "description": "A test scholarship",
        "eligibility_grade": "12",
        "eligibility_caste": "SC",
        "eligibility_income_max": 200000,
        "benefits": "₹10,000/year",
        "url": "https://example.com",
        "tags": ["Kerala"],
        "last_updated": datetime.utcnow(),
    }
    defaults.update(kwargs)
    return Scholarship(**defaults)


@patch("agent.tools.match_scholarships.query_scholarships")
def test_match_returns_relevant_scholarships(mock_query):
    """match_scholarships should return formatted results from DB."""
    from agent.tools.match_scholarships import match_scholarships

    mock_query.return_value = [
        _make_scholarship(name="E-Grantz SC", eligibility_caste="SC"),
        _make_scholarship(name="Merit Award", eligibility_caste=None),
    ]

    results = match_scholarships(
        bucket_1_keys={"grade": "12", "caste": "SC", "income": 100000},
        bucket_2_bonus=["Kerala"],
    )

    assert len(results) == 2
    assert results[0]["name"] == "E-Grantz SC"
    assert "url" in results[0]
    assert "eligibility_summary" in results[0]


@patch("agent.tools.match_scholarships.query_scholarships")
def test_match_empty_db(mock_query):
    """Should return empty list when DB has no matches."""
    from agent.tools.match_scholarships import match_scholarships

    mock_query.return_value = []

    results = match_scholarships(
        bucket_1_keys={"grade": "12", "caste": "General", "income": 1000000},
    )

    assert results == []


@patch("agent.tools.match_scholarships.query_scholarships")
def test_match_handles_string_income(mock_query):
    """Income may come as a string from Groq — should handle gracefully."""
    from agent.tools.match_scholarships import match_scholarships

    mock_query.return_value = []

    # Should not crash even if income is a string
    results = match_scholarships(
        bucket_1_keys={"grade": "12", "caste": "SC", "income": "50000"},
    )

    assert results == []
    # Verify income was converted to int for the query
    call_args = mock_query.call_args
    assert call_args.kwargs["income"] == 50000


@patch("agent.tools.match_scholarships.query_scholarships")
def test_match_handles_none_income(mock_query):
    """None income should be passed through."""
    from agent.tools.match_scholarships import match_scholarships

    mock_query.return_value = []

    results = match_scholarships(
        bucket_1_keys={"grade": "12", "caste": "SC", "income": None},
    )

    call_args = mock_query.call_args
    assert call_args.kwargs["income"] is None


def test_eligibility_summary_format():
    """_build_eligibility_summary should produce readable strings."""
    from agent.tools.match_scholarships import _build_eligibility_summary

    s = _make_scholarship(
        eligibility_grade="12",
        eligibility_caste="SC",
        eligibility_income_max=250000,
    )
    summary = _build_eligibility_summary(s)
    assert "Class 12+" in summary
    assert "SC category" in summary
    assert "₹2.5 lakh" in summary or "₹2 lakh" in summary


def test_eligibility_summary_bpl():
    """BPL income (0) should show as 'BPL only'."""
    from agent.tools.match_scholarships import _build_eligibility_summary

    s = _make_scholarship(eligibility_income_max=0)
    summary = _build_eligibility_summary(s)
    assert "BPL only" in summary


def test_eligibility_summary_open():
    """No restrictions should show 'Open to all'."""
    from agent.tools.match_scholarships import _build_eligibility_summary

    s = _make_scholarship(
        eligibility_grade=None,
        eligibility_caste=None,
        eligibility_income_max=None,
    )
    summary = _build_eligibility_summary(s)
    assert summary == "Open to all"
