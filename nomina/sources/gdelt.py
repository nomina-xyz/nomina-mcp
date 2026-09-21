"""GDELT DOC 2.0 article search (open for commercial use with citation).

GDELT asks for at most one request every five seconds per client, so requests are serialised
with a spacing lock and results cached for ten minutes. Headlines are best-effort: callers
report a failure in `partial_errors` rather than failing the whole tool.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from nomina.sources.common import Fetcher, MarketDataError

API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
CITATION = "The GDELT Project (https://www.gdeltproject.org/)"
_SPACING_SECONDS = 5.2


class Gdelt:
    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def headlines(
        self, query: str, limit: int, *, timespan: str = "14d"
    ) -> list[dict[str, str | None]]:
        params = {
            "query": f"{query} sourcelang:english",
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(max(1, min(limit * 3, 75))),
            "timespan": timespan,
            "sort": "DateDesc",
        }
        async with self._lock:
            wait = self._last_request + _SPACING_SECONDS - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                payload = await self.fetcher.request(
                    "GET",
                    API_URL,
                    params=params,
                    subject="GDELT article search",
                    ttl=600,
                    timeout=8.0,
                )
            finally:
                self._last_request = time.monotonic()
        if not isinstance(payload, dict):
            raise MarketDataError("GDELT article search returned an unexpected payload.")
        articles = payload.get("articles")
        if not isinstance(articles, list):
            return []
        seen: set[str] = set()
        results: list[dict[str, str | None]] = []
        for item in articles:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            title = (item.get("title") or "").strip()
            if not isinstance(url, str) or not url.startswith("https://") or not title:
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "title": title,
                    "publisher": item.get("domain"),
                    "url": url,
                    "published_at": _parse_seendate(item.get("seendate")),
                }
            )
            if len(results) == limit:
                break
        return results

    @staticmethod
    def source(query: str) -> dict[str, Any]:
        return {
            "name": "GDELT article search",
            "url": f"{API_URL}?query={query}&mode=ArtList&format=json",
            "citation": CITATION,
        }


def _parse_seendate(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return (
            datetime.strptime(value, "%Y%m%dT%H%M%SZ")
            .replace(tzinfo=UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except ValueError:
        return None
