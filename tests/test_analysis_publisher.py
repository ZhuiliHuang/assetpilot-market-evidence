from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.test_ai_candidate import valid_candidate


NOW = datetime(2026, 7, 15, 14, 5, tzinfo=timezone.utc)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def public_tree(tmp_path: Path) -> Path:
    from scripts.update_market_data import update_public_tree

    root = tmp_path / "public"
    update_public_tree(root, now=NOW, fixture_mode=True)
    return root


def write_candidate(tmp_path: Path, candidate: dict) -> Path:
    path = tmp_path / "ai-inbox" / "2026-07-15.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
    return path


def test_valid_candidate_publishes_official_analysis_and_updates_manifest(public_tree: Path, tmp_path: Path) -> None:
    from market_evidence.analysis_publisher import publish_candidate
    from market_evidence.schema_validation import validate_document

    candidate_path = write_candidate(tmp_path, valid_candidate(public_tree))
    analysis = publish_candidate(candidate_path, public_tree, published_at=NOW)

    validate_document("market-analysis", analysis)
    manifest = load_json(public_tree / "manifest.json")
    assert manifest["analysis"]["analysis_as_of"] == "2026-07-15"
    assert manifest["analysis"]["evidence_version"] == manifest["evidence_version"]
    assert load_json(public_tree / manifest["analysis"]["package_path"]) == analysis
    assert load_json(public_tree / "market-analysis-latest.json") == analysis


def test_invalid_candidate_leaves_previous_analysis_unchanged(public_tree: Path, tmp_path: Path) -> None:
    from market_evidence.ai_candidate import CandidateValidationError
    from market_evidence.analysis_publisher import publish_candidate
    from market_evidence.package_builder import sha256_hex

    first_path = write_candidate(tmp_path, valid_candidate(public_tree))
    publish_candidate(first_path, public_tree, published_at=NOW)
    before_manifest = load_json(public_tree / "manifest.json")
    before_analysis = load_json(public_tree / before_manifest["analysis"]["package_path"])

    invalid = valid_candidate(public_tree)
    invalid["focus_opportunities"][0]["thesis"] = "建议立即卖出"
    invalid_path = write_candidate(tmp_path, invalid)
    with pytest.raises(CandidateValidationError):
        publish_candidate(invalid_path, public_tree, published_at=NOW)

    after_manifest = load_json(public_tree / "manifest.json")
    after_analysis = load_json(public_tree / after_manifest["analysis"]["package_path"])
    assert sha256_hex(after_manifest) == sha256_hex(before_manifest)
    assert sha256_hex(after_analysis) == sha256_hex(before_analysis)


def test_fresh_candidate_replaces_stale_fallback(public_tree: Path, tmp_path: Path) -> None:
    from market_evidence.analysis_publisher import publish_candidate
    from scripts.update_market_data import update_public_tree

    first_path = write_candidate(tmp_path, valid_candidate(public_tree))
    publish_candidate(first_path, public_tree, published_at=NOW)
    update_public_tree(
        public_tree,
        now=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
        fixture_mode=True,
    )
    stale_manifest = load_json(public_tree / "manifest.json")
    assert stale_manifest["analysis"] is None
    assert stale_manifest["analysis_fallback"] is not None

    candidate = valid_candidate(public_tree)
    candidate.update(
        candidate_version="2026-07-16.aaaaaaaa",
        analysis_date="2026-07-16",
        generated_at="2026-07-16T14:00:00Z",
    )
    candidate_path = tmp_path / "ai-inbox" / "2026-07-16.json"
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
    analysis = publish_candidate(
        candidate_path,
        public_tree,
        published_at=datetime(2026, 7, 16, 14, 5, tzinfo=timezone.utc),
    )

    current_manifest = load_json(public_tree / "manifest.json")
    assert current_manifest["analysis_fallback"] is None
    assert current_manifest["analysis"]["evidence_version"] == current_manifest["evidence_version"]
    assert load_json(public_tree / "market-analysis-latest.json") == analysis
