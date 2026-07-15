from __future__ import annotations

import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPOSITORY_ROOT / "config" / "directions.json"

EXPECTED_CATEGORY_IDS = ["broad_style", "industry", "hong_kong"]
EXPECTED_DIRECTION_IDS = [
    "hs300",
    "csi500",
    "csi1000",
    "gem",
    "star50",
    "dividend",
    "information",
    "defense",
    "healthcare",
    "consumer",
    "finance",
    "cyclical_resources",
    "hsi",
    "hstech",
    "hk_dividend",
]


def load_registry() -> dict:
    assert REGISTRY_PATH.is_file(), "the locked 15-direction registry is missing"
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_registry_has_exactly_three_mutually_exclusive_categories() -> None:
    registry = load_registry()

    category_ids = [category["id"] for category in registry["categories"]]

    assert category_ids == EXPECTED_CATEGORY_IDS
    assert "all" not in category_ids


def test_registry_has_exactly_fifteen_ordered_first_level_directions() -> None:
    registry = load_registry()

    directions = [
        direction
        for category in registry["categories"]
        for direction in category["directions"]
    ]
    direction_ids = [direction["id"] for direction in directions]

    assert direction_ids == EXPECTED_DIRECTION_IDS
    assert len(direction_ids) == len(set(direction_ids)) == 15
    assert all(direction["level"] == 1 for direction in directions)


def test_registry_keeps_proxy_audit_state_explicit() -> None:
    registry = load_registry()

    for category in registry["categories"]:
        for direction in category["directions"]:
            assert direction["category_id"] == category["id"]
            assert direction["currency"] in {"CNY", "HKD"}
            assert direction["calendar"] in {"XSHG_XSHE", "XHKG"}
            assert direction["source_audit_status"] in {"pending", "verified"}
            if direction["source_audit_status"] == "pending":
                assert direction["primary_proxy_code"] is None
                assert direction["publisher"] is None

