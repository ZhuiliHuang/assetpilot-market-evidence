from __future__ import annotations

import json
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = REPOSITORY_ROOT / "config" / "sources.json"
DIRECTIONS_PATH = REPOSITORY_ROOT / "config" / "directions.json"


def load_json(path: Path) -> dict:
    assert path.is_file(), f"missing source audit file: {path.relative_to(REPOSITORY_ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def expected_direction_ids() -> list[str]:
    registry = load_json(DIRECTIONS_PATH)
    return [
        direction["id"]
        for category in registry["categories"]
        for direction in category["directions"]
    ]


def test_source_registry_covers_every_locked_direction_once() -> None:
    source_registry = load_json(SOURCES_PATH)

    covered = [entry["direction_id"] for entry in source_registry["direction_sources"]]

    assert covered == expected_direction_ids()
    assert len(covered) == len(set(covered)) == 15


def test_every_direction_has_official_metadata_and_multiple_data_fallbacks() -> None:
    source_registry = load_json(SOURCES_PATH)
    sources = {source["id"]: source for source in source_registry["sources"]}

    for entry in source_registry["direction_sources"]:
        assert sources[entry["official_source_id"]]["kind"] == "official_metadata"
        assert sources[entry["official_source_id"]]["redistribution_policy"] == "link_only"
        assert len(entry["data_source_chain"]) >= 2
        assert len(entry["data_source_chain"]) == len(set(entry["data_source_chain"]))
        assert all(sources[source_id]["kind"] == "market_data" for source_id in entry["data_source_chain"])


def test_sources_have_explicit_redistribution_and_bounded_retries() -> None:
    source_registry = load_json(SOURCES_PATH)

    for source in source_registry["sources"]:
        assert source["redistribution_policy"] in {
            "publish_raw",
            "publish_derived_only",
            "link_only",
            "blocked",
        }
        assert source["terms_url"].startswith("https://")
        assert 1 <= source["timeout_seconds"] <= 30
        assert 1 <= source["max_attempts"] <= 3
        assert "wind" not in source["id"].lower()
        assert "wind" not in source["provider"].lower()


def test_proxy_identifiers_are_locked_after_the_source_audit() -> None:
    directions = load_json(DIRECTIONS_PATH)

    for category in directions["categories"]:
        for direction in category["directions"]:
            assert direction["source_audit_status"] == "verified"
            assert direction["primary_proxy_code"]
            assert direction["publisher"]


def test_source_registry_validator_rejects_unknown_and_blocked_sources() -> None:
    from market_evidence.source_registry import SourceRegistryError, validate_source_registry

    valid = load_json(REPOSITORY_ROOT / "tests" / "fixtures" / "source-audit" / "valid.json")
    validate_source_registry(valid)

    invalid_directory = REPOSITORY_ROOT / "tests" / "fixtures" / "source-audit" / "invalid"
    invalid_fixtures = sorted(invalid_directory.glob("*.json"))
    assert invalid_fixtures
    for path in invalid_fixtures:
        with pytest.raises(SourceRegistryError, match=".+"):
            validate_source_registry(load_json(path))
