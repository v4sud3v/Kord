"""Tool: Match scholarships from the local database.

Queries the Supabase scholarship database using the student's
bucket_1_keys and bucket_2_bonus to find relevant scholarships.

This is a deterministic tool — no AI calls, just DB queries.
"""

from __future__ import annotations

from data.db import query_scholarships


def match_scholarships(
    bucket_1_keys: dict, bucket_2_bonus: list[str] | None = None
) -> list[dict]:
    """
    Find scholarships matching the student's profile.

    Args:
        bucket_1_keys: {"grade": "12", "caste": "SC", "income": 40000}
        bucket_2_bonus: ["disabled", "girl child", ...]

    Returns:
        List of matched scholarship dicts, sorted by relevance.
    """
    grade = bucket_1_keys.get("grade")
    caste = bucket_1_keys.get("caste")
    income = bucket_1_keys.get("income")

    # Convert income to int if it's a string
    if isinstance(income, str):
        try:
            income = int(income)
        except (ValueError, TypeError):
            income = None

    matches = query_scholarships(
        grade=grade,
        caste=caste,
        income=income,
        bonus_tags=bucket_2_bonus or [],
    )

    # Format for the agent response
    results = []
    for s in matches:
        results.append({
            "name": s.name,
            "source": s.source,
            "benefits": s.benefits,
            "url": s.url,
            "eligibility_summary": _build_eligibility_summary(s),
            "tags": s.tags,
        })

    print(f"[match] Found {len(results)} matching scholarships")
    return results


def _build_eligibility_summary(s) -> str:
    """Build a human-readable eligibility one-liner."""
    parts = []
    if s.eligibility_grade:
        parts.append(f"Class {s.eligibility_grade}+")
    if s.eligibility_caste:
        parts.append(f"{s.eligibility_caste} category")
    if s.eligibility_income_max is not None:
        if s.eligibility_income_max == 0:
            parts.append("BPL only")
        else:
            lakhs = s.eligibility_income_max / 100_000
            if lakhs == int(lakhs):
                parts.append(f"Income ≤ ₹{int(lakhs)} lakh/year")
            else:
                parts.append(f"Income ≤ ₹{lakhs:.1f} lakh/year")
    return " • ".join(parts) if parts else "Open to all"
