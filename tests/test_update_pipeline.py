from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_fixture_update_builds_and_validates_a_complete_public_tree(tmp_path: Path) -> None:
    from scripts.publish_data_branch import validate_public_tree
    from scripts.update_market_data import update_public_tree

    destination = tmp_path / "public"
    changed = update_public_tree(
        destination,
        now=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
        fixture_mode=True,
    )

    assert changed is True
    manifest = validate_public_tree(destination)
    assert manifest["evidence_version"].startswith("2026-07-15.")
    assert len(list((destination / "versions" / manifest["evidence_version"] / "directions").glob("*.json"))) == 15
    assert not (destination / ".git").exists()


def test_partial_fixture_failure_retains_old_direction_and_marks_degradation(tmp_path: Path) -> None:
    from scripts.update_market_data import update_public_tree

    destination = tmp_path / "public"
    update_public_tree(
        destination,
        now=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
        fixture_mode=True,
    )
    previous_manifest = load_json(destination / "manifest.json")

    update_public_tree(
        destination,
        now=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
        fixture_mode=True,
        failed_direction_ids={"hstech"},
    )

    current_manifest = load_json(destination / "manifest.json")
    assert current_manifest["evidence_version"] != previous_manifest["evidence_version"]
    assert current_manifest["degraded_sources"][0]["source_id"] == "hstech_public_source_chain"
    hk_category_entry = next(
        entry for entry in current_manifest["categories"] if entry["category_id"] == "hong_kong"
    )
    hk_category = load_json(destination / hk_category_entry["package_path"])
    hstech = next(item for item in hk_category["directions"] if item["direction_id"] == "hstech")
    assert previous_manifest["evidence_version"] in hstech["detail_path"]
    assert hstech["status"] == "degraded"

