from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlsplit


def test_eastmoney_url_contains_only_locked_public_index_parameters() -> None:
    from market_evidence.live_sources import eastmoney_price_url, sina_price_url
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


def test_hong_kong_targets_use_explicit_public_symbol_mapping() -> None:
    from market_evidence.live_sources import eastmoney_price_url, stooq_price_url
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
