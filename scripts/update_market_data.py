from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from market_evidence.package_builder import (
    build_market_packages,
    canonical_json_bytes,
    sha256_hex,
)
from market_evidence.publication import PublicationError, load_json, publish_validated_tree
from market_evidence.sources.base import Observation, SourceResult


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def month_sequence(end_date: date, count: int) -> list[date]:
    absolute_end = end_date.year * 12 + end_date.month - 1
    output = []
    for offset in range(count - 1, -1, -1):
        absolute_month = absolute_end - offset
        year, zero_based_month = divmod(absolute_month, 12)
        output.append(date(year, zero_based_month + 1, min(end_date.day, 28)))
    return output


def locked_directions() -> list[dict[str, Any]]:
    registry = load_json(REPOSITORY_ROOT / "config" / "directions.json")
    return [
        direction for category in registry["categories"] for direction in category["directions"]
    ]


def fixture_source_results(direction: dict[str, Any], now: datetime) -> list[SourceResult]:
    results: list[SourceResult] = []
    for source_index, source_id in enumerate(
        ("akshare_csindex_valuation", "eastmoney_index_history")
    ):
        rows = []
        for index, trade_date in enumerate(month_sequence(now.date(), 72)):
            adjustment = Decimal(source_index) / Decimal("100")
            rows.extend(
                [
                    Observation(
                        source_id,
                        direction["id"],
                        direction["primary_proxy_code"],
                        trade_date,
                        "pe",
                        Decimal("10") + Decimal(index) / Decimal("5") + adjustment,
                        direction["currency"],
                    ),
                    Observation(
                        source_id,
                        direction["id"],
                        direction["primary_proxy_code"],
                        trade_date,
                        "pb",
                        Decimal("1") + Decimal(index) / Decimal("100") + adjustment,
                        direction["currency"],
                    ),
                ]
            )
        results.append(
            SourceResult(
                source_id=source_id,
                retrieved_at=now,
                as_of_trade_date=rows[-1].trade_date,
                license_mode="publish_derived_only",
                status="success",
                rows=tuple(rows),
            )
        )
    return results


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def previous_direction_summaries(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = load_json(root / "manifest.json")
    summaries: dict[str, dict[str, Any]] = {}
    for category_entry in manifest["categories"]:
        category = load_json(root / category_entry["package_path"])
        for direction in category["directions"]:
            summaries[direction["direction_id"]] = direction
    return manifest, summaries


def write_built_tree(
    staged_root: Path,
    built: dict[str, Any],
    *,
    now: datetime,
    failed_direction_ids: set[str],
    previous_manifest: dict[str, Any] | None,
    previous_summaries: dict[str, dict[str, Any]],
) -> None:
    version = built["evidence_version"]
    version_root = staged_root / "versions" / version
    for package in built["directions"]:
        if package["direction_id"] in failed_direction_ids:
            continue
        write_json(version_root / "directions" / f"{package['direction_id']}.json", package)

    categories = built["categories"]
    for category in categories:
        for summary in category["directions"]:
            direction_id = summary["direction_id"]
            if direction_id not in failed_direction_ids:
                continue
            previous = previous_summaries.get(direction_id)
            if not previous:
                raise PublicationError(f"cannot retain {direction_id}: no previous valid direction")
            summary.clear()
            summary.update(previous)
            summary["status"] = "degraded"
        write_json(version_root / "categories" / f"{category['category_id']}.json", category)

    manifest = built["manifest"]
    for category_entry, category in zip(manifest["categories"], categories):
        category_entry["sha256"] = sha256_hex(category)
    if failed_direction_ids:
        last_date = previous_manifest["data_as_of"] if previous_manifest else None
        manifest["degraded_sources"] = [
            {
                "source_id": f"{direction_id}_public_source_chain",
                "failed_at": now.isoformat().replace("+00:00", "Z"),
                "last_successful_date": last_date,
                "impact": "retained the last validated direction package; current evidence is degraded",
            }
            for direction_id in sorted(failed_direction_ids)
        ]

    write_json(version_root / "manifest.json", manifest)
    write_json(staged_root / "manifest.json", manifest)

    archive = built["archive_manifest"]
    previous_archive_path = staged_root / "archive-manifest.json"
    if previous_archive_path.is_file():
        previous_archive = load_json(previous_archive_path)
        archive["entries"].extend(previous_archive.get("entries", []))
        archive["entries"] = archive["entries"][:30]
    archive["entries"][0]["sha256"] = sha256_hex(manifest)
    write_json(staged_root / "archive-manifest.json", archive)


def update_public_tree(
    destination: Path,
    *,
    now: datetime | None = None,
    fixture_mode: bool = False,
    failed_direction_ids: set[str] | None = None,
    total_failure: bool = False,
) -> bool:
    if total_failure:
        return False
    if not fixture_mode:
        raise PublicationError("live source probes are not enabled until end-to-end acceptance")

    now = now or datetime.now(timezone.utc)
    failed_direction_ids = failed_direction_ids or set()
    directions = locked_directions()
    known_direction_ids = {direction["id"] for direction in directions}
    unknown = failed_direction_ids - known_direction_ids
    if unknown:
        raise PublicationError(f"unknown failed directions: {sorted(unknown)}")

    source_results_by_direction = {
        direction["id"]: fixture_source_results(direction, now) for direction in directions
    }
    built = build_market_packages(directions, source_results_by_direction, now)
    staging_parent = destination.resolve().parent
    staging_parent.mkdir(parents=True, exist_ok=True)
    staged_root = Path(tempfile.mkdtemp(prefix="assetpilot-evidence-stage-", dir=staging_parent))
    try:
        previous_manifest = None
        previous_summaries: dict[str, dict[str, Any]] = {}
        if destination.exists():
            shutil.copytree(destination, staged_root, dirs_exist_ok=True)
            previous_manifest, previous_summaries = previous_direction_summaries(staged_root)
        write_built_tree(
            staged_root,
            built,
            now=now,
            failed_direction_ids=failed_direction_ids,
            previous_manifest=previous_manifest,
            previous_summaries=previous_summaries,
        )
        publish_validated_tree(staged_root, destination)
        return True
    finally:
        if staged_root.exists():
            shutil.rmtree(staged_root)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build public market evidence packages.")
    parser.add_argument("--fixtures", action="store_true", help="Use deterministic public-only fixtures.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fail-direction", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    update_public_tree(
        args.output,
        fixture_mode=args.fixtures,
        failed_direction_ids=set(args.fail_direction),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
