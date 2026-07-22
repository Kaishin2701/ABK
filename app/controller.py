from __future__ import annotations

from typing import Any

from checker.engine import run_all
from scraper.product_parser import parse_product_html
from scraper.product_scraper import scrape_product


def check_product_url(url: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    product_data = scrape_product(url)
    issues = run_all(product_data)
    return product_data, issues


def check_product_html(url: str, page_html: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    product_data = parse_product_html(page_html, url)
    issues = run_all(product_data)
    return product_data, issues

