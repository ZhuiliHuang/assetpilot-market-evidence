"""Adapter for Stooq-style public CSV index history."""

from __future__ import annotations

import csv
import io
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


class StooqPriceAdapter(SourceAdapter):
    source_id = "stooq_index_history"

    def __init__(
        self,
        client: BoundedHttpClient | None = None,
        url_builder: Callable[[SourceTarget, date, date], str] | None = None,
    ) -> None:
        self.client = client
        self.url_builder = url_builder

    def fetch(self, target: SourceTarget, start_date: date, end_date: date) -> SourceResult:
        if not self.client or not self.url_builder:
            raise RuntimeError("live Stooq fetch requires an audited client and URL builder")
        payload = self.client.get_bytes(
            self.url_builder(target, start_date, end_date), accept="text/csv"
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
        reader = csv.DictReader(io.StringIO(payload))
        if not reader.fieldnames or not {"Date", "Close"}.issubset(reader.fieldnames):
            raise SourcePayloadError("malformed Stooq CSV payload")

        rows: list[Observation] = []
        for raw_row in reader:
            try:
                trade_date = normalize_date(raw_row["Date"])
                value = normalize_metric_value("price", raw_row["Close"])
            except (KeyError, NormalizationError) as error:
                raise SourcePayloadError(f"malformed Stooq CSV row: {error}") from error
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
