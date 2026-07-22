from __future__ import annotations

from typing import Any

from checker.config import load_json_config
from checker.models import make_issue


def run(product_data: dict[str, Any]) -> list[dict[str, str]]:
    rules = load_json_config("review_rules.json")
    minimum_reviews = int(rules.get("minimum_reviews", 1))
    review_count = as_int(product_data.get("review_count"))

    if review_count >= minimum_reviews:
        return []

    return [
        make_issue(
            rules["case_code"],
            rules["severity"],
            rules["case_name"],
            title="Product has no review",
            found=f"Current review count: {review_count}",
            expected=f"The product should have at least {minimum_reviews} review.",
            explanation="A product should have at least one review to improve listing trustworthiness.",
        )
    ]


def as_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value or "0").strip())
    except ValueError:
        return 0
