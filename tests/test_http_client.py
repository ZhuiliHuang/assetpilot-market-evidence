from __future__ import annotations

import json
from urllib.error import URLError

import pytest


class FakeResponse:
    def __init__(self, body: bytes, final_url: str) -> None:
        self.body = body
        self.final_url = final_url
        self.offset = 0

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.body) - self.offset
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk

    def geturl(self) -> str:
        return self.final_url


def test_http_client_sends_only_public_headers_and_parses_json() -> None:
    from market_evidence.http_client import BoundedHttpClient

    calls: list[tuple[object, float]] = []

    def opener(request: object, timeout: float) -> FakeResponse:
        calls.append((request, timeout))
        return FakeResponse(json.dumps({"ok": True}).encode(), "https://data.example.com/value")

    client = BoundedHttpClient(
        allowed_hosts={"data.example.com"},
        timeout_seconds=5,
        max_attempts=2,
        max_response_bytes=1024,
        opener=opener,
    )

    assert client.get_json("https://data.example.com/value") == {"ok": True}
    request, timeout = calls[0]
    headers = {key.lower(): value for key, value in request.header_items()}
    assert timeout == 5
    assert "user-agent" in headers
    assert "authorization" not in headers
    assert "cookie" not in headers


def test_http_client_passes_timeout_as_timeout_not_as_request_body() -> None:
    from market_evidence.http_client import BoundedHttpClient

    observed: list[float] = []

    def keyword_only_opener(_request: object, *, timeout: float) -> FakeResponse:
        observed.append(timeout)
        return FakeResponse(b"{}", "https://data.example.com/value")

    client = BoundedHttpClient(
        allowed_hosts={"data.example.com"},
        timeout_seconds=7,
        opener=keyword_only_opener,
    )

    assert client.get_json("https://data.example.com/value") == {}
    assert observed == [7]


def test_http_client_rejects_insecure_urls_and_unapproved_redirects() -> None:
    from market_evidence.http_client import HttpSafetyError, BoundedHttpClient

    client = BoundedHttpClient(
        allowed_hosts={"data.example.com"},
        opener=lambda _request, timeout: FakeResponse(b"{}", "https://evil.example.net/value"),
    )

    with pytest.raises(HttpSafetyError, match="HTTPS"):
        client.get_json("http://data.example.com/value")
    with pytest.raises(HttpSafetyError, match="approved"):
        client.get_json("https://data.example.com/value")


def test_http_client_bounds_retries_and_response_size() -> None:
    from market_evidence.http_client import HttpFetchError, HttpSafetyError, BoundedHttpClient

    attempts = 0

    def failing_opener(_request: object, timeout: float) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        raise URLError("temporary")

    retry_client = BoundedHttpClient(
        allowed_hosts={"data.example.com"},
        max_attempts=2,
        opener=failing_opener,
    )
    with pytest.raises(HttpFetchError, match="after 2 attempts"):
        retry_client.get_json("https://data.example.com/value")
    assert attempts == 2

    size_client = BoundedHttpClient(
        allowed_hosts={"data.example.com"},
        max_response_bytes=4,
        opener=lambda _request, timeout: FakeResponse(b"12345", "https://data.example.com/value"),
    )
    with pytest.raises(HttpSafetyError, match="size"):
        size_client.get_json("https://data.example.com/value")


def test_http_client_waits_between_failed_attempts_without_exposing_request_data() -> None:
    from market_evidence.http_client import BoundedHttpClient

    attempts = 0
    waits: list[float] = []

    def flaky_opener(_request: object, timeout: float) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise URLError("temporary")
        return FakeResponse(b"{}", "https://data.example.com/value")

    client = BoundedHttpClient(
        allowed_hosts={"data.example.com"},
        max_attempts=2,
        retry_delay_seconds=12,
        sleeper=waits.append,
        opener=flaky_opener,
    )

    assert client.get_json("https://data.example.com/value") == {}
    assert waits == [12]
