"""Scraper: myScheme.gov.in — Central + State Government scholarships.

Strategy
--------
myScheme is a Next.js app. The search page at /search/scholarship embeds
scheme listings in __NEXT_DATA__. We also crawl individual scheme pages
at /schemes/{slug} for full details.

Legal: All data is publicly visible — no login, no CAPTCHA bypass.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from scrapers.base import fetch_page, extract_next_data, clean_text, get_client
from data.models import Scholarship

# Known Kerala-relevant scholarship slugs on myScheme.
# These are the publicly listed scheme URLs.
# We start with a curated seed list and can expand later.
_KERALA_SCHEME_SLUGS = [
    "e-grantz",
    "post-matric-scholarship-for-sc-students-kerala",
    "pre-matric-scholarship-for-sc-students-kerala",
    "post-matric-scholarship-for-obc-students-kerala",
    "pre-matric-scholarship-for-obc-students-kerala",
    "merit-cum-means-scholarship-for-minority-students",
    "central-sector-scheme-of-scholarship",
    "pragathi-scholarship-for-girl-students",
    "saksham-scholarship-for-differently-abled-students",
    "national-means-cum-merit-scholarship-scheme",
    "pm-yasasvi-pre-matric-scholarship",
    "pm-yasasvi-post-matric-scholarship",
    "pm-yasasvi-top-class-scholarship",
    "begum-hazrat-mahal-national-scholarship",
]

_BASE = "https://www.myscheme.gov.in"


async def scrape_myscheme() -> list[Scholarship]:
    """Scrape scholarship details from myScheme.gov.in."""
    print("[scraper:myscheme] Starting scrape...")
    results: list[Scholarship] = []

    async with get_client() as client:
        tasks = [
            _scrape_scheme_page(client, slug) for slug in _KERALA_SCHEME_SLUGS
        ]
        settled = await asyncio.gather(*tasks, return_exceptions=True)

        for slug, result in zip(_KERALA_SCHEME_SLUGS, settled):
            if isinstance(result, Exception):
                print(f"[scraper:myscheme] ⚠ Failed {slug}: {result}")
            elif result is not None:
                results.append(result)

    print(f"[scraper:myscheme] Done — {len(results)} scholarships scraped")
    return results


async def _scrape_scheme_page(
    client, slug: str
) -> Scholarship | None:
    """Fetch a single scheme detail page and parse it."""
    url = f"{_BASE}/schemes/{slug}"
    try:
        html = await fetch_page(url, client)
    except Exception as e:
        print(f"[scraper:myscheme] Could not fetch {url}: {e}")
        return None

    data = extract_next_data(html)
    props = data.get("props", {}).get("pageProps", {})
    scheme = props.get("schemeData", props.get("data", {}))

    if not scheme:
        # Fallback: try parsing basic info from HTML
        return _parse_html_fallback(html, url, slug)

    name = scheme.get("schemeName", scheme.get("title", slug))
    description = clean_text(scheme.get("schemeDescription", scheme.get("description", "")))
    benefits = clean_text(scheme.get("schemeBenefits", scheme.get("benefits", "")))

    # Extract eligibility hints
    eligibility_text = clean_text(
        scheme.get("schemeEligibility", scheme.get("eligibility", ""))
    )

    grade = _extract_grade(eligibility_text)
    caste = _extract_caste(eligibility_text, name)
    income = _extract_income(eligibility_text)
    tags = _extract_tags(eligibility_text, description, name)

    return Scholarship(
        name=name,
        source="myscheme",
        description=description[:500],
        eligibility_grade=grade,
        eligibility_caste=caste,
        eligibility_income_max=income,
        benefits=benefits[:300],
        url=url,
        tags=tags,
        last_updated=datetime.utcnow(),
    )


def _parse_html_fallback(html: str, url: str, slug: str) -> Scholarship | None:
    """Parse basic scheme info from raw HTML when __NEXT_DATA__ is sparse."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1") or soup.find("title")
    name = title_tag.get_text(strip=True) if title_tag else slug.replace("-", " ").title()

    # Grab all visible text for keyword extraction
    body_text = soup.get_text(" ", strip=True)

    return Scholarship(
        name=name,
        source="myscheme",
        description=body_text[:500],
        eligibility_grade=_extract_grade(body_text),
        eligibility_caste=_extract_caste(body_text, name),
        eligibility_income_max=_extract_income(body_text),
        benefits="",
        url=url,
        tags=_extract_tags(body_text, "", name),
        last_updated=datetime.utcnow(),
    )


# ── Extraction helpers ────────────────────────────────────────


def _extract_grade(text: str) -> str | None:
    """Try to find class/standard requirements."""
    import re

    text_lower = text.lower()
    if "post-matric" in text_lower or "post matric" in text_lower:
        return "11"  # Post-matric = class 11+
    if "pre-matric" in text_lower or "pre matric" in text_lower:
        return "1"  # Pre-matric = class 1-10
    # Look for "class X" or "standard X"
    match = re.search(r"(?:class|standard|grade)\s*(\d{1,2})", text_lower)
    if match:
        return match.group(1)
    return None


def _extract_caste(text: str, name: str) -> str | None:
    """Try to find caste category requirements."""
    combined = f"{name} {text}".upper()
    for code in ["SC", "ST", "OBC", "EWS", "OEC", "SEBC"]:
        if code in combined.split() or f"/{code}" in combined or f"{code}/" in combined:
            return code
    if "MINORITY" in combined:
        return "OBC"  # Most minority scholarships map to OBC/minority
    if "GENERAL" in combined:
        return "General"
    return None


def _extract_income(text: str) -> int | None:
    """Try to find income ceiling."""
    import re

    text_lower = text.lower()
    # Match patterns like "2.5 lakh", "250000", "2,50,000"
    match = re.search(r"(\d[\d,.]*)\s*(?:lakh|lac)", text_lower)
    if match:
        num = float(match.group(1).replace(",", ""))
        return int(num * 100_000)

    match = re.search(r"₹?\s*(\d{4,7}(?:,\d{2,3})*)", text_lower)
    if match:
        num = int(match.group(1).replace(",", ""))
        if num >= 10000:  # Likely an income value
            return num

    return None


def _extract_tags(eligibility: str, description: str, name: str) -> list[str]:
    """Extract bonus matching tags from scheme text."""
    combined = f"{name} {eligibility} {description}".lower()
    tags = []

    tag_keywords = {
        "girl child": ["girl", "female", "women", "pragathi"],
        "disability": ["disabled", "differently abled", "saksham", "handicap", "pwd"],
        "minority": ["minority", "muslim", "christian", "sikh", "buddhist", "jain", "parsi"],
        "merit": ["merit", "meritorious", "top class", "topper"],
        "BPL": ["bpl", "below poverty", "poverty line"],
        "single parent": ["single parent", "single mother", "widow"],
        "orphan": ["orphan"],
        "first generation": ["first generation", "first-generation"],
        "fisherman family": ["fisherman", "fishing", "fisheries"],
        "Kerala": ["kerala"],
    }

    for tag, keywords in tag_keywords.items():
        if any(kw in combined for kw in keywords):
            tags.append(tag)

    return tags
