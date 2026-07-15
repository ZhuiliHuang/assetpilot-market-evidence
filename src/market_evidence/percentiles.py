"""Deterministic empirical percentile calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from market_evidence.monthly import select_month_end
from market_evidence.sources.base import Observation


PERCENT_QUANTUM = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class PercentileValue:
    value: Decimal | None
    sample_count: int
    missing_reason: str | None


@dataclass(frozen=True, slots=True)
class PercentilePoint:
    trade_date: date
    value: Decimal | None
    sample_count: int
    missing_reason: str | None


def percent_rank_midrank(values: Iterable[Decimal], current: Decimal) -> Decimal:
    ordered = tuple(values)
    if not ordered:
        raise ValueError("percentile requires at least one value")
    less = sum(value < current for value in ordered)
    equal = sum(value == current for value in ordered)
    rank = (Decimal(less) + Decimal(equal) / Decimal("2")) / Decimal(len(ordered))
    return (rank * Decimal("100")).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)


def _one_series(rows: Iterable[Observation]) -> tuple[Observation, ...]:
    monthly = select_month_end(rows)
    if not monthly:
        return ()
    signatures = {(row.source_id, row.metric) for row in monthly}
    if len(signatures) != 1:
        raise ValueError("percentile calculation requires exactly one source and metric")
    return tuple(sorted(monthly, key=lambda row: row.trade_date))


def calculate_latest_percentile(
    rows: Iterable[Observation],
    *,
    window_months: int | None = None,
    min_independent_months: int = 60,
) -> PercentileValue:
    series = _one_series(rows)
    if window_months is not None:
        series = series[-window_months:]
    sample_count = len(series)
    if sample_count < min_independent_months:
        return PercentileValue(
            value=None,
            sample_count=sample_count,
            missing_reason=f"requires at least {min_independent_months} independent monthly observations",
        )
    current = series[-1].value
    return PercentileValue(
        value=percent_rank_midrank((row.value for row in series), current),
        sample_count=sample_count,
        missing_reason=None,
    )


def rolling_percentile_series(
    rows: Iterable[Observation],
    *,
    window_months: int | None = None,
    min_independent_months: int = 60,
) -> tuple[PercentilePoint, ...]:
    series = _one_series(rows)
    points: list[PercentilePoint] = []
    for index, row in enumerate(series):
        history = series[: index + 1]
        if window_months is not None:
            history = history[-window_months:]
        sample_count = len(history)
        if sample_count < min_independent_months:
            points.append(
                PercentilePoint(
                    trade_date=row.trade_date,
                    value=None,
                    sample_count=sample_count,
                    missing_reason=f"requires at least {min_independent_months} independent monthly observations",
                )
            )
            continue
        points.append(
            PercentilePoint(
                trade_date=row.trade_date,
                value=percent_rank_midrank((item.value for item in history), row.value),
                sample_count=sample_count,
                missing_reason=None,
            )
        )
    return tuple(points)

