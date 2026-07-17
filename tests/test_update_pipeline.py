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


def test_numeric_update_preserves_previous_analysis_as_stale_fallback(tmp_path: Path) -> None:
    from market_evidence.analysis_publisher import publish_candidate
    from scripts.update_market_data import update_public_tree
    from tests.test_ai_candidate import valid_candidate

    destination = tmp_path / "public"
    first_now = datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)
    update_public_tree(destination, now=first_now, fixture_mode=True)
    candidate = valid_candidate(destination)
    candidate_path = tmp_path / "ai-inbox" / "2026-07-15.json"
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
    publish_candidate(candidate_path, destination, published_at=first_now)
    previous_manifest = load_json(destination / "manifest.json")
    previous_analysis = previous_manifest["analysis"]

    update_public_tree(
        destination,
        now=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
        fixture_mode=True,
    )

    current_manifest = load_json(destination / "manifest.json")
    assert current_manifest["analysis"] is None
    assert current_manifest["analysis_fallback"] == previous_analysis
    assert current_manifest["analysis_fallback"]["evidence_version"] != current_manifest["evidence_version"]
    assert (destination / current_manifest["analysis_fallback"]["package_path"]).is_file()
    assert load_json(destination / "market-analysis-latest.json") == load_json(
        destination / current_manifest["analysis_fallback"]["package_path"]
    )


def test_same_evidence_refresh_keeps_current_analysis_current(tmp_path: Path) -> None:
    from market_evidence.analysis_publisher import publish_candidate
    from scripts.update_market_data import update_public_tree
    from tests.test_ai_candidate import valid_candidate

    destination = tmp_path / "public"
    now = datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)
    update_public_tree(destination, now=now, fixture_mode=True)
    candidate_path = tmp_path / "ai-inbox" / "2026-07-15.json"
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(
        json.dumps(valid_candidate(destination), ensure_ascii=False),
        encoding="utf-8",
    )
    publish_candidate(candidate_path, destination, published_at=now)
    published_analysis = load_json(destination / "manifest.json")["analysis"]

    update_public_tree(destination, now=now, fixture_mode=True)

    refreshed_manifest = load_json(destination / "manifest.json")
    assert refreshed_manifest["analysis"] == published_analysis
    assert refreshed_manifest["analysis_fallback"] is None


def test_public_tree_rejects_stale_analysis_fallback_with_wrong_hash(tmp_path: Path) -> None:
    import pytest

    from market_evidence.analysis_publisher import publish_candidate
    from market_evidence.package_builder import canonical_json_bytes
    from market_evidence.publication import PublicationError, validate_public_tree
    from scripts.update_market_data import update_public_tree
    from tests.test_ai_candidate import valid_candidate

    destination = tmp_path / "public"
    first_now = datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)
    update_public_tree(destination, now=first_now, fixture_mode=True)
    candidate_path = tmp_path / "ai-inbox" / "2026-07-15.json"
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(
        json.dumps(valid_candidate(destination), ensure_ascii=False),
        encoding="utf-8",
    )
    publish_candidate(candidate_path, destination, published_at=first_now)
    update_public_tree(
        destination,
        now=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
        fixture_mode=True,
    )
    manifest = load_json(destination / "manifest.json")
    manifest["analysis_fallback"]["sha256"] = "f" * 64
    (destination / "manifest.json").write_bytes(canonical_json_bytes(manifest) + b"\n")

    with pytest.raises(PublicationError, match="fallback analysis hash mismatch"):
        validate_public_tree(destination)


def test_public_tree_rejects_analysis_path_bound_to_wrong_version(tmp_path: Path) -> None:
    import pytest

    from market_evidence.analysis_publisher import publish_candidate
    from market_evidence.package_builder import canonical_json_bytes
    from market_evidence.publication import PublicationError, validate_public_tree
    from scripts.update_market_data import update_public_tree
    from tests.test_ai_candidate import valid_candidate

    destination = tmp_path / "public"
    first_now = datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)
    update_public_tree(destination, now=first_now, fixture_mode=True)
    candidate_path = tmp_path / "ai-inbox" / "2026-07-15.json"
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(
        json.dumps(valid_candidate(destination), ensure_ascii=False),
        encoding="utf-8",
    )
    publish_candidate(candidate_path, destination, published_at=first_now)
    update_public_tree(
        destination,
        now=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
        fixture_mode=True,
    )
    manifest = load_json(destination / "manifest.json")
    entry = manifest["analysis_fallback"]
    wrong_path = "versions/2026-07-14.ffffffffffff/market-analysis.json"
    wrong_file = destination / wrong_path
    wrong_file.parent.mkdir(parents=True, exist_ok=True)
    wrong_file.write_bytes((destination / entry["package_path"]).read_bytes())
    entry["package_path"] = wrong_path
    (destination / "manifest.json").write_bytes(canonical_json_bytes(manifest) + b"\n")

    with pytest.raises(PublicationError, match="path.*evidence version"):
        validate_public_tree(destination)
