"""Shared source contracts; adapters preserve their own observations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from market_evidence.normalize import normalize_currency, normalize_index_code


class SourcePayloadError(ValueError):
    """Raised when a public source changes shape or contains ambiguous rows."""


@dataclass(frozen=True, slots=True)
class SourceTarget:
    direction_id: str
    proxy_code: str
    currency: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "proxy_code", normalize_index_code(self.proxy_code))
        object.__setattr__(self, "currency", normalize_currency(self.currency))


@dataclass(frozen=True, slots=True)
class Observation:
    source_id: str
    direction_id: str
    proxy_code: str
    trade_date: date
    metric: str
    value: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class SourceResult:
    source_id: str
    retrieved_at: datetime
    as_of_trade_date: date | None
    license_mode: str
    status: str
    rows: tuple[Observation, ...]
    errors: tuple[str, ...] = ()


class SourceAdapter(ABC):
    source_id: str
    license_mode = "publish_derived_only"

    @abstractmethod
    def fetch(self, target: SourceTarget, start_date: date, end_date: date) -> SourceResult:
        """Fetch one public target within the requested date range."""


def build_result(
    *,
    source_id: str,
    target: SourceTarget,
    retrieved_at: datetime,
    rows: list[Observation],
    expected_latest_date: date | None = None,
    max_age_days: int = 3,
) -> SourceResult:
    if not rows:
        return SourceResult(
            source_id=source_id,
            retrieved_at=retrieved_at,
            as_of_trade_date=None,
            license_mode="publish_derived_only",
            status="empty",
            rows=(),
        )

    keys: set[tuple[date, str]] = set()
    for row in rows:
        key = (row.trade_date, row.metric)
        if key in keys:
            raise SourcePayloadError(f"duplicate observation for {row.trade_date} {row.metric}")
        keys.add(key)
        if row.direction_id != target.direction_id or row.proxy_code != target.proxy_code:
            raise SourcePayloadError("adapter changed the locked source target")

    ordered_rows = tuple(sorted(rows, key=lambda row: (row.trade_date, row.metric)))
    as_of_trade_date = max(row.trade_date for row in ordered_rows)
    status = "success"
    if expected_latest_date and (expected_latest_date - as_of_trade_date).days > max_age_days:
        status = "stale"
    return SourceResult(
        source_id=source_id,
        retrieved_at=retrieved_at,
        as_of_trade_date=as_of_trade_date,
        license_mode="publish_derived_only",
        status=status,
        rows=ordered_rows,
    )
