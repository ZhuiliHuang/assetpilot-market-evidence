"""Locked, public-only live source orchestration for scheduled evidence builds."""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable
from urllib.parse import urlencode

from market_evidence.http_client import BoundedHttpClient
from market_evidence.sources.base import SourceResult, SourceTarget
from market_evidence.sources.eastmoney import EastmoneyPriceAdapter
from market_evidence.sources.sina import SinaPriceAdapter
from market_evidence.sources.stooq import StooqPriceAdapter
from market_evidence.sources.tencent import TencentPriceAdapter


_EASTMONEY_HOST = "push2his.eastmoney.com"
_STOOQ_HOST = "stooq.com"
_SINA_HOST = "quotes.sina.cn"
_TENCENT_HOST = "web.ifzq.gtimg.cn"
_HK_EASTMONEY_SECURITY_IDS = {
    "HSI": "100.HSI",
    "HSTECH": "124.HSTECH",
    "HSHDYI": "124.HSHDYI",
}
_EASTMONEY_SECURITY_ID_OVERRIDES = {
    "932075": "2.932075",
}
_STOOQ_SYMBOLS = {
    "HSI": "^hsi",
}
_TENCENT_HK_SYMBOLS = {
    "HSI": "hkHSI",
    "HSTECH": "hkHSTECH",
}


def _eastmoney_security_id(target: SourceTarget) -> str:
    if target.proxy_code in _HK_EASTMONEY_SECURITY_IDS:
        return _HK_EASTMONEY_SECURITY_IDS[target.proxy_code]
    if target.proxy_code in _EASTMONEY_SECURITY_ID_OVERRIDES:
        return _EASTMONEY_SECURITY_ID_OVERRIDES[target.proxy_code]
    market = "0" if target.proxy_code.startswith("399") else "1"
    return f"{market}.{target.proxy_code}"


def eastmoney_price_url(target: SourceTarget, start_date: date, end_date: date) -> str:
    query = urlencode({
        "secid": _eastmoney_security_id(target),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53",
        "klt": "101",
        "fqt": "0",
        "beg": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
    })
    return f"https://{_EASTMONEY_HOST}/api/qt/stock/kline/get?{query}"


def stooq_price_url(target: SourceTarget, start_date: date, end_date: date) -> str:
    symbol = _STOOQ_SYMBOLS.get(target.proxy_code)
    if not symbol:
        raise ValueError("Stooq coverage is not approved for this locked direction")
    query = urlencode({
        "s": symbol,
        "d1": start_date.strftime("%Y%m%d"),
        "d2": end_date.strftime("%Y%m%d"),
        "i": "d",
    })
    return f"https://{_STOOQ_HOST}/q/d/l/?{query}"


def sina_price_url(target: SourceTarget, _start_date: date, _end_date: date) -> str:
    if not target.proxy_code.isdigit():
        raise ValueError("Sina coverage is not approved for this locked direction")
    market = "sz" if target.proxy_code.startswith("399") else "sh"
    symbol = f"{market}{target.proxy_code}"
    query = urlencode({
        "symbol": symbol,
        "scale": "240",
        "ma": "no",
        "datalen": "1500",
    })
    return f"https://{_SINA_HOST}/cn/api/jsonp_v2.php/var%20_assetpilot=/CN_MarketDataService.getKLineData?{query}"


def tencent_symbol(target: SourceTarget) -> str:
    if target.proxy_code in _TENCENT_HK_SYMBOLS:
        return _TENCENT_HK_SYMBOLS[target.proxy_code]
    if not target.proxy_code.isdigit():
        raise ValueError("Tencent coverage is not approved for this locked direction")
    if target.currency == "HKD":
        return f"hk{target.proxy_code}"
    market = "sz" if target.proxy_code.startswith("399") else "sh"
    return f"{market}{target.proxy_code}"


def tencent_price_url(target: SourceTarget, start_date: date, end_date: date) -> str:
    param = ",".join((
        tencent_symbol(target),
        "day",
        start_date.isoformat(),
        end_date.isoformat(),
        "640",
        "qfq",
    ))
    return f"https://{_TENCENT_HOST}/appstock/app/fqkline/get?{urlencode({'param': param})}"


def _failed_result(source_id: str, now: datetime, error: Exception) -> SourceResult:
    return SourceResult(
        source_id=source_id,
        retrieved_at=now,
        as_of_trade_date=None,
        license_mode="publish_derived_only",
        status="failed",
        rows=(),
        errors=(f"{type(error).__name__}: {str(error)[:160]}",),
    )


def fetch_live_source_results(
    direction: dict,
    start_date: date,
    end_date: date,
    now: datetime,
    *,
    client_factory: Callable[[], BoundedHttpClient] | None = None,
) -> list[SourceResult]:
    """Fetch only the locked direction code; never accepts portfolio context."""
    target = SourceTarget(
        direction_id=direction["id"],
        proxy_code=direction["primary_proxy_code"],
        currency=direction["currency"],
    )
    client = (client_factory or (lambda: BoundedHttpClient(
        allowed_hosts={_EASTMONEY_HOST, _SINA_HOST, _STOOQ_HOST, _TENCENT_HOST},
        timeout_seconds=15,
        max_attempts=2,
        max_response_bytes=5_000_000,
        retry_delay_seconds=12,
    )))()
    results: list[SourceResult] = []

    tencent = TencentPriceAdapter(
        client=client,
        url_builder=tencent_price_url,
        symbol_builder=tencent_symbol,
    )
    try:
        results.append(tencent.fetch(target, start_date, end_date))
    except Exception as error:
        results.append(_failed_result(tencent.source_id, now, error))

    if not any(result.status == "success" and result.rows for result in results):
        eastmoney = EastmoneyPriceAdapter(client=client, url_builder=eastmoney_price_url)
        try:
            results.append(eastmoney.fetch(target, start_date, end_date))
        except Exception as error:
            results.append(_failed_result(eastmoney.source_id, now, error))

    if target.proxy_code.isdigit() and target.currency == "CNY":
        sina = SinaPriceAdapter(client=client, url_builder=sina_price_url)
        try:
            results.append(sina.fetch(target, start_date, end_date))
        except Exception as error:
            results.append(_failed_result(sina.source_id, now, error))

    if target.proxy_code in _STOOQ_SYMBOLS:
        stooq = StooqPriceAdapter(client=client, url_builder=stooq_price_url)
        try:
            results.append(stooq.fetch(target, start_date, end_date))
        except Exception as error:
            results.append(_failed_result(stooq.source_id, now, error))

    return results
