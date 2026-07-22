from __future__ import annotations

from typing import Any

from checker.config import load_json_config
from checker.models import make_issue


def run(product_data: dict[str, Any]) -> list[dict[str, str]]:
    rules = load_json_config("description_rules.json")
    expected_types = expected_types_from_sku(product_data.get("sku"), rules)
    if not expected_types:
        return []

    description_text = collect_description_text(product_data, rules)
    heading_text = collect_heading_text(product_data)
    if not description_text:
        return [
            make_description_issue(
                rules,
                title="No description is available for product-type validation",
                found="Both Short Description and Long Description are empty.",
                expected=f"The description should mention: {', '.join(expected_types)}",
                explanation="The SKU contains product-type codes, but there is no description text to validate against.",
            )
        ]

    all_types = list(rules["sku_type_map"].values())
    missing_types = [
        item
        for item in expected_types
        if not contains_type(text_for_product_type(item, description_text, heading_text, rules), item, rules)
    ]
    wrong_types = [
        product_type
        for product_type in all_types
        if product_type not in expected_types
        and contains_type(text_for_product_type(product_type, description_text, heading_text, rules), product_type, rules)
    ]

    issues: list[dict[str, str]] = []
    if missing_types:
        issues.append(
            make_description_issue(
                rules,
                title="Description is missing the product type required by the SKU",
                found=f"Missing keyword(s): {', '.join(missing_types)}",
                expected=f"The SKU requires the description to mention: {', '.join(expected_types)}",
                explanation="The description wording should match the product type encoded in the SKU.",
            )
        )

    if wrong_types:
        issues.append(
            make_description_issue(
                rules,
                title="Description mentions a product type that does not match the SKU",
                found=f"Description mentions type(s) not present in the SKU: {', '.join(wrong_types)}",
                expected=f"Description should only mention SKU product type(s): {', '.join(expected_types)}",
                explanation="The description contains product-type wording that differs from the SKU and may misrepresent the listing.",
            )
        )

    return issues


def expected_types_from_sku(sku: Any, rules: dict[str, Any]) -> list[str]:
    sku_type_map = rules["sku_type_map"]
    parts = [part.upper() for part in str(sku or "").split("_") if part]
    expected: list[str] = []

    for part in parts:
        remaining = part
        found_in_part: list[str] = []
        while remaining:
            matched = False
            for code in sorted(sku_type_map, key=len, reverse=True):
                if remaining.startswith(code):
                    found_in_part.append(sku_type_map[code])
                    remaining = remaining[len(code):]
                    matched = True
                    break
            if not matched:
                found_in_part = []
                break

        for product_type in found_in_part:
            if product_type not in expected:
                expected.append(product_type)
    return expected


def text_for_product_type(product_type: str, description_text: str, heading_text: str, rules: dict[str, Any]) -> str:
    if product_type in rules.get("heading_only_types", []):
        return heading_text
    return description_text


def collect_description_text(product_data: dict[str, Any], rules: dict[str, Any]) -> str:
    text = normalize(
        " ".join(
            [
                str(product_data.get("short_description") or ""),
                str(product_data.get("long_description") or ""),
            ]
        )
    )
    for phrase in rules.get("ignored_phrases", []):
        text = text.replace(normalize(phrase), " ")
    return normalize(text)


def collect_heading_text(product_data: dict[str, Any]) -> str:
    return normalize(" ".join(str(item) for item in product_data.get("description_headings") or []))


def contains_type(text: str, product_type: str, rules: dict[str, Any]) -> bool:
    return any(keyword in text for keyword in rules["type_keywords"][product_type])


def make_description_issue(rules: dict[str, Any], title: str, found: str, expected: str, explanation: str) -> dict[str, str]:
    return make_issue(rules["case_code"], rules["severity"], rules["case_name"], title, found, expected, explanation)


def normalize(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").replace("_", " ").split())
