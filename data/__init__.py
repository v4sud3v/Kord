"""Data layer — SQLite-backed scholarship storage."""

from data.db import init_db, upsert_scholarships, query_scholarships, get_scrape_meta
from data.models import Scholarship, ScrapeMeta

__all__ = [
    "init_db",
    "upsert_scholarships",
    "query_scholarships",
    "get_scrape_meta",
    "Scholarship",
    "ScrapeMeta",
]
