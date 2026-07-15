"""Adapter for Sina public index K-line JSONP payloads."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Callable

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


class SinaPriceAdapter(SourceAdapter):
    source_id = "sina_index_history"

    def __init__(
        self,
        client: BoundedHttpClient | None = None,
        url_builder: Callable[[SourceTarget, date, date], str] | None = None,
    ) -> None:
        self.client = client
        self.url_builder = url_builder

    def fetch(self, target: SourceTarget, start_date: date, end_date: date) -> SourceResult:
        if not self.client or not self.url_builder:
            raise RuntimeError("live Sina fetch requires an audited client and URL builder")
        payload = self.client.get_bytes(
            self.url_builder(target, start_date, end_date),
            accept="text/javascript",
        ).decode("utf-8")
        return self.parse_payload(
            payload,
            target,
            datetime.now(timezone.utc),
            expected_latest_date=end_date,
        )

    def parse_payload(
        self,
        payload: str,
        target: SourceTarget,
        retrieved_at: datetime,
        *,
        expected_latest_date: date | None = None,
        max_age_days: int = 3,
    ) -> SourceResult:
        start = payload.find("([")
        end = payload.rfind("]);")
        if start < 0 or end < start:
            raise SourcePayloadError("malformed Sina JSONP payload")
        try:
            raw_rows = json.loads(payload[start + 1 : end + 1])
        except json.JSONDecodeError as error:
            raise SourcePayloadError("malformed Sina JSONP payload") from error
        if not isinstance(raw_rows, list):
            raise SourcePayloadError("malformed Sina K-line rows")

        rows: list[Observation] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict) or "day" not in raw_row or "close" not in raw_row:
                raise SourcePayloadError("malformed Sina K-line row")
            try:
                trade_date = normalize_date(raw_row["day"])
                value = normalize_metric_value("price", raw_row["close"])
            except NormalizationError as error:
                raise SourcePayloadError(f"malformed Sina K-line row: {error}") from error
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
