"""Scraper: Buddy4Study — Corporate/private scholarships.

Strategy
--------
Buddy4Study is a Next.js app. We fetch scholarship listing and detail pages,
extracting data from the __NEXT_DATA__ JSON blob or from rendered HTML.

We focus on Kerala-relevant and nationally-available scholarships.

Legal: All pages are publicly accessible — no login required.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from scrapers.base import fetch_page, extract_next_data, clean_text, get_client
from data.models import Scholarship

# State and category pages relevant to Kerala students
_LISTING_URLS = [
    "https://www.buddy4study.com/scholarships/kerala",
    "https://www.buddy4study.com/scholarships/nsp",
    "https://www.buddy4study.com/scholarships/girls",
    "https://www.buddy4study.com/scholarships/minority",
    "https://www.buddy4study.com/scholarships/physically-disabled",
    "https://www.buddy4study.com/scholarships/means-based",
]

_BASE = "https://www.buddy4study.com"


async def scrape_buddy4study() -> list[Scholarship]:
    """Scrape scholarship data from Buddy4Study."""
    print("[scraper:buddy4study] Starting scrape...")

    all_slugs: set[str] = set()
    results: list[Scholarship] = []

    async with get_client() as client:
        # Step 1: Gather scholarship slugs from listing pages
        listing_tasks = [fetch_page(url, client) for url in _LISTING_URLS]
        listing_results = await asyncio.gather(*listing_tasks, return_exceptions=True)

        for url, html_or_err in zip(_LISTING_URLS, listing_results):
            if isinstance(html_or_err, Exception):
                print(f"[scraper:buddy4study] ⚠ Failed listing {url}: {html_or_err}")
                continue
            slugs = _extract_slugs_from_listing(html_or_err)
            all_slugs.update(slugs)
            print(f"[scraper:buddy4study] Found {len(slugs)} scholarships on {url}")

        if not all_slugs:
            print("[scraper:buddy4study] No scholarship slugs found, skipping detail fetch")
            return []

        # Step 2: Fetch individual scholarship details
        # Limit concurrency to be polite
        sem = asyncio.Semaphore(5)
        detail_tasks = [
            _fetch_with_semaphore(sem, client, slug) for slug in all_slugs
        ]
        detail_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

        for slug, result in zip(all_slugs, detail_results):
            if isinstance(result, Exception):
                print(f"[scraper:buddy4study] ⚠ Failed detail {slug}: {result}")
            elif result is not None:
                results.append(result)

    print(f"[scraper:buddy4study] Done — {len(results)} scholarships scraped")
    return results


async def _fetch_with_semaphore(
    sem: asyncio.Semaphore, client, slug: str
) -> Scholarship | None:
    async with sem:
        return await _scrape_scholarship_page(client, slug)


def _extract_slugs_from_listing(html: str) -> list[str]:
    """Extract scholarship slugs from a Buddy4Study listing page."""
    from bs4 import BeautifulSoup

    slugs = []
    soup = BeautifulSoup(html, "html.parser")

    # Method 1: Extract from __NEXT_DATA__
    data = extract_next_data(html)
    props = data.get("props", {}).get("pageProps", {})

    # Try common prop keys for listings
    for key in ["scholarships", "data", "results", "scholarshipList"]:
        items = props.get(key, [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    slug = item.get("slug", item.get("url", ""))
                    if slug and "/" not in slug:
                        slugs.append(slug)
                    elif slug and slug.startswith("/scholarship/"):
                        slugs.append(slug.split("/")[-1])

    # Method 2: Extract from HTML links
    if not slugs:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/scholarship/" in href and href.count("/") <= 3:
                slug = href.rstrip("/").split("/")[-1]
                if slug and slug != "scholarship":
                    slugs.append(slug)

    return list(set(slugs))


async def _scrape_scholarship_page(client, slug: str) -> Scholarship | None:
    """Fetch and parse a single Buddy4Study scholarship detail page."""
    url = f"{_BASE}/scholarship/{slug}"
    try:
        html = await fetch_page(url, client)
    except Exception as e:
        print(f"[scraper:buddy4study] Could not fetch {url}: {e}")
        return None

    # Try __NEXT_DATA__ first
    data = extract_next_data(html)
    props = data.get("props", {}).get("pageProps", {})
    scholarship_data = props.get("scholarshipData", props.get("data", {}))

    if isinstance(scholarship_data, dict) and scholarship_data:
        return _parse_next_data(scholarship_data, url)

    # Fallback to HTML parsing
    return _parse_html(html, url, slug)


def _parse_next_data(data: dict, url: str) -> Scholarship:
    """Parse scholarship from __NEXT_DATA__ JSON."""
    name = data.get("title", data.get("name", "Unknown"))
    description = clean_text(data.get("description", data.get("about", "")))
    benefits = clean_text(data.get("benefits", data.get("award", "")))
    eligibility = clean_text(data.get("eligibility", ""))

    grade = _extract_grade(eligibility)
    caste = _extract_caste(eligibility, name)
    income = _extract_income(eligibility)
    tags = _extract_tags(eligibility, description, name)

    return Scholarship(
        name=name,
        source="buddy4study",
        description=description[:500],
        eligibility_grade=grade,
        eligibility_caste=caste,
        eligibility_income_max=income,
        benefits=benefits[:300],
        url=url,
        tags=tags,
        last_updated=datetime.utcnow(),
    )


def _parse_html(html: str, url: str, slug: str) -> Scholarship | None:
    """Fallback: parse scholarship from raw HTML."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1") or soup.find("title")
    if not title_tag:
        return None

    name = title_tag.get_text(strip=True)
    if "not found" in name.lower() or "error" in name.lower():
        return None

    body_text = soup.get_text(" ", strip=True)

    return Scholarship(
        name=name,
        source="buddy4study",
        description=body_text[:500],
        eligibility_grade=_extract_grade(body_text),
        eligibility_caste=_extract_caste(body_text, name),
        eligibility_income_max=_extract_income(body_text),
        benefits="",
        url=url,
        tags=_extract_tags(body_text, "", name),
        last_updated=datetime.utcnow(),
    )


