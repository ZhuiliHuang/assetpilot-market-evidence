"""Recover a previously validated analysis without relabelling its evidence version."""

from __future__ import annotations

import copy
import shutil
import tempfile
from pathlib import Path
from typing import Any

from market_evidence.package_builder import canonical_json_bytes, sha256_hex
from market_evidence.publication import (
    load_json,
    publish_validated_tree,
    validate_public_tree,
)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def recover_analysis_reference(current_root: Path, historical_root: Path) -> bool:
    """Restore the latest validated historical analysis into an otherwise empty tree."""

    current_root = current_root.resolve()
    historical_root = historical_root.resolve()
    current_manifest = validate_public_tree(current_root)
    if current_manifest.get("analysis") or current_manifest.get("analysis_fallback"):
        return False

    historical_manifest = validate_public_tree(historical_root)
    historical_entry = historical_manifest.get("analysis") or historical_manifest.get(
        "analysis_fallback"
    )
    if not historical_entry:
        return False

    staged_root = Path(
        tempfile.mkdtemp(prefix="assetpilot-analysis-recovery-", dir=current_root.parent)
    )
    try:
        shutil.copytree(current_root, staged_root, dirs_exist_ok=True)
        entry = copy.deepcopy(historical_entry)
        source_analysis = historical_root / entry["package_path"]
        target_analysis = staged_root / entry["package_path"]
        target_analysis.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_analysis, target_analysis)
        shutil.copy2(
            historical_root / "market-analysis-latest.json",
            staged_root / "market-analysis-latest.json",
        )

        manifest = load_json(staged_root / "manifest.json")
        if entry["evidence_version"] == manifest["evidence_version"]:
            manifest["analysis"] = entry
            manifest["analysis_fallback"] = None
        else:
            manifest["analysis"] = None
            manifest["analysis_fallback"] = entry
        _write_json(staged_root / "manifest.json", manifest)
        _write_json(
            staged_root / "versions" / manifest["evidence_version"] / "manifest.json",
            manifest,
        )

        archive_path = staged_root / "archive-manifest.json"
        if archive_path.is_file():
            archive = load_json(archive_path)
            for archive_entry in archive.get("entries", []):
                if archive_entry.get("evidence_version") == manifest["evidence_version"]:
                    archive_entry["sha256"] = sha256_hex(manifest)
            _write_json(archive_path, archive)

        validate_public_tree(staged_root)
        publish_validated_tree(staged_root, current_root)
        return True
    finally:
        if staged_root.exists():
            shutil.rmtree(staged_root)
