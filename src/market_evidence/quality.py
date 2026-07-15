"""Source adoption, conflict, freshness, and gap assessment."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from market_evidence.sources.base import SourceResult


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    adopted_source_id: str | None
    cross_validation: str
    conflicts: tuple[str, ...]
    attempted_source_ids: tuple[str, ...]


def assess_source_quality(
    source_results: list[SourceResult] | tuple[SourceResult, ...],
    *,
    conflict_tolerance_ratio: Decimal = Decimal("0.05"),
) -> QualityAssessment:
    attempted = tuple(result.source_id for result in source_results)
    healthy = [result for result in source_results if result.status == "success" and result.rows]
    adopted = healthy[0].source_id if healthy else None
    if len(healthy) < 2:
        return QualityAssessment(adopted, "unavailable", (), attempted)

    latest_by_source_metric: dict[tuple[str, str], Decimal] = {}
    for result in healthy:
        for row in result.rows:
            key = (result.source_id, row.metric)
            current = latest_by_source_metric.get(key)
            latest_date = max(
                item.trade_date for item in result.rows if item.metric == row.metric
            )
            if row.trade_date == latest_date:
                latest_by_source_metric[key] = row.value
            elif current is None:
                latest_by_source_metric[key] = row.value

    conflicts: list[str] = []
    first = healthy[0]
    first_metrics = {row.metric for row in first.rows}
    for other in healthy[1:]:
        other_metrics = {row.metric for row in other.rows}
        for metric in sorted(first_metrics & other_metrics):
            first_value = latest_by_source_metric[(first.source_id, metric)]
            other_value = latest_by_source_metric[(other.source_id, metric)]
            denominator = max(abs(first_value), abs(other_value))
            difference = Decimal("0") if denominator == 0 else abs(first_value - other_value) / denominator
            if difference > conflict_tolerance_ratio:
                conflicts.append(
                    f"{metric} differs between {first.source_id} and {other.source_id}"
                )

    return QualityAssessment(
        adopted_source_id=adopted,
        cross_validation="conflict" if conflicts else "confirmed",
        conflicts=tuple(conflicts),
        attempted_source_ids=attempted,
    )

