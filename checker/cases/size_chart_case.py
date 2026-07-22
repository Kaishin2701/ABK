from __future__ import annotations

from typing import Any

from checker.config import load_json_config
from checker.models import make_issue


def run(product_data: dict[str, Any]) -> list[dict[str, str]]:
    rules = load_json_config("size_chart_rules.json")
    size_chart_titles = rules["size_chart_titles"]
    required_codes = required_size_codes(product_data.get("sku"), size_chart_titles)
    if not required_codes:
        return []

    available_titles = collect_image_titles(product_data)
    issues: list[dict[str, str]] = []
    for code in sorted(required_codes):
        expected_titles = size_chart_titles[code]
        if not has_any_title(available_titles, expected_titles):
            issues.append(
                make_size_issue(
                    rules,
                    title=f"Missing size chart image for {code}",
                    found=(
                        "No matching size chart image was found in the gallery. "
                        f"Available image titles: {', '.join(available_titles) or 'no image titles'}"
                    ),
                    expected=f"SKU contains {code}, so one of these images is required: {', '.join(expected_titles)}",
                    explanation="The size chart must match the product type in the SKU so customers can choose the correct size.",
                )
            )
    return issues


def required_size_codes(sku: Any, size_chart_titles: dict[str, list[str]]) -> set[str]:
    parts = [part.upper() for part in str(sku or "").split("_") if part]
    required: set[str] = set()
    for code in size_chart_titles:
        if code in parts:
            required.add(code)
    if "ADK" in required and "AD" in required:
        required.remove("AD")
    return required


def collect_image_titles(product_data: dict[str, Any]) -> list[str]:
    titles: list[str] = []
    for image in product_data.get("image_details") or []:
        for key in ["title", "alt", "filename"]:
            value = image.get(key)
            if value and value not in titles:
                titles.append(str(value))
    return titles


def has_any_title(available_titles: list[str], expected_titles: list[str]) -> bool:
    normalized_available = [normalize(title) for title in available_titles]
    for expected in expected_titles:
        normalized_expected = normalize(expected)
        if any(normalized_expected in title for title in normalized_available):
            return True
    return False


def make_size_issue(rules: dict[str, Any], title: str, found: str, expected: str, explanation: str) -> dict[str, str]:
    return make_issue(rules["case_code"], rules["severity"], rules["case_name"], title, found, expected, explanation)


def normalize(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").replace("_", " ").split())
