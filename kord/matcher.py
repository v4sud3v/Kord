"""
Matcher module — scholarship eligibility logic.

Responsibilities:
  - Load scholarship rules from data/scholarships.json.
  - Compare a complete student profile against each scholarship's criteria.
  - Return the list of scholarships the student qualifies for.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA_FILE = Path(__file__).parent.parent / "data" / "scholarships.json"


def load_scholarships() -> list[dict[str, Any]]:
    """Load scholarship definitions from the JSON data file."""
    with _DATA_FILE.open() as f:
        return json.load(f)


def check_eligibility(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Return the scholarships (as dicts with name, description, documents)
    that match the given student *profile*.

    The profile must be fully filled before calling this function.
    """
    scholarships = load_scholarships()
    eligible: list[dict[str, Any]] = []

    for s in scholarships:
        c = s["criteria"]

        # Caste filter
        if "caste" in c and profile.get("caste") not in c["caste"]:
            continue

        # Grade filters
        grade = profile.get("grade")
        if grade is not None:
            if "min_grade" in c and grade < c["min_grade"]:
                continue
            if "max_grade" in c and grade > c["max_grade"]:
                continue

        # Income filter
        income = profile.get("income")
        if "max_income" in c and income is not None and income > c["max_income"]:
            continue

        eligible.append(s)

    return eligible
