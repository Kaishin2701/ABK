from __future__ import annotations

import html
import json
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scraper.models import ProductData


DESCRIPTION_SELECTORS = [
    "#tab-description .tab-content-wrapper",
    "#tab-content-description .tab-content-wrapper",
    "#tab-description",
    "#tab-content-description",
    ".woocommerce-Tabs-panel--description",
    ".tab-content-description .tab-content-wrapper",
    ".product-long-description",
]


def parse_product_html(page_html: str, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(page_html, "lxml")
    product = ProductData(url=url)

    product.title = first_text(
        soup,
        ["h1.product_title", "h1.entry-title", "h1", 'meta[property="og:title"]'],
    )
    product.sku = first_text(soup, [".sku", '[itemprop="sku"]'])
    product.tags = link_texts(soup, [".tagged_as a", ".product_meta a[rel='tag']"])
    product.categories = extract_categories(soup)
    product.short_description = first_text(
        soup,
        [
            ".woocommerce-product-details__short-description",
            ".summary .short-description",
            '[itemprop="description"]',
        ],
    )
    product.review_count = extract_review_count(soup)
    product.base_price = extract_base_price(soup)
    product.size_prices = extract_size_prices(soup)
    product.global_form = extract_global_form(soup)
    product.image_details = extract_image_details(soup)
    product.image_count = count_images(product.image_details)
    product.long_description = extract_long_description(soup)
    product.description_headings = extract_description_headings(soup)
    product.additional_information = extract_additional_information(soup)
    product.printed = analyze_printed(product.sku)

    return product.to_dict()


def first_text(soup: BeautifulSoup, selectors: list[str]) -> str | None:
    for selector in selectors:
        element = soup.select_one(selector)
        if not element:
            continue
        text = element.get("content") if element.name == "meta" else element.get_text(" ", strip=True)
        text = clean_text(text)
        if text:
            return text
    return None


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", html.unescape(value)).strip()
    return text or None


def link_texts(soup: BeautifulSoup, selectors: list[str]) -> list[str]:
    values: list[str] = []
    for selector in selectors:
        for element in soup.select(selector):
            text = clean_text(element.get_text(" ", strip=True))
            if text and text not in values:
                values.append(text)
    return values


def extract_categories(soup: BeautifulSoup) -> list[str]:
    categories = link_texts(soup, [".posted_in a", ".product_meta a[rel='category']"])
    if categories:
        return categories

    gtm_data = extract_gtm_product_data(soup)
    category = clean_text(gtm_data.get("item_category") if gtm_data else None)
    return [category] if category else []


def extract_review_count(soup: BeautifulSoup) -> int:
    candidates = []
    for selector in [".woocommerce-review-link", ".woocommerce-review-count", ".reviews_tab a"]:
        candidates.extend(element.get_text(" ", strip=True) for element in soup.select(selector))

    for text in candidates:
        match = re.search(r"(\d+)", text)
        if match:
            return int(match.group(1))
    return 0


def extract_base_price(soup: BeautifulSoup) -> float | None:
    gtm_data = extract_gtm_product_data(soup)
    if gtm_data and isinstance(gtm_data.get("price"), (int, float)):
        return float(gtm_data["price"])

    price_text = first_text(soup, [".summary .price", "p.price", ".price"])
    return parse_price(price_text)


def extract_size_prices(soup: BeautifulSoup) -> list[dict[str, Any]]:
    form = soup.select_one("form.variations_form")
    if not form:
        return []

    raw_variations = form.get("data-product_variations")
    if not raw_variations:
        return []

    try:
        variations = json.loads(html.unescape(raw_variations))
    except json.JSONDecodeError:
        return []

    size_prices: list[dict[str, Any]] = []
    for variation in variations:
        attributes = variation.get("attributes") or {}
        size = (
            attributes.get("attribute_pa_size")
            or attributes.get("attribute_size")
            or first_attribute_value(attributes, "size")
        )
        if not size:
            continue

        size_prices.append(
            {
                "size": str(size).upper(),
                "sku": clean_text(variation.get("sku")),
                "price": number_or_none(variation.get("display_price")),
                "regular_price": number_or_none(variation.get("display_regular_price")),
                "variation_id": variation.get("variation_id"),
                "in_stock": variation.get("is_in_stock"),
            }
        )

    return size_prices


def extract_global_form(soup: BeautifulSoup) -> list[dict[str, Any]]:
    form = soup.select_one("form.cart")
    if not form:
        return []

    options: list[dict[str, Any]] = []
    for field in form.select("select, input[type='checkbox'], input[type='radio'], textarea"):
        name = field.get("name")
        if not name or is_internal_field(name):
            continue

        option = {
            "name": name,
            "label": field_label(field),
            "type": field.name if field.name != "input" else field.get("type", "input"),
            "values": field_values(field),
            "price": field_price(field),
        }
        if option not in options:
            options.append(option)

    return options


def extract_image_details(soup: BeautifulSoup) -> list[dict[str, str | None]]:
    images: list[dict[str, str | None]] = []
    seen_sources: set[str] = set()

    for image in soup.select(".woocommerce-product-gallery img, .product-images img"):
        src = image.get("data-large_image") or image.get("data-src") or image.get("src")
        if not src or src in seen_sources:
            continue

        seen_sources.add(src)
        wrapper = image.find_parent(class_="swiper-slide") or image.find_parent("div")
        images.append(
            {
                "src": src,
                "title": image_title(image, wrapper),
                "alt": clean_text(image.get("alt")),
                "filename": filename_from_url(src),
            }
        )

    return images


def count_images(images: list[dict[str, str | None]]) -> dict[str, int]:
    total = len(images)
    return {"main": 1 if total else 0, "gallery": max(total - 1, 0), "total": total}


def image_title(image: Any, wrapper: Any) -> str | None:
    if wrapper:
        raw_sub_html = wrapper.get("data-sub-html")
        if raw_sub_html:
            sub_soup = BeautifulSoup(html.unescape(raw_sub_html), "lxml")
            text = clean_text(sub_soup.get_text(" ", strip=True))
            if text:
                return text

        for attr in ["title", "aria-label"]:
            text = clean_text(wrapper.get(attr))
            if text:
                return text

    return clean_text(image.get("title"))


def filename_from_url(url: str) -> str | None:
    path = urlparse(url).path
    return clean_text(path.rsplit("/", 1)[-1])


def extract_long_description(soup: BeautifulSoup) -> str | None:
    for selector in DESCRIPTION_SELECTORS:
        panel = soup.select_one(selector)
        if not panel:
            continue

        clone = BeautifulSoup(str(panel), "lxml")
        content = clone.select_one(selector) or clone
        for title in content.select(".tab-title, .entry-product-section-heading, .product-information-heading"):
            title.decompose()

        text = clean_text(content.get_text(" ", strip=True))
        if text:
            return text

    return None


def extract_description_headings(soup: BeautifulSoup) -> list[str]:
    headings: list[str] = []
    for selector in DESCRIPTION_SELECTORS:
        panel = soup.select_one(selector)
        if not panel:
            continue

        for heading in panel.select("h1, h2, h3, h4, h5, h6"):
            text = clean_text(heading.get_text(" ", strip=True))
            if text and text not in headings:
                headings.append(text)
        if headings:
            return headings

    return headings


def extract_additional_information(soup: BeautifulSoup) -> dict[str, str]:
    panel = soup.select_one(
        "#tab-additional_information, #tab-content-additional_information, "
        ".woocommerce-Tabs-panel--additional_information, .tab-content-additional_information"
    )
    if not panel:
        return {}

    info: dict[str, str] = {}
    for row in panel.select("tr"):
        key_node = row.select_one("th")
        value_node = row.select_one("td")
        key = clean_text(key_node.get_text(" ", strip=True) if key_node else None)
        value = clean_text(value_node.get_text(" ", strip=True) if value_node else None)
        if key and value:
            info[key] = value

    if info:
        return info

    text = clean_text(panel.get_text(" ", strip=True))
    return {"text": text} if text else {}


def analyze_printed(sku: str | None) -> dict[str, Any]:
    clean_sku = clean_text(sku)
    if not clean_sku:
        return {
            "is_printed": None,
            "content": None,
            "source": "sku",
            "reason": "No SKU is available to identify printed status.",
        }

    parts = [part.strip() for part in clean_sku.split("_") if part.strip()]
    has_no_token = any(part.lower() == "no" for part in parts)
    return {
        "is_printed": not has_no_token,
        "content": None,
        "source": "sku",
        "reason": (
            "SKU contains the No/NO token, so the product is identified as not printed."
            if has_no_token
            else "SKU does not contain the No/NO token, so the product is identified as printed."
        ),
    }


def extract_gtm_product_data(soup: BeautifulSoup) -> dict[str, Any]:
    field = soup.select_one('input[name="gtm4wp_product_data"]')
    if not field or not field.get("value"):
        return {}
    try:
        return json.loads(html.unescape(field["value"]))
    except json.JSONDecodeError:
        return {}


def field_label(field: Any) -> str | None:
    field_id = field.get("id")
    if field_id:
        parent = field.find_parent()
        label = parent.select_one(f'label[for="{field_id}"]') if parent else None
        if label:
            text = clean_text(label.get_text(" ", strip=True))
            if text:
                return text

    for wrapper in field.parents:
        classes = set(wrapper.get("class", []))
        if classes.intersection({"cpf-element", "tc-element-inner-wrap", "tc-cell"}):
            title = wrapper.select_one(".tc-element-label, .tm-epo-element-label, .tm-section-label, h3, h4")
            text = clean_text(title.get_text(" ", strip=True) if title else None)
            if text:
                return text

        if wrapper.name in {"form", "body", "html"}:
            break

    wrapper = field.find_parent(["p", "div", "li", "label"])
    if wrapper:
        label = wrapper.select_one("label")
        if label:
            text = clean_text(label.get_text(" ", strip=True))
            if text:
                return text

    return clean_text(field.get("aria-label") or field.get("placeholder") or field.get("name"))


def field_values(field: Any) -> list[str]:
    if field.name == "select":
        values = []
        for option in field.select("option"):
            text = clean_text(option.get_text(" ", strip=True))
            value = clean_text(option.get("value"))
            selected = text or value
            if selected and selected.lower() != "choose an option":
                values.append(selected)
        return values

    value = clean_text(field.get("value"))
    return [value] if value else []


def field_price(field: Any) -> float | None:
    for attr in ["data-price", "data-rules", "data-original-rules"]:
        raw = field.get(attr)
        if not raw:
            continue
        try:
            parsed = json.loads(html.unescape(raw))
        except json.JSONDecodeError:
            parsed = raw

        if isinstance(parsed, list):
            for item in parsed:
                price = number_or_none(item)
                if price is not None:
                    return price
        else:
            price = number_or_none(parsed)
            if price is not None:
                return price
    return None


def first_attribute_value(attributes: dict[str, Any], suffix: str) -> Any:
    for key, value in attributes.items():
        if key.endswith(suffix):
            return value
    return None


def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", text.replace(",", ""))
    return float(match.group(1)) if match else None


def number_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return parse_price(str(value)) if value is not None else None


def is_internal_field(name: str) -> bool:
    internal_names = {
        "add-to-cart",
        "cpf_product_price",
        "gtm4wp_product_data",
        "product_id",
        "quantity",
        "tc_form_prefix",
        "tcaddtocart",
        "tm-epo-counter",
        "variation_id",
        "woobt_ids",
    }
    return name in internal_names or name.startswith(("attribute_", "tm_attribute_"))

