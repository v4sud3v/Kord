"""Tool: Extract buckets from translated text via Groq LLM.

Takes the translated text and sorts it into exactly three JSON buckets:
  bucket_1_keys   → grade, income, caste  (normalised, or null)
  bucket_2_bonus  → open-ended life details that unlock hidden schemes
  bucket_3_missing→ names of core keys that are still null

Once Groq spits out that JSON, the AI's job is completely done. It shuts off.
Standard Python code takes over from here.
"""

import json
import os

from groq import AsyncGroq

REQUIRED_KEYS = ["grade", "caste", "income"]

SYSTEM_PROMPT = """\
You are a strict data-extraction engine for a Kerala scholarship system.

You will receive a student's message (already translated to English).
Your ONLY job: read the text and sort the information into three buckets.
Return ONLY a JSON object — no explanation, no markdown fences, no filler.

### Bucket definitions

**bucket_1_keys** — Mandatory filters for the scholarship database.
  • grade  — Current class/standard as a number string.
             Normalise: "plus two" → "12", "10th standard" → "10".
             If not mentioned → null.
  • caste  — Category code: "SC", "ST", "OBC", "General", "EWS",
             "OEC", "SEBC".  Normalise full names to codes.
             If not mentioned → null.
  • income — Family annual income as an integer (rupees).
             Normalise: "1 lakh" → 100000, "40,000" → 40000,
             "BPL" → 0 (below poverty line).
             If not mentioned → null.

**bucket_2_bonus** — Any extra life details the student mentions that
could match special scheme rules.  Examples: disability, single parent,
fisherman family, girl child, merit percentage, sport achievement,
daily-wage worker parent, specific district, religion, minority,
first-generation learner, orphan, etc.
Capture as short strings.  If nothing extra → empty list.

**bucket_3_missing** — List the NAMES of any bucket_1_keys that are null.
If all keys are filled → empty list.

### Output format (strict)
{
  "bucket_1_keys": { "grade": "...", "caste": "...", "income": ... },
  "bucket_2_bonus": ["...", "..."],
  "bucket_3_missing": ["...", "..."]
}
"""


def get_groq_api_key() -> str:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY environment variable is not set")
    return key


async def extract_buckets(text: str) -> dict:
    """
    Send a single translated message to Groq.
    Returns the three-bucket dict.
    """
    api_key = get_groq_api_key()
    client = AsyncGroq(api_key=api_key)

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=512,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {
            "bucket_1_keys": {"grade": None, "caste": None, "income": None},
            "bucket_2_bonus": [],
            "bucket_3_missing": list(REQUIRED_KEYS),
        }

    # Guarantee structural integrity
    keys = parsed.setdefault("bucket_1_keys", {})
    for k in REQUIRED_KEYS:
        keys.setdefault(k, None)
    parsed.setdefault("bucket_2_bonus", [])
    parsed.setdefault("bucket_3_missing", [])

    return parsed
