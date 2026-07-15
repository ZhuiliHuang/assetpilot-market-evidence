"""Adapter for public CSI-style valuation history payloads."""

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


class CsindexValuationAdapter(SourceAdapter):
    source_id = "akshare_csindex_valuation"

    def __init__(
        self,
        client: BoundedHttpClient | None = None,
        url_builder: Callable[[SourceTarget, date, date], str] | None = None,
    ) -> None:
        self.client = client
        self.url_builder = url_builder

    def fetch(self, target: SourceTarget, start_date: date, end_date: date) -> SourceResult:
        if not self.client or not self.url_builder:
            raise RuntimeError("live CSI fetch requires an audited client and URL builder")
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
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise SourcePayloadError("malformed CSI valuation payload")

        rows: list[Observation] = []
        for raw_row in payload["data"]:
            if not isinstance(raw_row, dict) or "date" not in raw_row:
                raise SourcePayloadError("malformed CSI valuation row")
            try:
                trade_date = normalize_date(raw_row["date"])
                for metric in ("pe", "pb", "dividend_yield"):
                    value = normalize_metric_value(metric, raw_row.get(metric))
                    if value is not None:
                        rows.append(
                            Observation(
                                source_id=self.source_id,
                                direction_id=target.direction_id,
                                proxy_code=target.proxy_code,
                                trade_date=trade_date,
                                metric=metric,
                                value=value,
                                currency=target.currency,
                            )
                        )
            except NormalizationError as error:
                raise SourcePayloadError(f"malformed CSI valuation row: {error}") from error

        return build_result(
            source_id=self.source_id,
            target=target,
            retrieved_at=retrieved_at,
            rows=rows,
            expected_latest_date=expected_latest_date,
            max_age_days=max_age_days,
        )

