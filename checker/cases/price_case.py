from __future__ import annotations

from typing import Any

from checker.config import load_json_config
from checker.models import make_issue


def run(product_data: dict[str, Any]) -> list[dict[str, str]]:
    rules = load_json_config("price_rules.json")
    issues: list[dict[str, str]] = []
    product_type = identify_product_type(product_data)

    if product_type:
        expected_price = expected_product_price(product_type, product_data, rules)
        for label, current_price in collect_product_prices(product_data):
            if not same_price(current_price, expected_price, rules["price_tolerance"]):
                issues.append(
                    make_price_issue(
                        rules,
                        title=f"Incorrect price for {label}",
                        found=f"{label} is {format_price(current_price, rules)}",
                        expected=expected_price_message(product_type, expected_price, product_data, rules),
                        explanation=(
                            "The product price does not match the standard price table. "
                            "Customers may see or pay the wrong price."
                        ),
                    )
                )
    else:
        issues.append(
            make_price_issue(
                rules,
                title="Unable to identify product type for price validation",
                found="The title/additional information data could not be mapped to the standard price table.",
                expected="The product should map to one Product Type in the price table.",
                explanation="A correct expected price cannot be confirmed without identifying the Product Type.",
            )
        )

    issues.extend(check_add_on_prices(product_data, rules))
    return issues


def identify_product_type(product_data: dict[str, Any]) -> str | None:
    title = normalize(product_data.get("title"))
    additional = product_data.get("additional_information") or {}
    gender_age = normalize(additional.get("Gender Age"))
    kit_type = normalize(additional.get("Kit Type"))
    kit_option = normalize(additional.get("Kit Option"))
    joined = " ".join([title, gender_age, kit_type, kit_option])

    is_bundle = "bundle" in joined
    is_retro = "retro" in joined
    is_kid = any(word in joined for word in ["kid", "kids", "youth", "child", "children"])
    is_adult = "adult" in joined
    has_socks, no_socks = detect_sock_option(kit_option, joined)
    is_shirt = "shirt" in joined or "jersey" in joined
    is_kit = "kit" in joined

    if is_bundle:
        if "printed upgrade" in joined:
            return "Printed upgrade (add to any bundle)"
        if is_kid and has_socks:
            return "Bundle - Kids With Socks"
        if is_kid and (no_socks or not has_socks):
            return "Bundle - Kids No Socks"
        if is_shirt:
            return "Bundle - Men Shirt"

    if is_retro:
        if is_kid and has_socks:
            return "Retro Kid Kit (With Socks) / Retro Men Shirt"
        if is_kid:
            return "Retro Kid Kit (No Socks)"
        if is_shirt:
            return "Retro Kid Kit (With Socks) / Retro Men Shirt"

    if is_kid and has_socks:
        return "Kid Kit (With Socks)"
    if is_kid:
        return "Kid Kit (No Socks)"

    if (is_adult or is_kit) and has_socks:
        return "Adult Kit (With Socks)"
    if is_adult or (is_kit and not is_shirt):
        return "Adult Kit (No Socks)"

    if is_shirt:
        return "Men's Shirt / Women's Shirt"
    return None


def detect_sock_option(kit_option: str, fallback_text: str) -> tuple[bool, bool]:
    if kit_option:
        if "with socks" in kit_option:
            return True, False
        if "no socks" in kit_option or "without socks" in kit_option:
            return False, True
        if "socks" in kit_option:
            return True, False

    has_socks = "with socks" in fallback_text or "socks" in fallback_text and "no socks" not in fallback_text
    no_socks = "no socks" in fallback_text or "without socks" in fallback_text
    return has_socks, no_socks

def expected_product_price(product_type: str, product_data: dict[str, Any], rules: dict[str, Any]) -> float:
    product_prices = rules["product_prices"]
    bundle_prices = rules["bundle_prices"]
    if product_type in product_prices:
        base_price = product_prices[product_type]
    else:
        base_price = bundle_prices[product_type]
    if is_printed_product(product_data):
        base_price += float(rules["printed_add_on_price"])
    return float(base_price)


def expected_price_message(product_type: str, expected_price: float, product_data: dict[str, Any], rules: dict[str, Any]) -> str:
    if is_printed_product(product_data):
        base_price = rules["product_prices"].get(
            product_type,
            rules["bundle_prices"].get(product_type, expected_price - rules["printed_add_on_price"]),
        )
        return (
            f"Product type '{product_type}' has base price {format_price(float(base_price), rules)} "
            f"+ printed {format_price(float(rules['printed_add_on_price']), rules)} "
            f"so it should be {format_price(expected_price, rules)}"
        )
    return f"Product type '{product_type}' should be {format_price(expected_price, rules)}"


def is_printed_product(product_data: dict[str, Any]) -> bool:
    return (product_data.get("printed") or {}).get("is_printed") is True


def collect_product_prices(product_data: dict[str, Any]) -> list[tuple[str, float]]:
    prices: list[tuple[str, float]] = []
    base_price = as_float(product_data.get("base_price"))
    if base_price is not None:
        prices.append(("base price", base_price))

    for size_item in product_data.get("size_prices") or []:
        size = size_item.get("size") or "unknown size"
        sku = size_item.get("sku") or "unknown SKU"
        price = as_float(size_item.get("price"))
        if price is not None:
            prices.append((f"size {size} / SKU {sku}", price))
    return prices


def check_add_on_prices(product_data: dict[str, Any], rules: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    add_on_prices = rules["add_on_prices"]
    for option in product_data.get("global_form") or []:
        label = normalize(option.get("label") or option.get("name"))
        current_price = as_float(option.get("price"))
        if current_price is None:
            continue

        expected_name = None
        if "badge" in label:
            expected_name = "Badge Add-on"
        elif "personal" in label and "bundle" in label:
            expected_name = "Personalisation Add-on (bundle item)"
        elif "personal" in label:
            expected_name = "Personalisation Add-on (individual product)"

        if not expected_name or is_free_no_option(option, current_price, rules):
            continue

        expected_price = float(add_on_prices[expected_name])
        if not same_price(current_price, expected_price, rules["price_tolerance"]):
            issues.append(
                make_price_issue(
                    rules,
                    title=f"Incorrect add-on price: {option.get('label') or option.get('name')}",
                    found=f"Add-on price is {format_price(current_price, rules)}",
                    expected=f"{expected_name} should be {format_price(expected_price, rules)}",
                    explanation="The add-on price does not match the standard price table.",
                )
            )
    return issues


def is_free_no_option(option: dict[str, Any], current_price: float, rules: dict[str, Any]) -> bool:
    if not same_price(current_price, 0.0, rules["price_tolerance"]):
        return False
    values = " ".join(str(value) for value in option.get("values") or [])
    option_text = normalize(f"{option.get('label', '')} {values}")
    return "no" in option_text and "yes" not in option_text


def make_price_issue(rules: dict[str, Any], title: str, found: str, expected: str, explanation: str) -> dict[str, str]:
    return make_issue(rules["case_code"], rules["severity"], rules["case_name"], title, found, expected, explanation)


def normalize(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    try:
        return float(str(value).replace("£", "").replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def same_price(current: float, expected: float, tolerance: float) -> bool:
    return abs(current - expected) <= tolerance


def format_price(value: float, rules: dict[str, Any]) -> str:
    return f"{rules.get('currency', '£')}{value:.2f}"



