from __future__ import annotations

from urllib.parse import urlparse

import requests

from scraper.product_parser import parse_product_html


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}


def _origin_for(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def fetch_html(url: str, timeout: int = 30) -> str:
    origin = _origin_for(url)
    with requests.Session() as session:
        session.headers.update(DEFAULT_HEADERS)

        # Some storefront security layers allow product pages only after a normal
        # browser-like visit has established basic cookies for the domain.
        try:
            session.get(origin, timeout=min(timeout, 15), allow_redirects=True)
        except requests.RequestException:
            pass

        headers = {"Referer": origin}
        response = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if response.status_code == 403:
            retry_headers = {
                "Referer": origin,
                "Sec-Fetch-Site": "none",
            }
            response = session.get(url, headers=retry_headers, timeout=timeout, allow_redirects=True)

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            if response.status_code == 403:
                raise requests.HTTPError(
                    "403 Forbidden while fetching product page. The source site may be blocking the server IP."
                ) from exc
            raise
        return response.text


def scrape_product(url: str) -> dict:
    return parse_product_html(fetch_html(url), url)


def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
