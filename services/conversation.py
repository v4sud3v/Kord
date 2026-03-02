"""In-memory conversation state — accumulates buckets across messages.

Each WhatsApp number gets its own session that merges new Groq extractions
into a running view of the three buckets.

For production you'd back this with Redis / a database.
For the prototype this simple dict is fine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

REQUIRED_KEYS = ["grade", "caste", "income"]


@dataclass
class Session:
    """One student's accumulated bucket state."""

    # Bucket 1 — core keys (merged across messages)
    bucket_1_keys: dict = field(
        default_factory=lambda: {"grade": None, "caste": None, "income": None}
    )

    # Bucket 2 — bonus context (accumulated, deduplicated)
    bucket_2_bonus: list[str] = field(default_factory=list)

    # Bucket 3 — missing keys (recomputed after every merge)
    bucket_3_missing: list[str] = field(default_factory=lambda: list(REQUIRED_KEYS))

    def merge(self, extraction: dict) -> None:
        """Merge a fresh Groq extraction into this session's state."""
        # Merge core keys — only overwrite with non-null values
        new_keys = extraction.get("bucket_1_keys", {})
        for k in REQUIRED_KEYS:
            val = new_keys.get(k)
            if val is not None:
                self.bucket_1_keys[k] = val

        # Accumulate bonus details (deduplicate, case-insensitive)
        existing = {d.lower() for d in self.bucket_2_bonus}
        for detail in extraction.get("bucket_2_bonus", []):
            if detail.lower() not in existing:
                self.bucket_2_bonus.append(detail)
                existing.add(detail.lower())

        # Recompute missing from our own state (source of truth)
        # Use `is None` — 0 is a valid value (e.g. BPL income)
        self.bucket_3_missing = [
            k for k in REQUIRED_KEYS if self.bucket_1_keys.get(k) is None
        ]

    @property
    def all_keys_collected(self) -> bool:
        return len(self.bucket_3_missing) == 0


# ── Global session store ─────────────────────────────────────

_sessions: dict[str, Session] = {}


def get_session(phone: str) -> Session:
    if phone not in _sessions:
        _sessions[phone] = Session()
    return _sessions[phone]


def reset_session(phone: str) -> None:
    _sessions.pop(phone, None)
