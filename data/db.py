"""Supabase-backed scholarship storage and querying.

Tables (create in Supabase dashboard)
------
scholarships  — one row per scholarship from any source.
scrape_meta   — one row per source, tracks last-scraped time.

Required environment variables:
  SUPABASE_URL  — your project URL (e.g. https://xyz.supabase.co)
  SUPABASE_KEY  — service-role or anon key
"""

from __future__ import annotations

import os
from datetime import datetime

from supabase import create_client, Client

from data.models import Scholarship, ScrapeMeta


def _get_client() -> Client:
    """Return a configured Supabase client."""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY environment variables must be set"
        )
    return create_client(url, key)


# ── Schema bootstrap (run once via Supabase SQL editor) ───────
#
# Copy-paste this into your Supabase SQL editor:
#
# CREATE TABLE IF NOT EXISTS scholarships (
#     id                     BIGSERIAL PRIMARY KEY,
#     source                 TEXT NOT NULL,
#     name                   TEXT NOT NULL,
#     description            TEXT DEFAULT '',
#     eligibility_grade      TEXT,
#     eligibility_caste      TEXT,
#     eligibility_income_max INTEGER,
#     benefits               TEXT DEFAULT '',
#     url                    TEXT DEFAULT '',
#     tags                   JSONB DEFAULT '[]',
#     last_updated           TIMESTAMPTZ NOT NULL DEFAULT now()
# );
#
# CREATE INDEX IF NOT EXISTS idx_scholarships_source
#     ON scholarships(source);
# CREATE INDEX IF NOT EXISTS idx_scholarships_caste
#     ON scholarships(eligibility_caste);
#
# CREATE TABLE IF NOT EXISTS scrape_meta (
#     source          TEXT PRIMARY KEY,
#     last_scraped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
#     record_count    INTEGER DEFAULT 0,
#     status          TEXT DEFAULT 'ok'
# );


def init_db() -> None:
    """Verify connection to Supabase (tables must already exist)."""
    client = _get_client()
    # Quick health check — try to read scrape_meta
    try:
        client.table("scrape_meta").select("source").limit(1).execute()
        print("[db] Connected to Supabase ✅")
    except Exception as e:
        print(f"[db] ⚠ Supabase connection check failed: {e}")
        print("[db] Make sure the scholarships and scrape_meta tables exist.")
        raise


# ── Write operations ──────────────────────────────────────────


def upsert_scholarships(source: str, scholarships: list[Scholarship]) -> None:
    """Replace ALL records for `source`, update scrape_meta."""
    client = _get_client()
    now = datetime.utcnow().isoformat()

    try:
        # Delete existing records for this source
        client.table("scholarships").delete().eq("source", source).execute()

        # Insert new records in batches of 50
        rows = [
            {
                "source": source,
                "name": s.name,
                "description": s.description,
                "eligibility_grade": s.eligibility_grade,
                "eligibility_caste": s.eligibility_caste,
                "eligibility_income_max": s.eligibility_income_max,
                "benefits": s.benefits,
                "url": s.url,
                "tags": s.tags,  # Supabase handles JSONB natively
                "last_updated": now,
            }
            for s in scholarships
        ]

        for i in range(0, len(rows), 50):
            batch = rows[i : i + 50]
            client.table("scholarships").insert(batch).execute()

        # Update scrape_meta
        client.table("scrape_meta").upsert(
            {
                "source": source,
                "last_scraped_at": now,
                "record_count": len(scholarships),
                "status": "ok",
            }
        ).execute()

        print(f"[db] Upserted {len(scholarships)} scholarships for source={source}")

    except Exception as e:
        # Record error in scrape_meta
        try:
            client.table("scrape_meta").upsert(
                {
                    "source": source,
                    "last_scraped_at": now,
                    "record_count": 0,
                    "status": "error",
                }
            ).execute()
        except Exception:
            pass
        raise


# ── Read operations ───────────────────────────────────────────


def get_scrape_meta(source: str) -> ScrapeMeta | None:
    """Return scrape metadata for a source, or None if never scraped."""
    client = _get_client()
    result = (
        client.table("scrape_meta")
        .select("*")
        .eq("source", source)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]
    return ScrapeMeta(
        source=row["source"],
        last_scraped_at=datetime.fromisoformat(row["last_scraped_at"]),
        record_count=row["record_count"],
        status=row["status"],
    )


def query_scholarships(
    grade: str | None = None,
    caste: str | None = None,
    income: int | None = None,
    bonus_tags: list[str] | None = None,
) -> list[Scholarship]:
    """
    Query scholarships matching the student's profile.

    Matching logic:
    - grade: exact match OR scholarship has no grade restriction (NULL)
    - caste: exact match OR scholarship has no caste restriction (NULL)
    - income: student income <= eligibility_income_max OR no ceiling (NULL)
    - bonus_tags: any tag overlap boosts relevance (returned first)
    """
    client = _get_client()
    query = client.table("scholarships").select("*")

    # Supabase PostgREST: or filter for nullable eligibility fields
    if grade is not None:
        query = query.or_(
            f"eligibility_grade.is.null,eligibility_grade.eq.{grade}"
        )

    if caste is not None:
        query = query.or_(
            f"eligibility_caste.is.null,eligibility_caste.eq.{caste}"
        )

    if income is not None:
        query = query.or_(
            f"eligibility_income_max.is.null,eligibility_income_max.gte.{income}"
        )

    result = query.execute()
    rows = result.data or []

    scholarships = [_row_to_scholarship(r) for r in rows]

    # Sort: tag-matched scholarships first
    if bonus_tags:
        tag_set = {t.lower() for t in bonus_tags}

        def tag_score(s: Scholarship) -> int:
            return -len(tag_set & {t.lower() for t in s.tags})

        scholarships.sort(key=tag_score)

    return scholarships


def _row_to_scholarship(row: dict) -> Scholarship:
    """Convert a Supabase row dict to a Scholarship dataclass."""
    tags = row.get("tags", [])
    if isinstance(tags, str):
        import json
        try:
            tags = json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            tags = []

    return Scholarship(
        id=row.get("id"),
        source=row["source"],
        name=row["name"],
        description=row.get("description", ""),
        eligibility_grade=row.get("eligibility_grade"),
        eligibility_caste=row.get("eligibility_caste"),
        eligibility_income_max=row.get("eligibility_income_max"),
        benefits=row.get("benefits", ""),
        url=row.get("url", ""),
        tags=tags,
        last_updated=datetime.fromisoformat(row["last_updated"]),
    )
