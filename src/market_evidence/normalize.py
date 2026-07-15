"""Deterministic normalization for public index observations."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


NULL_MARKERS = {"", "-", "--", "null", "none", "n/a", "nan"}
INDEX_CODE_PATTERN = re.compile(r"^[A-Z0-9._-]{2,40}$")


class NormalizationError(ValueError):
    """Raised when source data cannot be normalized without guessing or clipping."""


def normalize_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise NormalizationError(f"invalid date: {value!r}")


def normalize_number(value: Any, *, percent: bool = False) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in NULL_MARKERS:
        return None
    if text.endswith("%"):
        text = text[:-1].strip()
    elif percent:
        text = text.strip()
    text = text.replace(",", "")
    try:
        number = Decimal(text)
    except InvalidOperation as error:
        raise NormalizationError(f"invalid numeric value: {value!r}") from error
    if not number.is_finite():
        raise NormalizationError(f"non-finite numeric value: {value!r}")
    return number


def normalize_metric_value(metric: str, value: Any) -> Decimal | None:
    number = normalize_number(value, percent=metric == "dividend_yield")
    if number is None:
        return None

    bounds = {
        "pe": (Decimal("0"), Decimal("1000"), False),
        "pb": (Decimal("0"), Decimal("100"), False),
        "dividend_yield": (Decimal("0"), Decimal("100"), True),
        "price": (Decimal("0"), Decimal("1000000000"), False),
    }
    if metric not in bounds:
        raise NormalizationError(f"unknown metric: {metric}")
    lower, upper, allow_lower = bounds[metric]
    lower_valid = number >= lower if allow_lower else number > lower
    if not lower_valid or number > upper:
        raise NormalizationError(f"impossible {metric} value: {value!r}")
    return number


def normalize_index_code(value: Any) -> str:
    code = str(value).strip().upper()
    if not INDEX_CODE_PATTERN.fullmatch(code):
        raise NormalizationError(f"invalid index identifier: {value!r}")
    return code


def normalize_currency(value: Any) -> str:
    aliases = {"RMB": "CNY", "CNY": "CNY", "HKD": "HKD"}
    currency = aliases.get(str(value).strip().upper())
    if not currency:
        raise NormalizationError(f"unsupported currency: {value!r}")
    return currency

