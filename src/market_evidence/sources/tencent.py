"""Adapter for Tencent's public daily K-line payloads."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from market_evidence.http_client import BoundedHttpClient
from market_evidence.normalize import NormalizationError, normalize_date, normalize_metric_value
from market_evidence.sources.base import (
    Observation,
    SourceAdapter,
    SourcePayloadError,
    SourceResult,
    SourceTarget,
    build_result,
)


class TencentPriceAdapter(SourceAdapter):
    source_id = "tencent_index_history"
    _WINDOW_DAYS = 600

    def __init__(
        self,
        client: BoundedHttpClient | None = None,
        url_builder: Callable[[SourceTarget, date, date], str] | None = None,
        symbol_builder: Callable[[SourceTarget], str] | None = None,
        *,
        page_delay_seconds: float = 0.15,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.url_builder = url_builder
        self.symbol_builder = symbol_builder
        self.page_delay_seconds = page_delay_seconds
        self.sleeper = sleeper

    def fetch(self, target: SourceTarget, start_date: date, end_date: date) -> SourceResult:
        if not self.client or not self.url_builder or not self.symbol_builder:
            raise RuntimeError("live Tencent fetch requires audited client and symbol builders")

        retrieved_at = datetime.now(timezone.utc)
        expected_symbol = self.symbol_builder(target)
        rows_by_key: dict[tuple[date, str], Observation] = {}
        window_start = start_date
        while window_start <= end_date:
            window_end = min(window_start + timedelta(days=self._WINDOW_DAYS), end_date)
            payload = self.client.get_json(self.url_builder(target, window_start, window_end))
            page = self.parse_payload(
                payload,
                target,
                retrieved_at,
                expected_symbol=expected_symbol,
            )
            for row in page.rows:
                rows_by_key[(row.trade_date, row.metric)] = row
            window_start = window_end + timedelta(days=1)
            if window_start <= end_date and self.page_delay_seconds:
                self.sleeper(self.page_delay_seconds)

        return build_result(
            source_id=self.source_id,
            target=target,
            retrieved_at=retrieved_at,
            rows=list(rows_by_key.values()),
            expected_latest_date=end_date,
            max_age_days=3,
        )

    def parse_payload(
        self,
        payload: Any,
        target: SourceTarget,
        retrieved_at: datetime,
        *,
        expected_symbol: str,
        expected_latest_date: date | None = None,
        max_age_days: int = 3,
    ) -> SourceResult:
        if not isinstance(payload, dict) or payload.get("code") != 0:
            raise SourcePayloadError("malformed Tencent payload")
        data = payload.get("data")
        if not isinstance(data, dict) or expected_symbol not in data:
            raise SourcePayloadError("Tencent payload changed the locked symbol")
        node = data[expected_symbol]
        if not isinstance(node, dict):
            raise SourcePayloadError("malformed Tencent symbol payload")
        klines = node.get("qfqday") or node.get("day")
        if klines is None:
            return build_result(
                source_id=self.source_id,
                target=target,
                retrieved_at=retrieved_at,
                rows=[],
            )
        if not isinstance(klines, list):
            raise SourcePayloadError("malformed Tencent K-line payload")

        rows: list[Observation] = []
        for kline in klines:
            if not isinstance(kline, list) or len(kline) < 3:
                raise SourcePayloadError("malformed Tencent K-line row")
            try:
                trade_date = normalize_date(kline[0])
                value = normalize_metric_value("price", kline[2])
            except NormalizationError as error:
                raise SourcePayloadError(f"malformed Tencent K-line row: {error}") from error
            if value is not None:
                rows.append(Observation(
                    source_id=self.source_id,
                    direction_id=target.direction_id,
                    proxy_code=target.proxy_code,
                    trade_date=trade_date,
                    metric="price",
                    value=value,
                    currency=target.currency,
                ))

        return build_result(
            source_id=self.source_id,
            target=target,
            retrieved_at=retrieved_at,
            rows=rows,
            expected_latest_date=expected_latest_date,
            max_age_days=max_age_days,
        )
