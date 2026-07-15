from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)


def locked_direction(direction_id: str) -> dict:
    registry = json.loads((REPOSITORY_ROOT / "config" / "directions.json").read_text(encoding="utf-8"))
    return next(
        direction
        for category in registry["categories"]
        for direction in category["directions"]
        if direction["id"] == direction_id
    )


def source_results(direction_id: str = "hs300", proxy_code: str = "000300"):
    from market_evidence.sources.base import Observation, SourceResult

    results = []
    for source_index, source_id in enumerate(("akshare_csindex_valuation", "eastmoney_index_history")):
        rows = []
        for index in range(72):
            year = 2020 + index // 12
            month = index % 12 + 1
            trade_date = date(year, month, 28)
            adjustment = Decimal(source_index) / Decimal("100")
            rows.extend(
                [
                    Observation(source_id, direction_id, proxy_code, trade_date, "pe", Decimal(10 + index) + adjustment, "CNY"),
                    Observation(source_id, direction_id, proxy_code, trade_date, "pb", Decimal("1.0") + Decimal(index) / Decimal("100") + adjustment, "CNY"),
                ]
            )
        results.append(
            SourceResult(
                source_id=source_id,
                retrieved_at=NOW,
                as_of_trade_date=date(2025, 12, 28),
                license_mode="publish_derived_only",
                status="success",
                rows=tuple(rows),
            )
        )
    return results


def test_direction_package_is_schema_valid_evidence_rich_and_deterministic() -> None:
    from market_evidence.package_builder import build_direction_package, canonical_json_bytes
    from market_evidence.schema_validation import validate_document

    first = build_direction_package(locked_direction("hs300"), source_results(), NOW)
    second = build_direction_package(locked_direction("hs300"), source_results(), NOW)

    validate_document("market-direction", first)
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert first["chart"]["reference_bands"] == [20, 50, 80]
    assert first["chart"]["current_point"]["value"] == first["metrics"]["current_percentile"]["value"]
    assert 60 <= first["series"]["sample_count"] <= 360
    assert first["quality"]["adopted_source_id"] == "akshare_csindex_valuation"
    assert first["quality"]["cross_validation"] == "confirmed"


def test_category_and_manifest_packages_stay_within_initial_size_budgets() -> None:
    from market_evidence.package_builder import (
        build_category_packages,
        build_direction_package,
        build_manifest,
        canonical_json_bytes,
    )
    from market_evidence.schema_validation import validate_document

    package = build_direction_package(locked_direction("hs300"), source_results(), NOW)
    packages = [package]
    categories = build_category_packages(packages, NOW)
    manifest = build_manifest(packages, categories, expected_trade_date=date(2026, 7, 15), now=NOW)

    validate_document("market-data-manifest", manifest)
    assert len(canonical_json_bytes(manifest)) < 100_000
    assert all(len(canonical_json_bytes(category)) < 500_000 for category in categories)
    assert sum(len(canonical_json_bytes(category)) for category in categories) < 2_000_000


def test_full_registry_builds_fifteen_directions_three_categories_and_daily_archive() -> None:
    from market_evidence.package_builder import build_market_packages, canonical_json_bytes
    from market_evidence.schema_validation import validate_document
    from market_evidence.sources.base import Observation, SourceResult

    registry = json.loads((REPOSITORY_ROOT / "config" / "directions.json").read_text(encoding="utf-8"))
    directions = [
        direction for category in registry["categories"] for direction in category["directions"]
    ]
    results_by_direction = {}
    for direction in directions:
        rows = []
        for index in range(60):
            year = 2021 + index // 12
            month = index % 12 + 1
            trade_date = date(year, month, 28)
            rows.extend(
                [
                    Observation(
                        "akshare_csindex_valuation",
                        direction["id"],
                        direction["primary_proxy_code"],
                        trade_date,
                        "pe",
                        Decimal(10 + index),
                        direction["currency"],
                    ),
                    Observation(
                        "akshare_csindex_valuation",
                        direction["id"],
                        direction["primary_proxy_code"],
                        trade_date,
                        "pb",
                        Decimal("1") + Decimal(index) / Decimal("100"),
                        direction["currency"],
                    ),
                ]
            )
        results_by_direction[direction["id"]] = [
            SourceResult(
                source_id="akshare_csindex_valuation",
                retrieved_at=NOW,
                as_of_trade_date=date(2025, 12, 28),
                license_mode="publish_derived_only",
                status="success",
                rows=tuple(rows),
            )
        ]

    built = build_market_packages(directions, results_by_direction, NOW)

    assert len(built["directions"]) == 15
    assert [len(category["directions"]) for category in built["categories"]] == [6, 6, 3]
    assert len({package["evidence_version"] for package in built["directions"]}) == 1
    for package in built["directions"]:
        validate_document("market-direction", package)
    for category in built["categories"]:
        validate_document("market-category", category)
    validate_document("market-data-manifest", built["manifest"])
    assert built["archive_manifest"]["entries"][0]["evidence_version"] == built["manifest"]["evidence_version"]
    assert len(canonical_json_bytes(built["manifest"])) < 100_000
