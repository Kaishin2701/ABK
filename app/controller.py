from __future__ import annotations

from typing import Any

from checker.engine import run_all
from scraper.product_scraper import scrape_product


def check_product_url(url: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    product_data = scrape_product(url)
    issues = run_all(product_data)
    return product_data, issues
