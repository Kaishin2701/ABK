from __future__ import annotations

import os
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


def proxy_config() -> dict[str, str] | None:
    proxy_url = os.environ.get("SCRAPER_PROXY_URL", "").strip()
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}


def _origin_for(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def fetch_html(url: str, timeout: int = 30) -> str:
    origin = _origin_for(url)
    proxies = proxy_config()
    with requests.Session() as session:
        session.headers.update(DEFAULT_HEADERS)

        try:
            session.get(origin, timeout=min(timeout, 15), allow_redirects=True, proxies=proxies)
        except requests.RequestException:
            pass

        headers = {"Referer": origin}
        response = session.get(url, headers=headers, timeout=timeout, allow_redirects=True, proxies=proxies)
        if response.status_code == 403:
            retry_headers = {"Referer": origin, "Sec-Fetch-Site": "none"}
            response = session.get(url, headers=retry_headers, timeout=timeout, allow_redirects=True, proxies=proxies)

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            if response.status_code == 403:
                hint = (
                    "403 Forbidden while fetching product page through SCRAPER_PROXY_URL. "
                    "The proxy IP is also blocked by the source site."
                    if proxies
                    else "403 Forbidden while fetching product page. Set SCRAPER_PROXY_URL to use an approved proxy/VPN IP."
                )
                raise requests.HTTPError(hint) from exc
            raise
        return response.text


def scrape_product(url: str) -> dict:
    return parse_product_html(fetch_html(url), url)


def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

