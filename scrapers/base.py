"""Shared scraper utilities — HTTP client config and HTML helpers."""

from __future__ import annotations

import json
import re

import httpx
from bs4 import BeautifulSoup

# Polite defaults — we're not a bot farm
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def get_client() -> httpx.AsyncClient:
    """Return a configured async HTTP client."""
    return httpx.AsyncClient(
        headers=_HEADERS,
        timeout=_TIMEOUT,
        follow_redirects=True,
    )


async def fetch_page(url: str, client: httpx.AsyncClient | None = None) -> str:
    """Fetch a URL and return the HTML body as a string."""
    if client is None:
        async with get_client() as c:
            resp = await c.get(url)
            resp.raise_for_status()
            return resp.text
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.text


def extract_next_data(html: str) -> dict:
    """
    Pull the __NEXT_DATA__ JSON blob from a Next.js page.

    Next.js embeds all page props in a <script id="__NEXT_DATA__"> tag.
    Returns the parsed dict, or {} if not found.
    """
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag and tag.string:
        try:
            return json.loads(tag.string)
        except json.JSONDecodeError:
            return {}
    return {}


def clean_text(text: str | None) -> str:
    """Strip HTML tags and normalise whitespace."""
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean
