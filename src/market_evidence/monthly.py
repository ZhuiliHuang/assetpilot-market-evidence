"""Month-end sampling without collapsing independent sources or metrics."""

from __future__ import annotations

from collections.abc import Iterable

from market_evidence.sources.base import Observation


def select_month_end(rows: Iterable[Observation]) -> tuple[Observation, ...]:
    selected: dict[tuple[str, str, int, int], Observation] = {}
    for row in rows:
        key = (row.source_id, row.metric, row.trade_date.year, row.trade_date.month)
        current = selected.get(key)
        if current is None or row.trade_date > current.trade_date:
            selected[key] = row
    return tuple(
        sorted(
            selected.values(),
            key=lambda row: (row.source_id, row.metric, row.trade_date),
        )
    )

