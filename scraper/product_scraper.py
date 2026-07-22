from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

from scraper.models import ProductData
from scraper.product_parser import analyze_printed, clean_text, filename_from_url, parse_price, parse_product_html


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

API_HEADERS = {
    "User-Agent": DEFAULT_HEADERS["User-Agent"],
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": DEFAULT_HEADERS["Accept-Language"],
}


def _origin_for(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def _slug_for(url: str) -> str | None:
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    if "product" in path_parts:
        index = path_parts.index("product")
        if len(path_parts) > index + 1:
            return path_parts[index + 1]
    return path_parts[-1] if path_parts else None


def fetch_html(url: str, timeout: int = 30) -> str:
    origin = _origin_for(url)
    with requests.Session() as session:
        session.headers.update(DEFAULT_HEADERS)

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
    try:
        return parse_product_html(fetch_html(url), url)
    except requests.RequestException:
        api_product = scrape_product_api(url)
        if api_product:
            api_product["source"] = "woocommerce_store_api"
            return api_product
        raise


def scrape_product_api(url: str, timeout: int = 30) -> dict[str, Any] | None:
    slug = _slug_for(url)
    if not slug:
        return None

    origin = _origin_for(url)
    endpoint = f"{origin}wp-json/wc/store/v1/products?slug={quote(slug)}"
    with requests.Session() as session:
        session.headers.update(API_HEADERS)
        response = session.get(endpoint, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        products = _json_from_response(response)
        if not isinstance(products, list) or not products:
            return None

        product = products[0]
        return _parse_store_api_product(product, url, session, timeout)


def _json_from_response(response: requests.Response) -> Any:
    return json.loads(response.content.decode("utf-8-sig"))


def _parse_store_api_product(product: dict[str, Any], url: str, session: requests.Session, timeout: int) -> dict[str, Any]:
    data = ProductData(url=url)
    data.title = clean_text(product.get("name"))
    data.sku = clean_text(product.get("sku"))
    data.tags = _names_from_items(product.get("tags"))
    data.categories = _names_from_items(product.get("categories"))
    data.short_description = _text_from_html(product.get("short_description"))
    data.review_count = int(product.get("review_count") or 0)
    data.base_price = _price_from_store_prices(product.get("prices")) or parse_price(product.get("price_html"))
    data.image_details = _image_details_from_api(product.get("images"))
    data.image_count = {"main": 1 if data.image_details else 0, "gallery": max(len(data.image_details) - 1, 0), "total": len(data.image_details)}
    data.long_description = _text_from_html(product.get("description"))
    data.description_headings = _headings_from_html(product.get("description"))
    data.additional_information = _attributes_from_api(product.get("attributes"))
    data.size_prices = _size_prices_from_api(product, session, timeout)
    data.global_form = _global_form_from_api_text(data.short_description, data.long_description, data.printed)
    data.printed = analyze_printed(data.sku)

    # global_form depends on printed status, so calculate it again after SKU analysis.
    data.global_form = _global_form_from_api_text(data.short_description, data.long_description, data.printed)
    return data.to_dict()


def _names_from_items(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    names: list[str] = []
    for item in items:
        name = clean_text(item.get("name") if isinstance(item, dict) else str(item))
        if name and name not in names:
            names.append(name)
    return names


def _text_from_html(raw_html: Any) -> str | None:
    if not raw_html:
        return None
    soup = BeautifulSoup(str(raw_html), "lxml")
    return clean_text(soup.get_text(" ", strip=True))


def _headings_from_html(raw_html: Any) -> list[str]:
    if not raw_html:
        return []
    soup = BeautifulSoup(str(raw_html), "lxml")
    headings: list[str] = []
    for heading in soup.select("h1, h2, h3, h4, h5, h6"):
        text = clean_text(heading.get_text(" ", strip=True))
        if text and text not in headings:
            headings.append(text)
    return headings


def _image_details_from_api(images: Any) -> list[dict[str, str | None]]:
    if not isinstance(images, list):
        return []
    details: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for image in images:
        if not isinstance(image, dict):
            continue
        src = clean_text(image.get("src"))
        if not src or src in seen:
            continue
        seen.add(src)
        details.append(
            {
                "src": src,
                "title": clean_text(image.get("name")),
                "alt": clean_text(image.get("alt")),
                "filename": filename_from_url(src),
            }
        )
    return details


def _attributes_from_api(attributes: Any) -> dict[str, str]:
    info: dict[str, str] = {}
    if not isinstance(attributes, list):
        return info
    for attribute in attributes:
        if not isinstance(attribute, dict):
            continue
        name = clean_text(attribute.get("name"))
        terms = attribute.get("terms") or []
        values = _names_from_items(terms)
        if name and values:
            info[name] = ", ".join(values)
    return info


def _price_from_store_prices(prices: Any) -> float | None:
    if not isinstance(prices, dict):
        return None
    raw = prices.get("price") or prices.get("sale_price") or prices.get("regular_price")
    minor_unit = int(prices.get("currency_minor_unit") or 2)
    try:
        return int(raw) / (10 ** minor_unit)
    except (TypeError, ValueError):
        return None


def _size_prices_from_api(product: dict[str, Any], session: requests.Session, timeout: int) -> list[dict[str, Any]]:
    variations = product.get("variations") or []
    if not isinstance(variations, list):
        return []

    size_prices: list[dict[str, Any]] = []
    origin = _origin_for(product.get("permalink") or "https://replicafootballshirt.com/")
    for variation in variations:
        if not isinstance(variation, dict):
            continue
        variation_id = variation.get("id")
        size = _variation_size(variation)
        detail = _fetch_variation_detail(origin, variation_id, session, timeout) if variation_id else {}
        sku = clean_text(detail.get("sku")) or _infer_variation_sku(product.get("sku"), size)
        price = _price_from_store_prices(detail.get("prices")) or _price_from_store_prices(product.get("prices"))
        regular_price = None
        if isinstance(detail.get("prices"), dict):
            regular_price = _store_amount_to_float(detail["prices"].get("regular_price"), detail["prices"].get("currency_minor_unit"))

        if size or sku or price is not None:
            size_prices.append(
                {
                    "size": _display_size(size),
                    "sku": sku,
                    "price": price,
                    "regular_price": regular_price,
                    "variation_id": variation_id,
                    "in_stock": detail.get("is_in_stock"),
                }
            )
    return size_prices


def _fetch_variation_detail(origin: str, variation_id: Any, session: requests.Session, timeout: int) -> dict[str, Any]:
    try:
        response = session.get(f"{origin}wp-json/wc/store/v1/products/{variation_id}", timeout=min(timeout, 12), allow_redirects=True)
        if response.status_code != 200:
            return {}
        detail = _json_from_response(response)
        return detail if isinstance(detail, dict) else {}
    except requests.RequestException:
        return {}


def _variation_size(variation: dict[str, Any]) -> str | None:
    attrs = variation.get("attributes") or []
    if not isinstance(attrs, list):
        return None
    for attr in attrs:
        if not isinstance(attr, dict):
            continue
        if clean_text(attr.get("name")) and "size" in clean_text(attr.get("name")).lower():
            return clean_text(attr.get("value"))
    return None


def _display_size(size: str | None) -> str:
    if not size:
        return "unknown"
    text = str(size).strip()
    match = re.match(r"^(\d+)-(\d+)-(\d+)-yrs$", text, flags=re.I)
    if match:
        return f"{match.group(1)} ({match.group(2)}-{match.group(3)} yrs)"
    return text.upper()


def _infer_variation_sku(base_sku: Any, size: str | None) -> str | None:
    base = clean_text(base_sku)
    display = _display_size(size)
    if not base or display == "unknown":
        return base
    return f"{base}_{display}"


def _store_amount_to_float(value: Any, minor_unit: Any = 2) -> float | None:
    try:
        return int(value) / (10 ** int(minor_unit or 2))
    except (TypeError, ValueError):
        return None


def _global_form_from_api_text(short_description: str | None, long_description: str | None, printed: dict[str, Any]) -> list[dict[str, Any]]:
    text = " ".join([short_description or "", long_description or ""]).lower()
    options: list[dict[str, Any]] = []
    if "personalisation" in text or "personalization" in text or "personalise" in text:
        options.append(
            {
                "name": "personalise",
                "label": "Personalise For 10£",
                "type": "radio",
                "values": ["Yes(+ 10£)", "No"],
                "price": 10.0,
                "source": "woocommerce_store_api_description_inference",
            }
        )
    return options


def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
