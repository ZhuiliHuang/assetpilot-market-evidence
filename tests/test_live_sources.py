from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlsplit


def test_eastmoney_url_contains_only_locked_public_index_parameters() -> None:
    from market_evidence.live_sources import eastmoney_price_url, sina_price_url, tencent_price_url
    from market_evidence.sources.base import SourceTarget

    url = eastmoney_price_url(
        SourceTarget("gem", "399006", "CNY"),
        date(2016, 7, 15),
        date(2026, 7, 15),
    )
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.hostname == "push2his.eastmoney.com"
    assert query["secid"] == ["0.399006"]
    assert query["beg"] == ["20160715"]
    assert query["end"] == ["20260715"]
    assert set(query) == {"secid", "fields1", "fields2", "klt", "fqt", "beg", "end"}
    assert all(private not in url.lower() for private in ("portfolio", "account", "holding", "cost", "quantity", "token", "key"))

    sina = urlsplit(sina_price_url(SourceTarget("hs300", "000300", "CNY"), date(2016, 7, 15), date(2026, 7, 15)))
    sina_query = parse_qs(sina.query)
    assert sina.scheme == "https"
    assert sina.hostname == "quotes.sina.cn"
    assert sina_query == {"symbol": ["sh000300"], "scale": ["240"], "ma": ["no"], "datalen": ["1500"]}

    tencent = urlsplit(tencent_price_url(
        SourceTarget("hs300", "000300", "CNY"),
        date(2016, 7, 15),
        date(2018, 7, 15),
    ))
    tencent_query = parse_qs(tencent.query)
    assert tencent.scheme == "https"
    assert tencent.hostname == "web.ifzq.gtimg.cn"
    assert tencent_query == {"param": ["sh000300,day,2016-07-15,2018-07-15,640,qfq"]}


def test_hong_kong_targets_use_explicit_public_symbol_mapping() -> None:
    from market_evidence.live_sources import eastmoney_price_url, stooq_price_url, tencent_price_url
    from market_evidence.sources.base import SourceTarget

    start = date(2016, 7, 15)
    end = date(2026, 7, 15)
    hsi = SourceTarget("hsi", "HSI", "HKD")
    hstech = SourceTarget("hstech", "HSTECH", "HKD")
    hk_dividend = SourceTarget("hk_dividend", "HSHDYI", "HKD")
    finance = SourceTarget("finance", "932075", "CNY")

    assert "secid=100.HSI" in eastmoney_price_url(hsi, start, end)
    assert "secid=124.HSTECH" in eastmoney_price_url(hstech, start, end)
    assert "secid=124.HSHDYI" in eastmoney_price_url(hk_dividend, start, end)
    assert "secid=2.932075" in eastmoney_price_url(finance, start, end)
    assert "s=%5Ehsi" in stooq_price_url(hsi, start, end)
    assert "hkHSI%2Cday" in tencent_price_url(hsi, start, end)
    assert "hkHSTECH%2Cday" in tencent_price_url(hstech, start, end)


def test_cloud_safe_proxy_codes_have_exact_tencent_symbols() -> None:
    from market_evidence.live_sources import tencent_price_url
    from market_evidence.sources.base import SourceTarget

    start = date(2016, 7, 15)
    end = date(2026, 7, 15)
    finance = tencent_price_url(SourceTarget("finance", "000992", "CNY"), start, end)
    hk_dividend = tencent_price_url(SourceTarget("hk_dividend", "03110", "HKD"), start, end)

    assert "sh000992%2Cday" in finance
    assert "hk03110%2Cday" in hk_dividend
    assert all(private not in (finance + hk_dividend).lower() for private in (
        "portfolio", "account", "holding", "cost", "quantity", "token", "key"
    ))


def test_successful_tencent_fetch_does_not_probe_blocked_eastmoney_fallback() -> None:
    from datetime import datetime, timezone

    from market_evidence.live_sources import fetch_live_source_results

    requested_hosts: list[str] = []

    class FakeClient:
        def get_json(self, url: str) -> dict:
            parsed = urlsplit(url)
            requested_hosts.append(parsed.hostname or "")
            assert parsed.hostname != "push2his.eastmoney.com"
            param = parse_qs(parsed.query)["param"][0].split(",")
            symbol, end_date = param[0], param[3]
            return {
                "code": 0,
                "data": {symbol: {"day": [[end_date, "1", "2", "3", "1", "10"]]}},
            }

    results = fetch_live_source_results(
        {
            "id": "hstech",
            "primary_proxy_code": "HSTECH",
            "currency": "HKD",
        },
        date(2026, 7, 14),
        date(2026, 7, 15),
        datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
        client_factory=FakeClient,
    )

    assert [result.source_id for result in results] == ["tencent_index_history"]
    assert requested_hosts == ["web.ifzq.gtimg.cn"]
