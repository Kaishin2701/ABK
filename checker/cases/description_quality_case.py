from __future__ import annotations

from typing import Any

from checker.config import load_json_config
from checker.models import make_issue


def run(product_data: dict[str, Any]) -> list[dict[str, str]]:
    rules = load_json_config("description_quality_rules.json")
    description_text = collect_description_text(product_data)
    matched_phrases = [
        phrase
        for phrase in rules.get("deprecated_phrases", [])
        if normalize(phrase) in description_text
    ]

    if not matched_phrases:
        return []

    return [
        make_issue(
            rules["case_code"],
            rules["severity"],
            rules["case_name"],
            title="Description contains outdated content that should be improved",
            found=f"Matched phrase(s): {', '.join(matched_phrases)}",
            expected="The description should focus on the current product and avoid old collection-promo blocks.",
            explanation=(
                "The phrase 'Check out our full collection' usually belongs to an older collection-navigation template. "
                "It does not directly describe the product and should be replaced with more useful product copy."
            ),
        )
    ]


def collect_description_text(product_data: dict[str, Any]) -> str:
    return normalize(
        " ".join(
            [
                str(product_data.get("short_description") or ""),
                str(product_data.get("long_description") or ""),
            ]
        )
    )


def normalize(value: Any) -> str:
    return " ".join(str(value or "").lower().split())
