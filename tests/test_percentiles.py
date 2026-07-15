from __future__ import annotations

from datetime import date
from decimal import Decimal


def test_month_end_selection_keeps_each_source_and_metric_separate() -> None:
    from market_evidence.monthly import select_month_end
    from market_evidence.sources.base import Observation

    rows = [
        Observation("one", "hs300", "000300", date(2026, 1, 15), "pe", Decimal("10"), "CNY"),
        Observation("one", "hs300", "000300", date(2026, 1, 31), "pe", Decimal("11"), "CNY"),
        Observation("one", "hs300", "000300", date(2026, 1, 31), "pb", Decimal("1.2"), "CNY"),
        Observation("two", "hs300", "000300", date(2026, 1, 30), "pe", Decimal("10.9"), "CNY"),
    ]

    selected = select_month_end(rows)

    assert [(row.source_id, row.metric, row.trade_date) for row in selected] == [
        ("one", "pb", date(2026, 1, 31)),
        ("one", "pe", date(2026, 1, 31)),
        ("two", "pe", date(2026, 1, 30)),
    ]


def test_midrank_percentile_handles_ties_deterministically() -> None:
    from market_evidence.percentiles import percent_rank_midrank

    assert percent_rank_midrank(
        [Decimal("1"), Decimal("2"), Decimal("2"), Decimal("3")], Decimal("2")
    ) == Decimal("50.00")


def test_percentiles_enforce_independent_month_gate_and_five_year_window() -> None:
    from market_evidence.percentiles import calculate_latest_percentile
    from market_evidence.sources.base import Observation

    rows = []
    for index in range(72):
        year = 2020 + index // 12
        month = index % 12 + 1
        rows.append(
            Observation(
                "one",
                "hs300",
                "000300",
                date(year, month, 28),
                "pe",
                Decimal(index + 1),
                "CNY",
            )
        )

    too_short = calculate_latest_percentile(rows[:59], min_independent_months=60)
    five_year = calculate_latest_percentile(rows, window_months=60, min_independent_months=60)
    all_history = calculate_latest_percentile(rows, min_independent_months=60)

    assert too_short.value is None
    assert "60" in too_short.missing_reason
    assert five_year.sample_count == 60
    assert all_history.sample_count == 72
    assert five_year.value == Decimal("99.17")
    assert all_history.value == Decimal("99.31")

