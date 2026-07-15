from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest


def test_normalize_dates_numbers_and_nulls() -> None:
    from market_evidence.normalize import normalize_date, normalize_number

    assert normalize_date("2026-07-15") == date(2026, 7, 15)
    assert normalize_date("20260715") == date(2026, 7, 15)
    assert normalize_number("1,234.50") == Decimal("1234.50")
    assert normalize_number("4.25%", percent=True) == Decimal("4.25")
    assert normalize_number("--") is None


def test_impossible_market_values_are_rejected_not_clipped() -> None:
    from market_evidence.normalize import NormalizationError, normalize_metric_value

    assert normalize_metric_value("pe", "18.2") == Decimal("18.2")
    assert normalize_metric_value("pb", "3.1") == Decimal("3.1")
    assert normalize_metric_value("dividend_yield", "4.5%") == Decimal("4.5")

    with pytest.raises(NormalizationError, match="pe"):
        normalize_metric_value("pe", "-2")
    with pytest.raises(NormalizationError, match="pb"):
        normalize_metric_value("pb", "101")
    with pytest.raises(NormalizationError, match="price"):
        normalize_metric_value("price", "0")


def test_identifiers_and_currencies_use_locked_forms() -> None:
    from market_evidence.normalize import NormalizationError, normalize_currency, normalize_index_code

    assert normalize_index_code(" 000300 ") == "000300"
    assert normalize_index_code("hstech") == "HSTECH"
    assert normalize_currency("rmb") == "CNY"
    assert normalize_currency("HKD") == "HKD"

    with pytest.raises(NormalizationError, match="currency"):
        normalize_currency("USD")

