from __future__ import annotations

from typing import Any, Callable

from checker.cases.category_case import run as run_category_case
from checker.cases.consistency_case import run as run_consistency_case
from checker.cases.description_logic_case import run as run_description_logic_case
from checker.cases.description_quality_case import run as run_description_quality_case
from checker.cases.personalisation_case import run as run_personalisation_case
from checker.cases.price_case import run as run_price_case
from checker.cases.review_case import run as run_review_case
from checker.cases.size_chart_case import run as run_size_chart_case

CaseRunner = Callable[[dict[str, Any]], list[dict[str, str]]]

ALL_CASES: list[CaseRunner] = [
    run_price_case,
    run_personalisation_case,
    run_size_chart_case,
    run_description_logic_case,
    run_description_quality_case,
    run_category_case,
    run_review_case,
    run_consistency_case,
]


def run_all(product_data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for case in ALL_CASES:
        issues.extend(case(product_data))
    return issues



