from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def fixture_live_loader(direction: dict, _start, _end, now):
    from scripts.update_market_data import fixture_source_results

    return fixture_source_results(direction, now)


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


def test_live_update_uses_public_loader_without_fixture_mode(tmp_path: Path) -> None:
    from scripts.publish_data_branch import validate_public_tree
    from scripts.update_market_data import update_public_tree

    destination = tmp_path / "public"
    changed = update_public_tree(
        destination,
        now=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
        source_loader=fixture_live_loader,
    )

    assert changed is True
    manifest = validate_public_tree(destination)
    assert manifest["data_as_of"] == "2026-07-15"
    assert manifest["degraded_sources"] == []


def test_live_update_paces_only_the_default_cloud_loader(tmp_path: Path, monkeypatch) -> None:
    import scripts.update_market_data as update_module

    waits: list[float] = []
    loaded: list[str] = []

    def default_loader(direction: dict, start, end, now):
        loaded.append(direction["id"])
        return fixture_live_loader(direction, start, end, now)

    monkeypatch.setattr(update_module, "fetch_live_source_results", default_loader)
    changed = update_module.update_public_tree(
        tmp_path / "public",
        now=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
        sleeper=waits.append,
    )

    assert changed is True
    assert len(loaded) == 15
    assert waits == [12] * 14


def test_live_update_logs_only_bounded_source_diagnostics(tmp_path: Path, capsys) -> None:
    from market_evidence.sources.base import SourceResult
    from scripts.update_market_data import update_public_tree

    def diagnostic_loader(direction: dict, start, end, now):
        results = fixture_live_loader(direction, start, end, now)
        return results + [SourceResult(
            source_id="bounded_failure",
            retrieved_at=now,
            as_of_trade_date=None,
            license_mode="publish_derived_only",
            status="failed",
            rows=(),
            errors=("RuntimeError: api_key=must-never-appear",),
        )]

    update_public_tree(
        tmp_path / "public",
        now=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
        source_loader=diagnostic_loader,
    )

    output = capsys.readouterr().out
    assert '"direction_id":"hs300"' in output
    assert '"source_id":"bounded_failure"' in output
    assert '"error_type":"RuntimeError"' in output
    assert "must-never-appear" not in output
    assert "api_key" not in output


def test_live_partial_failure_retains_the_previous_valid_direction(tmp_path: Path) -> None:
    from market_evidence.sources.base import SourceResult
    from scripts.update_market_data import update_public_tree

    destination = tmp_path / "public"
    first_now = datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)
    update_public_tree(destination, now=first_now, source_loader=fixture_live_loader)
    previous = load_json(destination / "manifest.json")

    def partial_loader(direction: dict, start, end, now):
        if direction["id"] != "hstech":
            return fixture_live_loader(direction, start, end, now)
        return [SourceResult(
            source_id="eastmoney_index_history",
            retrieved_at=now,
            as_of_trade_date=None,
            license_mode="publish_derived_only",
            status="failed",
            rows=(),
            errors=("simulated public source outage",),
        )]

    changed = update_public_tree(
        destination,
        now=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
        source_loader=partial_loader,
    )

    assert changed is True
    current = load_json(destination / "manifest.json")
    assert current["evidence_version"] != previous["evidence_version"]
    assert current["degraded_sources"][0]["source_id"] == "hstech_public_source_chain"
    category_entry = next(item for item in current["categories"] if item["category_id"] == "hong_kong")
    category = load_json(destination / category_entry["package_path"])
    hstech = next(item for item in category["directions"] if item["direction_id"] == "hstech")
    assert hstech["status"] == "degraded"
    assert previous["evidence_version"] in hstech["detail_path"]


def test_live_total_failure_keeps_the_last_valid_tree_byte_for_byte(tmp_path: Path) -> None:
    import hashlib

    from market_evidence.sources.base import SourceResult
    from scripts.update_market_data import update_public_tree

    destination = tmp_path / "public"
    first_now = datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)
    update_public_tree(destination, now=first_now, source_loader=fixture_live_loader)
    before = hashlib.sha256((destination / "manifest.json").read_bytes()).hexdigest()

    def failed_loader(direction: dict, _start, _end, now):
        return [SourceResult(
            source_id=f"{direction['id']}_public_source_chain",
            retrieved_at=now,
            as_of_trade_date=None,
            license_mode="publish_derived_only",
            status="failed",
            rows=(),
            errors=("simulated complete public outage",),
        )]

    changed = update_public_tree(
        destination,
        now=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
        source_loader=failed_loader,
    )

    assert changed is False
    assert hashlib.sha256((destination / "manifest.json").read_bytes()).hexdigest() == before


def test_first_live_failure_reports_missing_previous_evidence_accurately(tmp_path: Path) -> None:
    from market_evidence.sources.base import SourceResult
    from scripts.update_market_data import update_public_tree

    def partial_loader(direction: dict, start, end, now):
        if direction["id"] != "hstech":
            return fixture_live_loader(direction, start, end, now)
        return [SourceResult(
            source_id="eastmoney_index_history",
            retrieved_at=now,
            as_of_trade_date=None,
            license_mode="publish_derived_only",
            status="failed",
            rows=(),
            errors=("simulated first-run outage",),
        )]

    destination = tmp_path / "public"
    update_public_tree(
        destination,
        now=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
        source_loader=partial_loader,
    )

    manifest = load_json(destination / "manifest.json")
    degraded = next(
        item for item in manifest["degraded_sources"]
        if item["source_id"] == "hstech_public_source_chain"
    )
    assert degraded["last_successful_date"] is None
    assert degraded["impact"] == "no previous validated direction package is available"
