"""Promote a validated AI candidate into an official analysis package."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from market_evidence.ai_candidate import CandidateValidationError, validate_candidate
from market_evidence.package_builder import canonical_json_bytes, iso_datetime, sha256_hex
from market_evidence.publication import load_json, publish_validated_tree
from market_evidence.schema_validation import EvidenceValidationError, validate_document


_CANDIDATE_NAME = re.compile(r"^(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})\.json$")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _candidate_repository_path(candidate_path: Path, candidate: dict[str, Any]) -> str:
    match = _CANDIDATE_NAME.fullmatch(candidate_path.name)
    if candidate_path.parent.name != "ai-inbox" or not match:
        raise CandidateValidationError("candidate path must be ai-inbox/YYYY-MM-DD.json")
    if match.group("date") != candidate["analysis_date"]:
        raise CandidateValidationError("candidate path date must match analysis date")
    return f"ai-inbox/{candidate_path.name}"


def build_analysis(
    candidate: dict[str, Any],
    candidate_path: Path,
    *,
    published_at: datetime,
) -> dict[str, Any]:
    repository_path = _candidate_repository_path(candidate_path, candidate)
    candidate_sha = sha256_hex(candidate)
    analysis = {
        "schema_version": "1.0.0",
        "analysis_version": f"{candidate['analysis_date']}.{candidate_sha[:12]}",
        "evidence_version": candidate["evidence_version"],
        "evidence_manifest_sha256": candidate["evidence_manifest_sha256"],
        "analysis_date": candidate["analysis_date"],
        "published_at": iso_datetime(published_at),
        "candidate_path": repository_path,
        "candidate_sha256": candidate_sha,
        "focus_opportunities": candidate["focus_opportunities"],
        "risks": candidate["risks"],
        "overall_limitations": candidate["overall_limitations"],
    }
    try:
        validate_document("market-analysis", analysis)
    except EvidenceValidationError as error:
        raise CandidateValidationError(f"invalid official analysis: {error}") from error
    return analysis


def publish_candidate(
    candidate_path: Path,
    public_root: Path,
    *,
    published_at: datetime,
) -> dict[str, Any]:
    """Validate first, then atomically publish without mutating on rejection."""

    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CandidateValidationError("invalid candidate JSON") from error
    if not isinstance(candidate, dict):
        raise CandidateValidationError("invalid candidate JSON object")

    validate_candidate(candidate, public_root)
    analysis = build_analysis(candidate, candidate_path, published_at=published_at)

    public_root = public_root.resolve()
    staged_root = Path(
        tempfile.mkdtemp(prefix="assetpilot-analysis-stage-", dir=public_root.parent)
    )
    try:
        shutil.copytree(public_root, staged_root, dirs_exist_ok=True)
        manifest = load_json(staged_root / "manifest.json")
        evidence_version = manifest["evidence_version"]
        analysis_path = f"versions/{evidence_version}/market-analysis.json"
        _write_json(staged_root / analysis_path, analysis)
        _write_json(staged_root / "market-analysis-latest.json", analysis)

        manifest["analysis"] = {
            "analysis_as_of": analysis["analysis_date"],
            "package_path": analysis_path,
            "sha256": sha256_hex(analysis),
            "evidence_version": evidence_version,
        }
        _write_json(staged_root / "manifest.json", manifest)
        _write_json(staged_root / "versions" / evidence_version / "manifest.json", manifest)

        archive_path = staged_root / "archive-manifest.json"
        if archive_path.is_file():
            archive = load_json(archive_path)
            for entry in archive.get("entries", []):
                if entry.get("evidence_version") == evidence_version:
                    entry["sha256"] = sha256_hex(manifest)
                    break
            _write_json(archive_path, archive)

        publish_validated_tree(staged_root, public_root)
        return analysis
    finally:
        if staged_root.exists():
            shutil.rmtree(staged_root)
