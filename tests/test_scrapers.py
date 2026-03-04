"""Tests for scrapers — all HTTP calls mocked."""

from unittest.mock import patch, AsyncMock, MagicMock
import json

import pytest

from data.models import Scholarship


# ── myScheme scraper tests ───────────────────────────────────


@pytest.mark.asyncio
@patch("scrapers.myscheme.fetch_page", new_callable=AsyncMock)
async def test_myscheme_scraper_parses_scheme_page(mock_fetch):
    """myScheme scraper should parse __NEXT_DATA__ from scheme pages."""
    from scrapers.myscheme import scrape_myscheme

    # Simulate a scheme page with __NEXT_DATA__
    next_data = {
        "props": {
            "pageProps": {
                "schemeData": {
                    "schemeName": "E-Grantz Scholarship",
                    "schemeDescription": "Financial aid for SC/ST students",
                    "schemeBenefits": "Tuition fee + maintenance",
                    "schemeEligibility": "Post-matric SC students, income below 2.5 lakh",
                }
            }
        }
    }
    mock_html = f'<html><script id="__NEXT_DATA__">{json.dumps(next_data)}</script></html>'
    mock_fetch.return_value = mock_html

    results = await scrape_myscheme()
    assert len(results) > 0
    # All results should be Scholarship instances
    for s in results:
        assert isinstance(s, Scholarship)
        assert s.source == "myscheme"


@pytest.mark.asyncio
@patch("scrapers.myscheme.fetch_page", new_callable=AsyncMock)
async def test_myscheme_scraper_handles_fetch_errors(mock_fetch):
    """myScheme scraper should gracefully handle HTTP errors."""
    from scrapers.myscheme import scrape_myscheme

    mock_fetch.side_effect = Exception("Connection refused")

    results = await scrape_myscheme()
    # Should return empty list, not crash
    assert results == []


# ── e-Grantz scraper tests ───────────────────────────────────


@pytest.mark.asyncio
async def test_egrantz_scraper_returns_curated_data():
    """e-Grantz scraper should return the curated Kerala scholarship list."""
    from scrapers.egrantz import scrape_egrantz

    results = await scrape_egrantz()
    assert len(results) > 0

    # All should be egrantz source
    for s in results:
        assert s.source == "egrantz"
        assert "Kerala" in s.tags

    # Check specific known schemes exist
    names = [s.name for s in results]
    assert any("SC" in name for name in names)
    assert any("ST" in name for name in names)


@pytest.mark.asyncio
async def test_egrantz_all_have_urls():
    """Every e-Grantz scholarship should have a URL."""
    from scrapers.egrantz import scrape_egrantz

    results = await scrape_egrantz()
    for s in results:
        assert s.url, f"Missing URL for: {s.name}"


# ── Buddy4Study scraper tests ────────────────────────────────


@pytest.mark.asyncio
@patch("scrapers.buddy4study.fetch_page", new_callable=AsyncMock)
async def test_buddy4study_scraper_extracts_slugs(mock_fetch):
    """Buddy4Study scraper should extract scholarship slugs from listing pages."""
    from scrapers.buddy4study import _extract_slugs_from_listing

    html = """
    <html>
    <body>
        <a href="/scholarship/hdfc-scholarship">HDFC</a>
        <a href="/scholarship/tata-scholarship">Tata</a>
        <a href="/about">About</a>
    </body>
    </html>
    """
    slugs = _extract_slugs_from_listing(html)
    assert "hdfc-scholarship" in slugs
    assert "tata-scholarship" in slugs
    assert "about" not in slugs


@pytest.mark.asyncio
@patch("scrapers.buddy4study.fetch_page", new_callable=AsyncMock)
async def test_buddy4study_handles_empty_listings(mock_fetch):
    """Buddy4Study should return empty list when no slugs are found."""
    from scrapers.buddy4study import scrape_buddy4study

    mock_fetch.return_value = "<html><body>No scholarships</body></html>"

    results = await scrape_buddy4study()
    assert results == []


# ── Base utilities tests ──────────────────────────────────────


def test_extract_next_data_parses_json():
    """Should extract JSON from __NEXT_DATA__ script tag."""
    from scrapers.base import extract_next_data

    html = '<html><script id="__NEXT_DATA__">{"props":{"test":1}}</script></html>'
    data = extract_next_data(html)
    assert data["props"]["test"] == 1


def test_extract_next_data_returns_empty_on_missing():
    """Should return {} when no __NEXT_DATA__ found."""
    from scrapers.base import extract_next_data

    data = extract_next_data("<html><body>No script</body></html>")
    assert data == {}


def test_clean_text_strips_html():
    """Should remove HTML tags and normalize whitespace."""
    from scrapers.base import clean_text

    assert clean_text("<b>Hello</b> <i>World</i>") == "Hello World"
    assert clean_text("  multiple   spaces  ") == "multiple spaces"
    assert clean_text(None) == ""
    assert clean_text("") == ""


# ── Refresh logic tests ──────────────────────────────────────


@pytest.mark.asyncio
@patch("scrapers.upsert_scholarships")
@patch("scrapers.get_scrape_meta")
async def test_refresh_if_stale_skips_fresh_data(mock_meta, mock_upsert):
    """refresh_if_stale should skip sources with fresh data."""
    from scrapers import refresh_if_stale
    from data.models import ScrapeMeta
    from datetime import datetime

    # All sources are fresh (scraped 1 hour ago)
    mock_meta.return_value = ScrapeMeta(
        source="myscheme",
        last_scraped_at=datetime.utcnow(),
        record_count=10,
        status="ok",
    )

    mock_scraper = AsyncMock(return_value=[])

    with patch("scrapers._SOURCES", {
        "myscheme": mock_scraper,
        "egrantz": mock_scraper,
        "buddy4study": mock_scraper,
    }):
        counts = await refresh_if_stale(max_age_hours=24)

    # No scrapers should have been called (all fresh)
    mock_scraper.assert_not_called()
    assert counts == {}


@pytest.mark.asyncio
@patch("scrapers.upsert_scholarships")
@patch("scrapers.get_scrape_meta")
async def test_refresh_if_stale_scrapes_when_never_scraped(mock_meta, mock_upsert):
    """refresh_if_stale should scrape sources that have never been scraped."""
    from scrapers import refresh_if_stale

    # Never scraped
    mock_meta.return_value = None

    mock_ms = AsyncMock(return_value=[])
    mock_eg = AsyncMock(return_value=[])
    mock_b4s = AsyncMock(return_value=[])

    with patch("scrapers._SOURCES", {
        "myscheme": mock_ms,
        "egrantz": mock_eg,
        "buddy4study": mock_b4s,
    }):
        counts = await refresh_if_stale(max_age_hours=24)

    # All scrapers should have been called
    mock_ms.assert_called_once()
    mock_eg.assert_called_once()
    mock_b4s.assert_called_once()

