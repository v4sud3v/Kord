"""Scrapers package — unified entry points for all scholarship sources."""

from __future__ import annotations

from datetime import datetime, timedelta

from data.db import get_scrape_meta, upsert_scholarships
from scrapers.myscheme import scrape_myscheme
from scrapers.egrantz import scrape_egrantz
from scrapers.buddy4study import scrape_buddy4study

_SOURCES = {
    "myscheme": scrape_myscheme,
    "egrantz": scrape_egrantz,
    "buddy4study": scrape_buddy4study,
}


async def scrape_all() -> dict[str, int]:
    """
    Run all three scrapers and upsert results into the database.

    Returns a dict of {source: record_count}.
    """
    print("[scrapers] Running all scrapers...")
    counts: dict[str, int] = {}

    for source, scraper_fn in _SOURCES.items():
        try:
            scholarships = await scraper_fn()
            upsert_scholarships(source, scholarships)
            counts[source] = len(scholarships)
        except Exception as e:
            print(f"[scrapers] ⚠ {source} failed: {e}")
            counts[source] = 0

    total = sum(counts.values())
    print(f"[scrapers] All done — {total} total scholarships across {len(counts)} sources")
    return counts


async def refresh_if_stale(max_age_hours: int = 24) -> dict[str, int]:
    """
    Only scrape sources whose data is older than `max_age_hours`.

    Returns a dict of {source: record_count} for sources that were refreshed.
    """
    print(f"[scrapers] Checking staleness (max_age={max_age_hours}h)...")
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    counts: dict[str, int] = {}

    for source, scraper_fn in _SOURCES.items():
        meta = get_scrape_meta(source)

        if meta and meta.last_scraped_at > cutoff and meta.status == "ok":
            print(
                f"[scrapers] {source}: fresh ({meta.record_count} records, "
                f"scraped {meta.last_scraped_at.isoformat()})"
            )
            continue

        reason = "never scraped" if meta is None else f"stale (last: {meta.last_scraped_at.isoformat()})"
        print(f"[scrapers] {source}: {reason} — refreshing...")

        try:
            scholarships = await scraper_fn()
            upsert_scholarships(source, scholarships)
            counts[source] = len(scholarships)
        except Exception as e:
            print(f"[scrapers] ⚠ {source} refresh failed: {e}")
            counts[source] = 0

    if counts:
        print(f"[scrapers] Refreshed {len(counts)} source(s)")
    else:
        print("[scrapers] All sources are fresh, no refresh needed")

    return counts
