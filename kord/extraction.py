"""
Extraction module — LLM-powered entity extraction.

Responsibilities:
  - Send the user's English text to Gemini (or OpenAI) with a strict system prompt.
  - Parse the model response into a StudentProfile dict.
  - Merge the new fields into the existing session profile.
"""

from __future__ import annotations

import json
import os
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

_MODEL = "gemini-1.5-flash"

_SYSTEM_PROMPT = """
You are a precise entity extractor for a scholarship eligibility assistant.
The user is a student or parent from Kerala, India.

Given a message, update ONLY the fields you can confidently extract.
Return a single valid JSON object with exactly these keys:
  age      – integer or null
  grade    – integer (school grade 1–12) or null
  caste    – one of "SC", "ST", "OBC", "General", or null
  income   – annual household income in INR as integer, or null

Do not add any extra keys. Do not include any explanation outside the JSON.
""".strip()


def extract_profile_fields(english_text: str) -> dict[str, Any]:
    """
    Ask the LLM to extract student profile fields from *english_text*.
    Returns a partial profile dict — only the keys the model was able to fill.
    Missing/unknown fields are returned as null (None).
    """
    model = genai.GenerativeModel(_MODEL, system_instruction=_SYSTEM_PROMPT)
    response = model.generate_content(english_text)
    raw = response.text.strip()

    # Strip markdown code fences if the model wraps the JSON
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw)


def merge_profile(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """
    Merge *updates* into *existing*, only overwriting None values.
    This prevents a later message from accidentally clearing confirmed data.
    """
    merged = dict(existing)
    for key, value in updates.items():
        if value is not None:
            merged[key] = value
    return merged


def missing_fields(profile: dict[str, Any]) -> list[str]:
    """Return the list of profile keys that are still None."""
    return [k for k, v in profile.items() if v is None]
