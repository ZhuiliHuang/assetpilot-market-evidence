from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from market_evidence.analysis_publisher import publish_candidate
from market_evidence.package_builder import sha256_hex
from market_evidence.publication import PublicationError, load_json, validate_public_tree
from scripts.update_market_data import update_public_tree
from tests.test_ai_candidate import valid_candidate


NOW = datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)


def historical_tree(tmp_path: Path) -> Path:
    root = tmp_path / "historical"
    update_public_tree(root, now=NOW, fixture_mode=True)
    candidate_path = tmp_path / "ai-inbox" / "2026-07-15.json"
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(
        json.dumps(valid_candidate(root), ensure_ascii=False),
        encoding="utf-8",
    )
    publish_candidate(candidate_path, root, published_at=NOW)
    return root


def test_recovers_last_valid_analysis_as_older_evidence_fallback(tmp_path: Path) -> None:
    from market_evidence.analysis_recovery import recover_analysis_reference

    historical = historical_tree(tmp_path)
    current = tmp_path / "current"
    update_public_tree(
        current,
        now=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
        fixture_mode=True,
    )
    historical_entry = load_json(historical / "manifest.json")["analysis"]

    changed = recover_analysis_reference(current, historical)

    manifest = validate_public_tree(current)
    assert changed is True
    assert manifest["analysis"] is None
    assert manifest["analysis_fallback"] == historical_entry
    assert (current / historical_entry["package_path"]).is_file()
    assert sha256_hex(load_json(current / "market-analysis-latest.json")) == historical_entry["sha256"]


def test_recovery_is_noop_when_current_tree_already_has_analysis(tmp_path: Path) -> None:
    from market_evidence.analysis_recovery import recover_analysis_reference

    current = historical_tree(tmp_path)
    before = sha256_hex(load_json(current / "manifest.json"))

    assert recover_analysis_reference(current, current) is False
    assert sha256_hex(load_json(current / "manifest.json")) == before


def test_recovery_rejects_tampered_history_without_mutating_current(tmp_path: Path) -> None:
    from market_evidence.analysis_recovery import recover_analysis_reference

    historical = historical_tree(tmp_path)
    historical_manifest = load_json(historical / "manifest.json")
    analysis_path = historical / historical_manifest["analysis"]["package_path"]
    analysis = load_json(analysis_path)
    analysis["overall_limitations"].append("tampered")
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    current = tmp_path / "current"
    update_public_tree(
        current,
        now=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
        fixture_mode=True,
    )
    before = sha256_hex(load_json(current / "manifest.json"))

    with pytest.raises(PublicationError, match="analysis hash mismatch"):
        recover_analysis_reference(current, historical)

    assert sha256_hex(load_json(current / "manifest.json")) == before
    assert not (current / "market-analysis-latest.json").exists()
