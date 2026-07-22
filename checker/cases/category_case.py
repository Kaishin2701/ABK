from __future__ import annotations

import csv
from functools import lru_cache
from typing import Any

from checker.config import load_json_config, project_path
from checker.models import make_issue


def run(product_data: dict[str, Any]) -> list[dict[str, str]]:
    rules = load_json_config("category_rules.json")
    catalog = load_category_catalog(
        rules["category_file"],
        tuple(rules["continents"]),
        tuple(rules["non_club_parents"]),
    )
    actual_categories = actual_product_categories(product_data)
    searchable_text = normalize(" ".join([str(product_data.get("title") or ""), " ".join(actual_categories)]))

    entity = identify_entity(product_data, searchable_text, catalog)
    if not entity:
        return []

    missing = [name for name in entity["required_categories"] if not has_category(actual_categories, name)]
    if not missing:
        return []

    return [
        make_category_issue(
            rules,
            title="Product may be assigned to the wrong category or missing required categories",
            found=f"Current category/tag values: {', '.join(actual_categories) or 'no category data'}",
            expected=(
                f"The product is identified as {entity['entity_type']} '{entity['name']}', "
                f"so it should include: {', '.join(entity['required_categories'])}"
            ),
            explanation=(
                "According to the RFS category tree, club products must include both the league and club categories; "
                "national team products must include both the continent and country categories. "
                f"Missing: {', '.join(missing)}."
            ),
        )
    ]


def identify_entity(product_data: dict[str, Any], searchable_text: str, catalog: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    additional = product_data.get("additional_information") or {}
    national_name = clean(additional.get("National Team"))
    club_name = clean(additional.get("Club Name"))

    if national_name:
        national = best_match(national_name, catalog["national_teams"])
        if national:
            return national

    if club_name:
        club = best_match(club_name, catalog["clubs"])
        if club:
            return club

    national = best_match(searchable_text, catalog["national_teams"])
    club = best_match(searchable_text, catalog["clubs"])
    if national and club:
        return national if len(national["name"]) >= len(club["name"]) else club
    return national or club


def best_match(searchable_text: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [item for item in candidates if any(contains_name(searchable_text, name) for name in item.get("match_names", [item["name"]]))]
    if not matches:
        return None
    return max(matches, key=lambda item: len(item["name"]))


def contains_name(text: str, name: str) -> bool:
    normalized_text = f" {normalize(text)} "
    normalized_name = f" {normalize(name)} "
    return normalized_name in normalized_text or normalized_text.strip() in normalized_name


def actual_product_categories(product_data: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for source in [product_data.get("categories") or [], product_data.get("tags") or []]:
        for item in source:
            text = clean(item)
            if text and text not in values:
                values.append(text)
    return values


def has_category(actual_categories: list[str], expected_name: str) -> bool:
    expected = normalize(expected_name)
    return any(normalize(category) == expected for category in actual_categories)


@lru_cache(maxsize=1)
def load_category_catalog(category_file: str, continents_tuple: tuple[str, ...], non_club_parents_tuple: tuple[str, ...]) -> dict[str, list[dict[str, Any]]]:
    continents = set(continents_tuple)
    non_club_parents = continents | set(non_club_parents_tuple)
    rows = read_category_rows(category_file)
    national_teams: list[dict[str, Any]] = []
    clubs: list[dict[str, Any]] = []

    for row in rows:
        raw_name = clean(row.get("name"))
        name = canonical_category_name(raw_name)
        parent_name = clean(row.get("parent_name"))
        if not name or not parent_name:
            continue

        if parent_name in continents:
            national_teams.append(
                {
                    "entity_type": "national team",
                    "name": name,
                    "parent": parent_name,
                    "match_names": unique_values([raw_name, name]),
                    "required_categories": [parent_name, name],
                }
            )
        elif parent_name not in non_club_parents:
            clubs.append(
                {
                    "entity_type": "club",
                    "name": name,
                    "parent": parent_name,
                    "match_names": unique_values([raw_name, name]),
                    "required_categories": [parent_name, name],
                }
            )
    return {"national_teams": national_teams, "clubs": clubs}


def read_category_rows(category_file: str) -> list[dict[str, str]]:
    raw = project_path(category_file).read_bytes()
    for encoding in ["utf-8-sig", "cp1252", "latin-1"]:
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1", errors="replace")
    return list(csv.DictReader(text.splitlines(), delimiter="\t"))


def make_category_issue(rules: dict[str, Any], title: str, found: str, expected: str, explanation: str) -> dict[str, str]:
    return make_issue(rules["case_code"], rules["severity"], rules["case_name"], title, found, expected, explanation)


def canonical_category_name(value: Any) -> str:
    text = clean(value)
    suffixes = [
        " Replica Football Shirts & Kit",
        " Replica Football Shirts & Kits",
        " Replica Football Shirt",
        " Replica Football Kit",
        " Football Shirts & Kit",
        " Football Shirts & Kits",
    ]
    for suffix in suffixes:
        if text.lower().endswith(suffix.lower()):
            text = text[: -len(suffix)]
            break
    return clean(text)


def unique_values(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        value = clean(value)
        if value and value not in result:
            result.append(value)
    return result

def clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def normalize(value: Any) -> str:
    return " ".join(clean(value).lower().replace("-", " ").replace("_", " ").split())

