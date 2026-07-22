from __future__ import annotations

from typing import Any

from checker.config import load_json_config
from checker.models import make_issue


def run(product_data: dict[str, Any]) -> list[dict[str, str]]:
    rules = load_json_config("personalisation_rules.json")
    printed = product_data.get("printed") or {}
    is_printed = printed.get("is_printed")
    has_form = has_personalisation_form(product_data, rules)

    if is_printed is None:
        return [
            make_personalisation_issue(
                rules,
                title="Unable to identify printed status from SKU",
                found=f"SKU: {product_data.get('sku') or 'missing SKU'}",
                expected="The SKU should indicate whether the product is printed or not printed.",
                explanation="This case needs printed/no-printed status to validate the personalisation form.",
            )
        ]

    if is_printed and has_form:
        return [
            make_personalisation_issue(
                rules,
                title="Printed product still has a personalisation form",
                found="The SKU is identified as printed, but global_form still contains a personalisation option.",
                expected="Printed products should not display an extra personalisation form.",
                explanation="The product already has printed content from the SKU, so an extra personalisation form may confuse customers.",
            )
        ]

    if not is_printed and not has_form:
        return [
            make_personalisation_issue(
                rules,
                title="No-printed product is missing the personalisation form",
                found="The SKU is identified as no printed, but global_form has no personalisation option.",
                expected="No-printed products should provide a personalisation form so customers can add name/number if needed.",
                explanation="The product has no pre-printed content, so the customer should be able to choose personalisation.",
            )
        ]

    return []


def has_personalisation_form(product_data: dict[str, Any], rules: dict[str, Any]) -> bool:
    keywords = [normalize(item) for item in rules.get("form_keywords", [])]
    for option in product_data.get("global_form") or []:
        text = normalize(
            " ".join(
                [
                    str(option.get("name") or ""),
                    str(option.get("label") or ""),
                    " ".join(str(value) for value in option.get("values") or []),
                ]
            )
        )
        if any(keyword in text for keyword in keywords):
            return True
    return False


def make_personalisation_issue(rules: dict[str, Any], title: str, found: str, expected: str, explanation: str) -> dict[str, str]:
    return make_issue(rules["case_code"], rules["severity"], rules["case_name"], title, found, expected, explanation)


def normalize(value: Any) -> str:
    return " ".join(str(value or "").lower().split())
