"""Data models for scholarships and scrape metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Scholarship:
    """One scholarship record from any source."""

    name: str
    source: str  # "myscheme" | "egrantz" | "buddy4study"
    description: str = ""
    eligibility_grade: str | None = None   # e.g. "10", "12", "UG"
    eligibility_caste: str | None = None   # e.g. "SC", "ST", "OBC", "General"
    eligibility_income_max: int | None = None  # annual ₹, None = no ceiling
    benefits: str = ""
    url: str = ""
    tags: list[str] = field(default_factory=list)  # bonus match tags
    last_updated: datetime = field(default_factory=datetime.utcnow)
    id: int | None = None  # DB-assigned

    def tags_json(self) -> str:
        """Serialize tags for SQLite storage."""
        return json.dumps(self.tags)

    @staticmethod
    def tags_from_json(raw: str) -> list[str]:
        """Deserialize tags from SQLite storage."""
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []


@dataclass
class ScrapeMeta:
    """Tracks when a source was last scraped."""

    source: str
    last_scraped_at: datetime
    record_count: int
    status: str = "ok"  # "ok" | "error"