# ── Extraction helpers (shared patterns) ─────────────────────

def _extract_grade(text: str) -> str | None:
    import re
    text_lower = text.lower()
    if "post-matric" in text_lower or "post matric" in text_lower:
        return "11"
    if "pre-matric" in text_lower or "pre matric" in text_lower:
        return "1"
    match = re.search(r"(?:class|standard|grade)\s*(\d{1,2})", text_lower)
    if match:
        return match.group(1)
    if "graduation" in text_lower or "under graduate" in text_lower:
        return "UG"
    if "post graduation" in text_lower:
        return "PG"
    return None


def _extract_caste(text: str, name: str) -> str | None:
    combined = f"{name} {text}".upper()
    for code in ["SC", "ST", "OBC", "EWS", "OEC", "SEBC"]:
        if code in combined.split() or f"/{code}" in combined or f"{code}/" in combined:
            return code
    if "MINORITY" in combined:
        return "OBC"
    return None


def _extract_income(text: str) -> int | None:
    import re
    text_lower = text.lower()
    match = re.search(r"(\d[\d,.]*)\s*(?:lakh|lac)", text_lower)
    if match:
        num = float(match.group(1).replace(",", ""))
        return int(num * 100_000)
    match = re.search(r"₹?\s*(\d{4,7}(?:,\d{2,3})*)", text_lower)
    if match:
        num = int(match.group(1).replace(",", ""))
        if num >= 10000:
            return num
    return None


def _extract_tags(eligibility: str, description: str, name: str) -> list[str]:
    combined = f"{name} {eligibility} {description}".lower()
    tags = []
    tag_keywords = {
        "girl child": ["girl", "female", "women"],
        "disability": ["disabled", "differently abled", "handicap", "pwd"],
        "minority": ["minority", "muslim", "christian"],
        "merit": ["merit", "meritorious", "topper"],
        "BPL": ["bpl", "below poverty"],
        "single parent": ["single parent", "widow"],
        "orphan": ["orphan"],
        "first generation": ["first generation", "first-generation"],
        "Kerala": ["kerala"],
    }
    for tag, keywords in tag_keywords.items():
        if any(kw in combined for kw in keywords):
            tags.append(tag)
    return tags
