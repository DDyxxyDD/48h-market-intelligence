"""Common network and date helpers for public collectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import time
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.models import Article

USER_AGENT = "48h-market-intelligence/2.0 (+local research tool; public feeds only)"


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse common RSS/RFC-822 and ISO-8601 timestamps as UTC."""
    if not value:
        return None
    value = value.strip()
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


TRANSIENT_HTTP_CODES = {429, 500, 502, 503, 504}


def fetch_with_attempts(url: str, timeout: float = 12, retries: int = 1,
                        backoff: float = 0.4, sleep=time.sleep) -> tuple[bytes, int]:
    """Fetch bytes and report attempts, retrying only transient failures/timeouts."""
    last_error: Exception | None = None
    attempts = 0
    for attempt in range(retries + 1):
        attempts += 1
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/json, text/html, text/xml;q=0.9, */*;q=0.5"})
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured public URLs
                return response.read(5_000_000), attempts
        except Exception as exc:  # endpoint isolation is intentional
            last_error = exc
            transient = not isinstance(exc, HTTPError) or exc.code in TRANSIENT_HTTP_CODES
            if attempt < retries and transient:
                sleep(backoff * (2 ** attempt))
                continue
            break
    assert last_error is not None
    setattr(last_error, "attempts", attempts)
    raise last_error


def fetch_bytes(url: str, timeout: float = 12, retries: int = 1) -> bytes:
    """Fetch a public endpoint with a bounded timeout and modest retry."""
    return fetch_with_attempts(url, timeout, retries)[0]


@dataclass
class CollectionResult:
    """Articles and endpoint-level status from one collector."""

    articles: list[Article] = field(default_factory=list)
    statuses: list[dict[str, Any]] = field(default_factory=list)
