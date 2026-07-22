from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"


@lru_cache(maxsize=None)
def load_json_config(filename: str) -> dict[str, Any]:
    path = CONFIG_DIR / filename
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def project_path(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path
