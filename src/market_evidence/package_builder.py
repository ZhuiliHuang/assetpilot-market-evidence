"""Build compact, deterministic public evidence packages."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from market_evidence.downsample import downsample_points
from market_evidence.monthly import select_month_end
from market_evidence.percentiles import (
    PercentilePoint,
    PercentileValue,
    calculate_latest_percentile,
    rolling_percentile_series,
)
from market_evidence.quality import assess_source_quality
from market_evidence.sources.base import Observation, SourceResult


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_VERSION = "2026-07-15.1"
CATEGORY_ORDER = (
    ("broad_style", "宽基/风格"),
    ("industry", "行业"),
    ("hong_kong", "港股"),
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def iso_datetime(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def numeric(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def metric_payload(value: PercentileValue) -> dict[str, Any]:
    return {
        "value": numeric(value.value),
        "missing_reason": value.missing_reason,
    }


def conservative_metric(values: Iterable[PercentileValue]) -> PercentileValue:
    values = tuple(values)
    available = [value for value in values if value.value is not None]
    if available:
        selected = max(available, key=lambda value: value.value or Decimal("-1"))
        return PercentileValue(selected.value, selected.sample_count, None)
    sample_count = max((value.sample_count for value in values), default=0)
    reason = next((value.missing_reason for value in values if value.missing_reason), "no usable metric")
    return PercentileValue(None, sample_count, reason)


def conservative_series(series_by_metric: dict[str, tuple[PercentilePoint, ...]]) -> list[dict[str, Any]]:
    points_by_date: dict[date, list[PercentilePoint]] = {}
    for points in series_by_metric.values():
        for point in points:
            points_by_date.setdefault(point.trade_date, []).append(point)

    output: list[dict[str, Any]] = []
    for trade_date in sorted(points_by_date):
        candidates = points_by_date[trade_date]
        available = [point for point in candidates if point.value is not None]
        if available:
            selected = max(available, key=lambda point: point.value or Decimal("-1"))
            output.append(
                {"date": trade_date.isoformat(), "value": numeric(selected.value), "missing_reason": None}
            )
        else:
            output.append(
                {
                    "date": trade_date.isoformat(),
                    "value": None,
                    "missing_reason": next(
                        (point.missing_reason for point in candidates if point.missing_reason),
                        "no usable metric",
                    ),
                }
            )
    return output


def detect_gaps(rows: tuple[Observation, ...]) -> list[dict[str, str]]:
    dates = sorted({row.trade_date for row in rows})
    gaps: list[dict[str, str]] = []
    for previous, current in zip(dates, dates[1:]):
        if (current - previous).days <= 45:
            continue
        gaps.append(
            {
                "start_date": previous.isoformat(),
                "end_date": current.isoformat(),
                "reason": "source has no independent month-end observation in this interval",
                "decision_impact": "percentile continuity is reduced; use the result as degraded evidence",
            }
        )
    return gaps


def source_homepages() -> dict[str, str]:
    registry = json.loads((REPOSITORY_ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
    return {source["id"]: source["homepage_url"] for source in registry["sources"]}


def _version_seed(direction: dict[str, Any], source_results: list[SourceResult], now: datetime) -> str:
    seed = {
        "direction_id": direction["id"],
        "now": iso_datetime(now),
        "sources": [
            {
                "source_id": result.source_id,
                "status": result.status,
                "as_of": result.as_of_trade_date.isoformat() if result.as_of_trade_date else None,
                "rows": [
                    [row.trade_date.isoformat(), row.metric, str(row.value)] for row in result.rows
                ],
            }
            for result in source_results
        ],
    }
    return f"{now.date().isoformat()}.{sha256_hex(seed)[:12]}"


def build_direction_package(
    direction: dict[str, Any],
    source_results: list[SourceResult],
    now: datetime,
    *,
    evidence_version: str | None = None,
) -> dict[str, Any]:
    quality = assess_source_quality(source_results)
    adopted = next(
        (result for result in source_results if result.source_id == quality.adopted_source_id),
        None,
    )
    evidence_version = evidence_version or _version_seed(direction, source_results, now)
    monthly_rows = select_month_end(adopted.rows if adopted else ())
    metrics_present = {row.metric for row in monthly_rows}
    valuation_metrics = [metric for metric in ("pe", "pb") if metric in metrics_present]
    selected_metrics = valuation_metrics or (["price"] if "price" in metrics_present else [])

    latest_by_metric: dict[str, PercentileValue] = {}
    five_year_by_metric: dict[str, PercentileValue] = {}
    all_history_by_metric: dict[str, PercentileValue] = {}
    series_by_metric: dict[str, tuple[PercentilePoint, ...]] = {}
    for metric in selected_metrics:
        rows = tuple(row for row in monthly_rows if row.metric == metric)
        latest_by_metric[metric] = calculate_latest_percentile(rows)
        five_year_by_metric[metric] = calculate_latest_percentile(rows, window_months=60)
        all_history_by_metric[metric] = calculate_latest_percentile(rows)
        series_by_metric[metric] = rolling_percentile_series(rows)

    current = conservative_metric(latest_by_metric.values())
    five_year = conservative_metric(five_year_by_metric.values())
    all_history = conservative_metric(all_history_by_metric.values())
    chart_points = downsample_points(conservative_series(series_by_metric), max_points=360)
    current_point = chart_points[-1] if chart_points else {"date": None, "value": None, "missing_reason": "no usable history"}

    if adopted is None:
        status = "missing"
    elif current.value is None or quality.cross_validation == "conflict":
        status = "degraded"
    else:
        status = "ready"

    homepages = source_homepages()
    source_evidence = []
    for result in source_results:
        role = "adopted" if result.source_id == quality.adopted_source_id else "cross_check"
        source_evidence.append(
            {
                "source_id": result.source_id,
                "role": role,
                "as_of": result.as_of_trade_date.isoformat() if result.as_of_trade_date else None,
                "url": homepages.get(result.source_id, "https://example.com/unregistered-source"),
                "cross_validation": quality.cross_validation if result.rows else "unavailable",
                "last_attempt": iso_datetime(result.retrieved_at),
            }
        )
    if not source_evidence:
        source_evidence.append(
            {
                "source_id": "no_source_succeeded",
                "role": "attempted",
                "as_of": None,
                "url": "https://github.com/",
                "cross_validation": "unavailable",
                "last_attempt": iso_datetime(now),
            }
        )

    data_as_of = adopted.as_of_trade_date if adopted and adopted.as_of_trade_date else now.date()
    first_date = monthly_rows[0].trade_date if monthly_rows else None
    last_date = monthly_rows[-1].trade_date if monthly_rows else None
    sample_count = len({(row.trade_date.year, row.trade_date.month) for row in monthly_rows if row.metric in selected_metrics})
    series_metric = "valuation_percentile" if valuation_metrics else "price_percentile"

    return {
        "schema_version": "1.0.0",
        "registry_version": REGISTRY_VERSION,
        "evidence_version": evidence_version,
        "direction_id": direction["id"],
        "category_id": direction["category_id"],
        "display_name": direction["display_name"],
        "data_as_of": data_as_of.isoformat(),
        "status": status,
        "proxy": {
            "definition": direction["proxy_definition"],
            "code": direction["primary_proxy_code"],
            "publisher": direction["publisher"],
            "currency": direction["currency"],
            "calendar": direction["calendar"],
        },
        "valuation_applicable": direction["valuation_applicable"],
        "metrics": {
            "current_percentile": metric_payload(current),
            "five_year_percentile": metric_payload(five_year),
            "all_history_percentile": metric_payload(all_history),
        },
        "series": {
            "metric": series_metric,
            "unit": "percentile",
            "start_date": first_date.isoformat() if first_date else None,
            "end_date": last_date.isoformat() if last_date else None,
            "sample_count": sample_count,
            "points": chart_points,
        },
        "chart": {
            "reference_bands": [20, 50, 80],
            "current_point": current_point,
            "downsampled": len(chart_points) < len(conservative_series(series_by_metric)),
        },
        "quality": {
            "adopted_source_id": quality.adopted_source_id,
            "cross_validation": quality.cross_validation,
            "conflicts": list(quality.conflicts),
            "attempted_source_ids": list(quality.attempted_source_ids),
            "freshness": "fresh" if adopted and adopted.status == "success" else "degraded",
        },
        "source_evidence": source_evidence,
        "gaps": detect_gaps(monthly_rows),
        "calculation": {
            "method": "empirical_cdf_midrank",
            "metric_definition": "PE and PB are ranked separately; the higher available rank is the conservative valuation temperature. Yield remains separate.",
            "software_version": "0.1.0",
            "calculated_at": iso_datetime(now),
        },
    }


def build_category_packages(packages: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    evidence_version = packages[0]["evidence_version"] if packages else f"{now.date().isoformat()}.00000000"
    output = []
    for category_id, display_name in CATEGORY_ORDER:
        members = [package for package in packages if package["category_id"] == category_id]
        output.append(
            {
                "schema_version": "1.0.0",
                "registry_version": REGISTRY_VERSION,
                "evidence_version": evidence_version,
                "category_id": category_id,
                "display_name": display_name,
                "data_as_of": max((package["data_as_of"] for package in members), default=now.date().isoformat()),
                "summary": "Historical percentiles are deterministic public evidence, not a return promise.",
                "directions": [
                    {
                        "direction_id": package["direction_id"],
                        "display_name": package["display_name"],
                        "status": package["status"],
                        **package["metrics"],
                        "sample_count": package["series"]["sample_count"],
                        "series_preview": downsample_points(
                            package["series"]["points"],
                            max_points=60,
                        ),
                        "detail_path": f"versions/{evidence_version}/directions/{package['direction_id']}.json",
                        "sha256": sha256_hex(package),
                    }
                    for package in members
                ],
            }
        )
    return output


def build_manifest(
    packages: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    *,
    expected_trade_date: date,
    now: datetime,
) -> dict[str, Any]:
    evidence_version = packages[0]["evidence_version"] if packages else f"{now.date().isoformat()}.00000000"
    return {
        "schema_version": "1.0.0",
        "registry_version": REGISTRY_VERSION,
        "evidence_version": evidence_version,
        "generated_at": iso_datetime(now),
        "data_as_of": expected_trade_date.isoformat(),
        "categories": [
            {
                "category_id": category["category_id"],
                "package_path": f"versions/{evidence_version}/categories/{category['category_id']}.json",
                "sha256": sha256_hex(category),
            }
            for category in categories
        ],
        "analysis": None,
        "degraded_sources": [],
    }


def build_market_packages(
    directions: list[dict[str, Any]],
    source_results_by_direction: dict[str, list[SourceResult]],
    now: datetime,
) -> dict[str, Any]:
    version_seed = [
        _version_seed(
            direction,
            source_results_by_direction.get(direction["id"], []),
            now,
        )
        for direction in directions
    ]
    evidence_version = f"{now.date().isoformat()}.{sha256_hex(version_seed)[:12]}"
    direction_packages = [
        build_direction_package(
            direction,
            source_results_by_direction.get(direction["id"], []),
            now,
            evidence_version=evidence_version,
        )
        for direction in directions
    ]
    category_packages = build_category_packages(direction_packages, now)
    data_dates = [date.fromisoformat(package["data_as_of"]) for package in direction_packages]
    expected_trade_date = max(data_dates, default=now.date())
    manifest = build_manifest(
        direction_packages,
        category_packages,
        expected_trade_date=expected_trade_date,
        now=now,
    )
    archive_manifest = {
        "schema_version": "1.0.0",
        "entries": [
            {
                "evidence_version": evidence_version,
                "data_as_of": manifest["data_as_of"],
                "manifest_path": f"versions/{evidence_version}/manifest.json",
                "sha256": sha256_hex(manifest),
            }
        ],
    }
    return {
        "evidence_version": evidence_version,
        "directions": direction_packages,
        "categories": category_packages,
        "manifest": manifest,
        "archive_manifest": archive_manifest,
    }
