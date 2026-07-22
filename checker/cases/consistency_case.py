from __future__ import annotations

import re
from typing import Any

from checker.config import load_json_config
from checker.models import make_issue


def run(product_data: dict[str, Any]) -> list[dict[str, str]]:
    rules = load_json_config("consistency_rules.json")
    issues: list[dict[str, str]] = []
    issues.extend(check_season_consistency(product_data, rules))
    issues.extend(check_national_team_season_format(product_data, rules))
    issues.extend(check_kit_type_consistency(product_data, rules))
    issues.extend(check_team_consistency(product_data, rules))
    return issues


def check_season_consistency(product_data: dict[str, Any], rules: dict[str, Any]) -> list[dict[str, str]]:
    title = str(product_data.get("title") or "")
    sku = str(product_data.get("sku") or "")
    additional = product_data.get("additional_information") or {}
    additional_season = clean(additional.get(rules.get("season_field", "Season")))
    if not additional_season:
        return []

    title_seasons = extract_seasons(title)
    sku_seasons = extract_seasons(sku)
    reference_seasons = title_seasons + [item for item in sku_seasons if item not in title_seasons]
    if not reference_seasons:
        return []

    normalized_additional = normalize_season(additional_season)
    if normalized_additional in [normalize_season(item) for item in reference_seasons]:
        return []

    return [
        consistency_issue(
            rules,
            title="Season mismatch between title/SKU and additional information",
            found=f"Title/SKU season(s): {', '.join(reference_seasons)}; Additional Information Season: {additional_season}",
            expected="The season in Additional Information should match the season shown in the title or SKU.",
            explanation="A season mismatch can cause the product to be listed under the wrong year or collection.",
        )
    ]


def check_national_team_season_format(product_data: dict[str, Any], rules: dict[str, Any]) -> list[dict[str, str]]:
    if not is_national_team_product(product_data):
        return []

    additional = product_data.get("additional_information") or {}
    season = clean(additional.get(rules.get("season_field", "Season")))
    if not season or re.fullmatch(r"\d{4}", season):
        return []

    return [
        consistency_issue(
            rules,
            title="Invalid season format for national team product",
            found=f"Additional Information Season is '{season}'",
            expected="National team products should use a single year, for example 2025 or 2026, not a range like 2025/26.",
            explanation="National team products should be grouped by tournament/year rather than club-style season ranges.",
        )
    ]


def check_kit_type_consistency(product_data: dict[str, Any], rules: dict[str, Any]) -> list[dict[str, str]]:
    expected_types = expected_kit_types_from_sku(product_data.get("sku"), rules)
    if not expected_types:
        return []

    additional = product_data.get("additional_information") or {}
    kit_type = clean(additional.get("Kit Type"))
    if not kit_type:
        return []

    normalized_kit_type = normalize(kit_type)
    missing = [item for item in expected_types if normalize(item) not in normalized_kit_type]
    wrong = [
        value
        for value in rules["sku_type_map"].values()
        if value not in expected_types and normalize(value) in normalized_kit_type
    ]

    if not missing and not wrong:
        return []

    found_parts = []
    if missing:
        found_parts.append(f"missing from Kit Type: {', '.join(missing)}")
    if wrong:
        found_parts.append(f"unexpected in Kit Type: {', '.join(wrong)}")

    return [
        consistency_issue(
            rules,
            title="Kit Type does not match SKU product type code",
            found=f"SKU expects {', '.join(expected_types)}; Additional Information Kit Type is '{kit_type}' ({'; '.join(found_parts)})",
            expected="Kit Type should match the product type encoded in the SKU, such as HO=Home, AW=Away, TH=Third, GK=Goalkeeper, TN=Training.",
            explanation="If SKU and Kit Type disagree, downstream category, description, and pricing checks may classify the product incorrectly.",
        )
    ]


def check_team_consistency(product_data: dict[str, Any], rules: dict[str, Any]) -> list[dict[str, str]]:
    title_team = team_name_from_title(product_data.get("title"))
    additional_team = team_name_from_additional(product_data, rules)
    if not title_team or not additional_team:
        return []

    if normalize(title_team) in normalize(additional_team) or normalize(additional_team) in normalize(title_team):
        return []

    return [
        consistency_issue(
            rules,
            title="Team name in title does not match additional information",
            found=f"Title team candidate: '{title_team}'; Additional Information team: '{additional_team}'",
            expected="The team name inferred from the title should match the team/club/national team in Additional Information.",
            explanation="A team mismatch usually means the product was copied from another listing or assigned incorrect attributes.",
        )
    ]


def expected_kit_types_from_sku(sku: Any, rules: dict[str, Any]) -> list[str]:
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


def is_national_team_product(product_data: dict[str, Any]) -> bool:
    additional = product_data.get("additional_information") or {}
    if clean(additional.get("National Team")):
        return True

    joined_categories = normalize(" ".join((product_data.get("categories") or []) + (product_data.get("tags") or [])))
    return "international teams" in joined_categories


def team_name_from_title(title: Any) -> str | None:
    words = re.findall(r"[A-Za-z]+", str(title or ""))
    if not words:
        return None
    if words[0].lower() == "retro" and len(words) > 1:
        return words[1]
    return words[0]


def team_name_from_additional(product_data: dict[str, Any], rules: dict[str, Any]) -> str | None:
    additional = product_data.get("additional_information") or {}
    for field in rules.get("team_fields", []):
        value = clean(additional.get(field))
        if value:
            return value
    return None


def extract_seasons(value: Any) -> list[str]:
    text = str(value or "")
    seasons = re.findall(r"(?:20\d{2})(?:[/-]\d{2})?", text)
    normalized: list[str] = []
    for season in seasons:
        if season not in normalized:
            normalized.append(season)
    return normalized


def normalize_season(value: str) -> str:
    return clean(value).replace("-", "/")


def consistency_issue(rules: dict[str, Any], title: str, found: str, expected: str, explanation: str) -> dict[str, str]:
    return make_issue(rules["case_code"], rules["severity"], rules["case_name"], title, found, expected, explanation)


def clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def normalize(value: Any) -> str:
    return " ".join(clean(value).lower().replace("-", " ").replace("_", " ").split())
