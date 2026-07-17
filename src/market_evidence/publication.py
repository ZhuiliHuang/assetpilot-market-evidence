"""Validate and atomically publish a complete public evidence tree."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from market_evidence.package_builder import sha256_hex
from market_evidence.schema_validation import EvidenceValidationError, validate_document


class PublicationError(RuntimeError):
    """Raised when a staged public tree is incomplete or unsafe."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PublicationError(f"cannot read validated JSON at {path.name}: {error}") from error


def resolve_public_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise PublicationError(f"public path escapes staged root: {relative_path}") from error
    return candidate


def _validate_analysis_entry(
    root: Path,
    manifest: dict[str, Any],
    entry: dict[str, Any],
    *,
    fallback: bool,
) -> dict[str, Any]:
    label = "fallback analysis" if fallback else "analysis"
    expected_path = f"versions/{entry['evidence_version']}/market-analysis.json"
    if entry["package_path"] != expected_path:
        raise PublicationError(f"{label} path does not match evidence version")
    analysis_path = resolve_public_path(root, entry["package_path"])
    analysis = load_json(analysis_path)
    if sha256_hex(analysis) != entry["sha256"]:
        raise PublicationError(f"{label} hash mismatch")
    if analysis["evidence_version"] != entry["evidence_version"]:
        raise PublicationError(f"{label} entry evidence version mismatch")
    if analysis["analysis_date"] != entry["analysis_as_of"]:
        raise PublicationError(f"{label} date mismatch")
    if fallback and entry["evidence_version"] == manifest["evidence_version"]:
        raise PublicationError("fallback analysis must reference an older evidence version")
    if not fallback and entry["evidence_version"] != manifest["evidence_version"]:
        raise PublicationError("analysis evidence version mismatch")
    validate_document("market-analysis", analysis)
    return analysis


def validate_public_tree(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise PublicationError("staged public tree is missing manifest.json")
    manifest = load_json(manifest_path)
    try:
        validate_document("market-data-manifest", manifest)
        analysis_entry = manifest["analysis"]
        fallback_entry = manifest.get("analysis_fallback")
        if analysis_entry is not None and fallback_entry is not None:
            raise PublicationError("manifest cannot publish current and fallback analysis together")
        selected_analysis_entry = analysis_entry or fallback_entry
        if selected_analysis_entry is not None:
            _validate_analysis_entry(
                root,
                manifest,
                selected_analysis_entry,
                fallback=analysis_entry is None,
            )
            latest_analysis = load_json(root / "market-analysis-latest.json")
            if sha256_hex(latest_analysis) != selected_analysis_entry["sha256"]:
                raise PublicationError("latest analysis does not match versioned analysis")
        for category_entry in manifest["categories"]:
            category_path = resolve_public_path(root, category_entry["package_path"])
            category = load_json(category_path)
            if sha256_hex(category) != category_entry["sha256"]:
                raise PublicationError(f"category hash mismatch: {category_entry['category_id']}")
            validate_document("market-category", category)
            for direction_entry in category["directions"]:
                direction_path = resolve_public_path(root, direction_entry["detail_path"])
                direction = load_json(direction_path)
                if sha256_hex(direction) != direction_entry["sha256"]:
                    raise PublicationError(
                        f"direction hash mismatch: {direction_entry['direction_id']}"
                    )
                validate_document("market-direction", direction)
    except EvidenceValidationError as error:
        raise PublicationError(str(error)) from error
    return manifest


def publish_validated_tree(staged_root: Path, destination: Path) -> dict[str, Any]:
    manifest = validate_public_tree(staged_root)
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    incoming = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-incoming-", dir=destination.parent)
    )
    backup = destination.parent / f".{destination.name}-previous"
    try:
        shutil.copytree(staged_root, incoming, dirs_exist_ok=True)
        validate_public_tree(incoming)
        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(incoming, destination)
        except Exception:
            if backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        return manifest
    finally:
        if incoming.exists():
            shutil.rmtree(incoming)
