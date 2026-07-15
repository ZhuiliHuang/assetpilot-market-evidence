"""Small, bounded HTTP client for public market endpoints."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


DEFAULT_USER_AGENT = "AssetPilotMarketEvidence/0.1 (+public-derived-data; no-auth)"


class HttpSafetyError(ValueError):
    """Raised when an HTTP request violates a fixed public-source boundary."""


class HttpFetchError(RuntimeError):
    """Raised when a bounded public fetch cannot be completed."""


class BoundedHttpClient:
    def __init__(
        self,
        *,
        allowed_hosts: set[str],
        timeout_seconds: float = 15,
        max_attempts: int = 2,
        max_response_bytes: int = 5_000_000,
        user_agent: str = DEFAULT_USER_AGENT,
        opener: Callable[[Request, float], Any] = urlopen,
    ) -> None:
        if not allowed_hosts:
            raise HttpSafetyError("at least one approved host is required")
        if not 1 <= max_attempts <= 3:
            raise HttpSafetyError("max_attempts must be between one and three")
        if not 0 < timeout_seconds <= 30:
            raise HttpSafetyError("timeout must be positive and at most thirty seconds")
        if not 1 <= max_response_bytes <= 10_000_000:
            raise HttpSafetyError("response size bound is invalid")

        self.allowed_hosts = {host.lower() for host in allowed_hosts}
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.max_response_bytes = max_response_bytes
        self.user_agent = user_agent
        self.opener = opener

    def _validate_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme != "https":
            raise HttpSafetyError("public market requests must use HTTPS")
        if parsed.username or parsed.password:
            raise HttpSafetyError("credentials are forbidden in public market URLs")
        if (parsed.hostname or "").lower() not in self.allowed_hosts:
            raise HttpSafetyError("request host is not approved")

    def get_bytes(self, url: str, *, accept: str = "application/json") -> bytes:
        self._validate_url(url)
        request = Request(
            url,
            headers={
                "Accept": accept,
                "User-Agent": self.user_agent,
            },
            method="GET",
        )

        last_error: Exception | None = None
        for _attempt in range(1, self.max_attempts + 1):
            try:
                with self.opener(request, self.timeout_seconds) as response:
                    final_url = response.geturl()
                    self._validate_url(final_url)
                    body = response.read(self.max_response_bytes + 1)
                    if len(body) > self.max_response_bytes:
                        raise HttpSafetyError("response size exceeds the configured bound")
                    return body
            except HttpSafetyError:
                raise
            except (TimeoutError, URLError, OSError) as error:
                last_error = error

        detail = str(last_error)[:200] if last_error else "unknown error"
        raise HttpFetchError(f"public fetch failed after {self.max_attempts} attempts: {detail}")

    def get_json(self, url: str) -> Any:
        try:
            return json.loads(self.get_bytes(url).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise HttpFetchError(f"public endpoint returned malformed JSON: {error}") from error

