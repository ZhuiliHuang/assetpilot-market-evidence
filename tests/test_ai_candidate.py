from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


NOW = datetime(2026, 7, 15, 14, 0, tzinfo=timezone.utc)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def valid_candidate(public_root: Path) -> dict:
    from market_evidence.package_builder import sha256_hex

    manifest = load_json(public_root / "manifest.json")
    return {
        "schema_version": "1.0.0",
        "candidate_version": "2026-07-15.aaaaaaaa",
        "evidence_version": manifest["evidence_version"],
        "evidence_manifest_sha256": sha256_hex(manifest),
        "analysis_date": "2026-07-15",
        "generated_at": "2026-07-15T14:00:00Z",
        "focus_opportunities": [
            {
                "direction_id": "hs300",
                "thesis": "历史位置与来源一致性支持继续观察",
                "supporting_evidence_refs": [
                    "directions/hs300#/metrics/current_percentile/value",
                    "directions/hs300#/source_evidence/0/as_of",
                    "directions/hs300#/source_evidence/0/url",
                ],
                "counter_evidence_refs": ["directions/hs300#/series/points/71/value"],
                "invalidation_conditions": ["来源一致性转为冲突"],
                "research_action": "compare_public_evidence",
                "limitations": ["公开估值不能替代企业质量研究"]
            },
            {
                "direction_id": "hstech",
                "thesis": "公开证据值得等待进一步确认",
                "supporting_evidence_refs": [
                    "directions/hstech#/metrics/current_percentile/value",
                    "directions/hstech#/source_evidence/0/as_of",
                    "directions/hstech#/source_evidence/0/url",
                ],
                "counter_evidence_refs": ["directions/hstech#/series/points/71/value"],
                "invalidation_conditions": ["数据缺口扩大并影响判断"],
                "research_action": "wait_for_confirmation",
                "limitations": ["跨市场制度差异仍需单独评估"]
            }
        ],
        "risks": [
            {
                "direction_id": "star50",
                "risk_type": "crowding",
                "summary": "拥挤风险需要持续交叉核验",
                "evidence_refs": ["directions/star50#/series/points/71/value"],
                "invalidation_conditions": ["多来源一致显示拥挤缓解"]
            }
        ],
        "overall_limitations": ["结论仅使用公开证据且不包含个人持仓"]
    }


@pytest.fixture
def public_tree(tmp_path: Path) -> Path:
    from scripts.update_market_data import update_public_tree

    root = tmp_path / "public"
    update_public_tree(root, now=NOW, fixture_mode=True)
    return root


def test_valid_candidate_binds_to_exact_manifest_and_resolvable_references(public_tree: Path) -> None:
    from market_evidence.ai_candidate import validate_candidate

    validated = validate_candidate(valid_candidate(public_tree), public_tree)

    assert validated.evidence_version == load_json(public_tree / "manifest.json")["evidence_version"]
    assert validated.direction_ids == ("hs300", "hstech", "star50")


@pytest.mark.parametrize(
    "mutation,expected",
    [
        (lambda candidate: candidate.update(evidence_version="stale.version"), "version"),
        (lambda candidate: candidate.update(evidence_manifest_sha256="f" * 64), "hash"),
        (lambda candidate: candidate["focus_opportunities"][0].update(direction_id="unknown"), "direction"),
        (lambda candidate: candidate["focus_opportunities"][0].update(thesis="建议立即买入"), "trading"),
        (lambda candidate: candidate["focus_opportunities"][0].update(thesis="核验 https://evil.example/"), "url"),
        (
            lambda candidate: candidate["focus_opportunities"][0].update(
                research_action="buy_now"
            ),
            "invalid",
        ),
        (lambda candidate: candidate.update(schema_drift="unexpected"), "invalid"),
        (lambda candidate: candidate["focus_opportunities"][0].update(thesis="估值处于 12 分位"), "invalid"),
        (lambda candidate: candidate["focus_opportunities"][0].update(current_percentile=12), "invalid"),
        (lambda candidate: candidate["risks"][0].update(account_id="private"), "private"),
        (
            lambda candidate: candidate["focus_opportunities"][0].update(
                supporting_evidence_refs=["directions/hs300#/metrics/current_percentile/value"]
            ),
            "source",
        ),
        (
            lambda candidate: candidate["focus_opportunities"][0].update(
                supporting_evidence_refs=["directions/hs300#/metrics/not_real/value"]
            ),
            "reference",
        ),
    ],
)
def test_invalid_candidates_are_rejected(public_tree: Path, mutation, expected: str) -> None:
    from market_evidence.ai_candidate import CandidateValidationError, validate_candidate

    candidate = copy.deepcopy(valid_candidate(public_tree))
    mutation(candidate)

    with pytest.raises(CandidateValidationError, match=expected):
        validate_candidate(candidate, public_tree)
