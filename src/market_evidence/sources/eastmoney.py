"""Adapter for Eastmoney-style public index K-line payloads."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable

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


class EastmoneyPriceAdapter(SourceAdapter):
    source_id = "eastmoney_index_history"

    def __init__(
        self,
        client: BoundedHttpClient | None = None,
        url_builder: Callable[[SourceTarget, date, date], str] | None = None,
    ) -> None:
        self.client = client
        self.url_builder = url_builder

    def fetch(self, target: SourceTarget, start_date: date, end_date: date) -> SourceResult:
        if not self.client or not self.url_builder:
            raise RuntimeError("live Eastmoney fetch requires an audited client and URL builder")
        payload = self.client.get_json(self.url_builder(target, start_date, end_date))
        return self.parse_payload(
            payload,
            target,
            datetime.now(timezone.utc),
            expected_latest_date=end_date,
        )

    def parse_payload(
        self,
        payload: Any,
        target: SourceTarget,
        retrieved_at: datetime,
        *,
        expected_latest_date: date | None = None,
        max_age_days: int = 3,
    ) -> SourceResult:
        if not isinstance(payload, dict):
            raise SourcePayloadError("malformed Eastmoney payload")
        data = payload.get("data")
        if data is None:
            return build_result(
                source_id=self.source_id,
                target=target,
                retrieved_at=retrieved_at,
                rows=[],
            )
        if not isinstance(data, dict) or not isinstance(data.get("klines"), list):
            raise SourcePayloadError("malformed Eastmoney K-line payload")

        rows: list[Observation] = []
        for kline in data["klines"]:
            fields = str(kline).split(",")
            if len(fields) < 3:
                raise SourcePayloadError("malformed Eastmoney K-line row")
            try:
                trade_date = normalize_date(fields[0])
                value = normalize_metric_value("price", fields[2])
            except NormalizationError as error:
                raise SourcePayloadError(f"malformed Eastmoney K-line row: {error}") from error
            if value is not None:
                rows.append(
                    Observation(
                        source_id=self.source_id,
                        direction_id=target.direction_id,
                        proxy_code=target.proxy_code,
                        trade_date=trade_date,
                        metric="price",
                        value=value,
                        currency=target.currency,
                    )
                )

        return build_result(
            source_id=self.source_id,
            target=target,
            retrieved_at=retrieved_at,
            rows=rows,
            expected_latest_date=expected_latest_date,
            max_age_days=max_age_days,
        )

