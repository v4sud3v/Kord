"""NLP service — tokenize transcripts, extract structured fields, and embed."""

import re

import nltk
import numpy as np
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer


# ---------------------------------------------------------------------------
# 1. Tokenisation
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """
    Word-tokenize the transcript and strip out punctuation-only tokens.
    Returns a list of lowercased tokens.
    """
    tokens = word_tokenize(text)
    # keep only alphanumeric tokens, lowercase
    return [t.lower() for t in tokens if re.search(r"\w", t)]


def remove_stopwords(tokens: list[str]) -> list[str]:
    """Remove English stopwords (the transcript is already translated to English)."""
    stop = set(stopwords.words("english"))
    return [t for t in tokens if t not in stop]


# ---------------------------------------------------------------------------
# 2. Detail Extraction  (regex-based, tuned for Kord's use-case)
# ---------------------------------------------------------------------------

# Patterns that match the kind of info a Kerala student would mention
_PATTERNS: dict[str, re.Pattern] = {
    "age": re.compile(
        r"(?:i(?:'m| am)\s+|age\s*(?:is)?\s*|(\d{1,2})\s*years?\s*old)"
        r"(\d{1,2})",
        re.IGNORECASE,
    ),
    "standard": re.compile(
        r"(?:(\d{1,2})(?:th|st|nd|rd)?\s*(?:standard|std|class|grade))"
        r"|(?:(?:standard|std|class|grade)\s*(\d{1,2}))",
        re.IGNORECASE,
    ),
    "income": re.compile(
        r"(?:income|earning|salary|bpl|below poverty|apl|above poverty"
        r"|(?:rs\.?\s*\d[\d,]*))",
        re.IGNORECASE,
    ),
    "caste": re.compile(
        r"\b(obc|sc|st|general|ews|obh|oec|sebc"
        r"|scheduled\s*(?:caste|tribe)"
        r"|other\s*backward\s*class"
        r"|economically\s*weaker\s*section)\b",
        re.IGNORECASE,
    ),
    "location": re.compile(
        # common Kerala district / city names (expandable)
        r"\b(thiruvananthapuram|kochi|kozhikode|thrissur|kollam"
        r"|palakkad|alappuzha|kannur|kottayam|malappuram"
        r"|pathanamthitta|idukki|wayanad|kasaragod|ernakulam"
        r"|kanayannur|trivandrum|calicut|cochin"
        r"|kerala)\b",
        re.IGNORECASE,
    ),
}


def extract_details(text: str) -> dict[str, str | None]:
    """
    Run every pattern against the raw transcript and return a dict of
    extracted fields.  Value is the first match string or None.
    """
    details: dict[str, str | None] = {}

    # --- age ---
    age_match = _PATTERNS["age"].search(text)
    if age_match:
        # group(1) or group(2) holds the digits depending on phrasing
        details["age"] = next(
            (g for g in age_match.groups() if g and g.isdigit()), None
        )
    else:
        # fallback: look for bare numbers in age-likely range
        nums = re.findall(r"\b(\d{1,2})\b", text)
        details["age"] = next(
            (n for n in nums if 10 <= int(n) <= 25), None
        )

    # --- standard / class ---
    std_match = _PATTERNS["standard"].search(text)
    if std_match:
        details["standard"] = next(
            (g for g in std_match.groups() if g), None
        )
    else:
        details["standard"] = None

    # --- income ---
    inc_match = _PATTERNS["income"].search(text)
    details["income"] = inc_match.group(0).strip() if inc_match else None

    # --- caste category ---
    caste_match = _PATTERNS["caste"].search(text)
    details["caste"] = caste_match.group(0).strip() if caste_match else None

    # --- location ---
    loc_match = _PATTERNS["location"].search(text)
    details["location"] = loc_match.group(0).strip() if loc_match else None

    return details


# ---------------------------------------------------------------------------
# 3. Embedding  (TF-IDF vectors via scikit-learn + numpy)
# ---------------------------------------------------------------------------

# A module-level vectorizer that learns vocabulary incrementally per call.
# For a production system you'd fit once on a corpus; here we fit per-request
# so it works standalone.

def embed_tokens(tokens: list[str]) -> np.ndarray:
    """
    Convert a list of tokens into a TF-IDF vector.
    Returns a 1-D numpy array (the embedding).
    """
    if not tokens:
        return np.array([])

    # TfidfVectorizer expects documents (strings), so we join tokens back
    doc = " ".join(tokens)
    vectorizer = TfidfVectorizer()
    # fit_transform on single doc + a tiny dummy so IDF isn't degenerate
    matrix = vectorizer.fit_transform([doc, ""])
    vector = matrix[0].toarray().flatten()
    return vector


# ---------------------------------------------------------------------------
# 4. Pipeline  — single entry-point for the webhook
# ---------------------------------------------------------------------------

def process_transcript(transcript: str) -> dict:
    """
    Full NLP pipeline:
      1. tokenize
      2. remove stopwords
      3. extract structured details
      4. embed cleaned tokens into a vector

    Returns a dict with tokens, cleaned_tokens, extracted details, and
    the embedding vector.
    """
    # 1 — tokenize
    tokens = tokenize(transcript)

    # 2 — clean tokens
    cleaned = remove_stopwords(tokens)

    # 3 — extract structured details
    details = extract_details(transcript)

    # 4 — embed
    vector = embed_tokens(cleaned)

    return {
        "tokens": tokens,
        "cleaned_tokens": cleaned,
        "details": details,
        "embedding": vector,
    }


# ---------------------------------------------------------------------------
# Pretty-print helper (used by the webhook for terminal output)
# ---------------------------------------------------------------------------

def print_nlp_results(result: dict) -> None:
    """Print the NLP pipeline output in a readable format."""
    print("\n" + "=" * 60)
    print("  NLP PIPELINE RESULTS")
    print("=" * 60)

    print(f"\n📝 Tokens ({len(result['tokens'])}):")
    print(f"   {result['tokens']}")

    print(f"\n🧹 Cleaned tokens (stopwords removed) ({len(result['cleaned_tokens'])}):")
    print(f"   {result['cleaned_tokens']}")

    print("\n🔍 Extracted Details:")
    for key, value in result["details"].items():
        status = f"✅ {value}" if value else "❌ not found"
        print(f"   {key:>10}: {status}")

    vec = result["embedding"]
    print(f"\n📐 Embedding vector (shape={vec.shape}, dtype={vec.dtype}):")
    # show first 10 values so terminal isn't flooded
    if vec.size > 10:
        print(f"   {vec[:10]}  ... ({vec.size} dimensions total)")
    else:
        print(f"   {vec}")

    print("=" * 60 + "\n")
