from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest


FIXTURE_DIRECTORY = Path(__file__).resolve().parent / "fixtures" / "sources"
TARGET = None
RETRIEVED_AT = datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)


def source_target():
    from market_evidence.sources.base import SourceTarget

    return SourceTarget(direction_id="hs300", proxy_code="000300", currency="CNY")


def load_json(name: str) -> dict:
    return json.loads((FIXTURE_DIRECTORY / name).read_text(encoding="utf-8"))


def test_csindex_adapter_preserves_current_and_monthly_metrics() -> None:
    from market_evidence.sources.csindex import CsindexValuationAdapter

    result = CsindexValuationAdapter().parse_payload(
        load_json("csindex-valuation.json"),
        source_target(),
        RETRIEVED_AT,
        expected_latest_date=date(2026, 7, 15),
    )

    assert result.status == "success"
    assert result.as_of_trade_date == date(2026, 7, 15)
    assert {row.metric for row in result.rows} == {"pe", "pb", "dividend_yield"}
    assert len(result.rows) == 6
    assert result.license_mode == "publish_derived_only"


def test_price_adapters_keep_source_rows_separate() -> None:
    from market_evidence.sources.eastmoney import EastmoneyPriceAdapter
    from market_evidence.sources.stooq import StooqPriceAdapter

    eastmoney = EastmoneyPriceAdapter().parse_payload(
        load_json("eastmoney-price.json"), source_target(), RETRIEVED_AT
    )
    stooq = StooqPriceAdapter().parse_payload(
        (FIXTURE_DIRECTORY / "stooq-price.csv").read_text(encoding="utf-8"),
        source_target(),
        RETRIEVED_AT,
    )

    assert [row.source_id for row in eastmoney.rows] == ["eastmoney_index_history"] * 2
    assert [row.source_id for row in stooq.rows] == ["stooq_index_history"] * 2
    assert eastmoney.rows[0].value != stooq.rows[0].value


def test_adapters_report_empty_malformed_stale_and_duplicate_payloads() -> None:
    from market_evidence.sources.base import SourcePayloadError
    from market_evidence.sources.csindex import CsindexValuationAdapter

    adapter = CsindexValuationAdapter()
    empty = adapter.parse_payload(load_json("empty.json"), source_target(), RETRIEVED_AT)
    assert empty.status == "empty"
    assert empty.rows == ()

    stale = adapter.parse_payload(
        load_json("stale-valuation.json"),
        source_target(),
        RETRIEVED_AT,
        expected_latest_date=date(2026, 7, 15),
        max_age_days=3,
    )
    assert stale.status == "stale"

    with pytest.raises(SourcePayloadError, match="malformed"):
        adapter.parse_payload(load_json("malformed.json"), source_target(), RETRIEVED_AT)
    with pytest.raises(SourcePayloadError, match="duplicate"):
        adapter.parse_payload(load_json("duplicate-valuation.json"), source_target(), RETRIEVED_AT)
