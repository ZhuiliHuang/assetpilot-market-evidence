from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal


def make_result(source_id: str, latest_value: str, *, status: str = "success"):
    from market_evidence.sources.base import Observation, SourceResult

    rows = (
        Observation(source_id, "hs300", "000300", date(2026, 6, 30), "pe", Decimal("10"), "CNY"),
        Observation(source_id, "hs300", "000300", date(2026, 7, 15), "pe", Decimal(latest_value), "CNY"),
    )
    return SourceResult(
        source_id=source_id,
        retrieved_at=datetime(2026, 7, 15, 12, tzinfo=timezone.utc),
        as_of_trade_date=date(2026, 7, 15),
        license_mode="publish_derived_only",
        status=status,
        rows=rows,
    )


def test_quality_selects_first_healthy_source_and_confirms_close_values() -> None:
    from market_evidence.quality import assess_source_quality

    assessment = assess_source_quality([make_result("primary", "11"), make_result("check", "11.2")])

    assert assessment.adopted_source_id == "primary"
    assert assessment.cross_validation == "confirmed"
    assert assessment.conflicts == ()


def test_quality_marks_material_conflict_without_merging_it_away() -> None:
    from market_evidence.quality import assess_source_quality

    assessment = assess_source_quality([make_result("primary", "11"), make_result("check", "14")])

    assert assessment.cross_validation == "conflict"
    assert assessment.conflicts
    assert assessment.attempted_source_ids == ("primary", "check")

