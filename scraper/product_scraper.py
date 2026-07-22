from __future__ import annotations

from urllib.parse import urlparse

import requests

from scraper.product_parser import parse_product_html


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_html(url: str, timeout: int = 12) -> str:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=(4, timeout))
    response.raise_for_status()
    return response.text


def scrape_product(url: str) -> dict:
    return parse_product_html(fetch_html(url), url)


def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
