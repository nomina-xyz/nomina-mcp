"""Shared types and a cached JSON/text fetcher for the data sources."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Literal

import httpx

Measure = Literal["percent", "points"]
Kind = Literal["crypto", "fx", "commodity", "equity", "yield", "macro"]

_CACHE_MAX_ENTRIES = 512


class MarketDataError(Exception):
    """An actionable problem retrieving or interpreting source data."""


@dataclass(frozen=True)
class Point:
    date: str  # ISO date of the observation
    observed_at: str  # ISO timestamp of the underlying observation
    value: float


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    kind: Kind
    unit: str  # "USD", "percent", "index", "thousands"
    measure: Measure  # how period change is expressed
    source: str  # human source name
    url: str  # public page describing the instrument
    frequency: Literal["daily", "monthly"] = "daily"


@dataclass(frozen=True)
class Series:
    instrument: Instrument
    period: str
    interval: str
    points: list[Point]
    source_url: str
    latest_value: float | None
    latest_at: str | None
    notes: list[str] = field(default_factory=list)


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def iso_from_unix(value: float) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")


def day_start(value: date) -> int:
    return int(datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp())


class Fetcher:
    """HTTP access with a per-URL TTL cache. Errors are never cached."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client
        self._cache: dict[str, tuple[float, Any]] = {}
        self._inflight: dict[str, asyncio.Future[Any]] = {}

    def _get_cached(self, key: str) -> Any | None:
        cached = self._cache.get(key)
        if cached is not None and time.monotonic() < cached[0]:
            return cached[1]
        return None

    def _store(self, key: str, payload: Any, ttl: float) -> None:
        if key not in self._cache and len(self._cache) >= _CACHE_MAX_ENTRIES:
            del self._cache[min(self._cache, key=lambda entry: self._cache[entry][0])]
        self._cache[key] = (time.monotonic() + ttl, payload)

    async def request(
        self,
        method: str,
        url: str,
        *,
        subject: str,
        ttl: float,
        params: dict[str, str] | None = None,
        json_body: Any | None = None,
        headers: dict[str, str] | None = None,
        as_text: bool = False,
        timeout: float | None = None,
        before_send: Callable[[], None] | None = None,
    ) -> Any:
        """Fetch with caching and coalescing; `before_send` runs once per real network request."""
        key = f"{method} {httpx.URL(url, params=params)} {json_body!r}"
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        pending = self._inflight.get(key)
        if pending is not None:
            return await asyncio.shield(pending)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._inflight[key] = future
        try:
            if before_send is not None:
                before_send()
            payload = await self._fetch(
                method,
                url,
                subject=subject,
                params=params,
                json_body=json_body,
                headers=headers,
                as_text=as_text,
                timeout=timeout,
            )
        except BaseException as exc:
            future.set_exception(exc)
            future.exception()  # mark retrieved; waiters re-raise from the shielded future
            raise
        else:
            self._store(key, payload, ttl)
            future.set_result(payload)
            return payload
        finally:
            self._inflight.pop(key, None)

    async def _fetch(
        self,
        method: str,
        url: str,
        *,
        subject: str,
        params: dict[str, str] | None,
        json_body: Any | None,
        headers: dict[str, str] | None,
        as_text: bool,
        timeout: float | None,
    ) -> Any:
        try:
            response = await self.client.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=timeout if timeout is not None else httpx.USE_CLIENT_DEFAULT,
            )
        except httpx.TimeoutException as exc:
            raise MarketDataError(f"{subject} timed out. Try again later.") from exc
        except httpx.RequestError as exc:
            raise MarketDataError(f"{subject} request failed: {exc.__class__.__name__}.") from exc
        if response.status_code == 429:
            raise MarketDataError(
                f"{subject} rate-limited this request (HTTP 429). Try again later."
            )
        if not response.is_success:
            raise MarketDataError(
                f"{subject} returned HTTP {response.status_code}. Try again later."
            )
        if as_text:
            return response.text
        try:
            return response.json()
        except ValueError as exc:
            raise MarketDataError(f"{subject} returned invalid JSON.") from exc
