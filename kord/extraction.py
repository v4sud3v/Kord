"""
Extraction module — LLM-powered entity extraction (Groq Cloud API).

This module extracts structured student profile fields from plain English text
using the Groq Cloud API (OpenAI-compatible endpoint).

Environment variables required:
  - GROQ_API_KEY: Your Groq API key from https://console.groq.com

The module returns a JSON object with exactly these keys:
  - age: integer or null
  - grade: integer (1–12) or null
  - caste: one of "SC", "ST", "OBC", "General", or null
  - income: annual household income in INR as integer, or null

The extractor asks the model to only return the JSON object — no extra text.
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

# Environment configuration
_GROQ_KEY = os.environ.get("GROQ_API_KEY")
_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.3-70b-versatile"  # Fast, capable model

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


def _call_groq(user_text: str) -> str:
    """Call the Groq Cloud API using OpenAI-compatible format.

    This function expects `GROQ_API_KEY` to be set in the environment.
    Returns the assistant's message content as a string.
    """
    if not _GROQ_KEY:
        raise RuntimeError(
            "GROQ_API_KEY must be set in the environment. "
            "Get your key from https://console.groq.com"
        )

    headers = {
        "Authorization": f"Bearer {_GROQ_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": _GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.1,  # Low temperature for consistent extraction
        "max_tokens": 200,
    }

    resp = requests.post(_GROQ_API_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    # OpenAI-compatible response: data["choices"][0]["message"]["content"]
    return data["choices"][0]["message"]["content"].strip()


def extract_profile_fields(english_text: str) -> dict[str, Any]:
    """
    Use Groq to extract profile fields from *english_text*.

    Returns a dict with keys `age`, `grade`, `caste`, `income` (values may
    be None). The model is instructed to return only JSON; this function
    will strip code fences if present and parse the JSON.
    """
    raw = _call_groq(english_text)

    # Strip code fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 2:
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]

    return json.loads(raw)


def merge_profile(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Merge *updates* into *existing*, only overwriting None values."""
    merged = dict(existing)
    for key, value in updates.items():
        if value is not None:
            merged[key] = value
    return merged


def missing_fields(profile: dict[str, Any]) -> list[str]:
    """Return the list of profile keys that are still None."""
    return [k for k, v in profile.items() if v is None]
