"""Chainlink Data Feeds on Ethereum mainnet, read from public JSON-RPC gateways.

Every feed round is stored on-chain, so a daily (or weekly) close series is reconstructed by
binary-searching round timestamps; all target dates are searched in parallel, one batched
`eth_call` request per step. Rounds are immutable, so resolved rounds are cached for the
process lifetime.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import httpx

from nomina.sources.common import (
    Fetcher,
    Instrument,
    Kind,
    MarketDataError,
    Point,
    day_start,
    iso_from_unix,
)

FEED_DIRECTORY_URL = "https://reference-data-directory.vercel.app/feeds-mainnet.json"
FEED_PAGE = "https://data.chain.link/feeds/ethereum/mainnet/{path}"
RPC_URLS = (
    "https://ethereum.publicnode.com",
    "https://rpc.mevblocker.io",
)
_SELECTOR = {
    "latestRoundData": "0xfeaf968c",
    "getRoundData": "0x9a6fc8f5",
    "decimals": "0x313ce567",
    "phaseAggregators": "0xc1597304",
    "latestRound": "0x668a0f02",
}
_BATCH = 100
_CATEGORIES = ("low", "medium", "high", "new")
_MAX_CONCURRENT_BATCHES = 4
_MIN_INTERVAL_SECONDS = 0.08  # global spacing between batch requests (about 12 per second)
_ATTEMPTS = 4
_BACKOFF_SECONDS = 0.75
_THROTTLE_MARKERS = ("rate", "limit", "too many", "capacity", "quota", "throttl")
_BATCH_TIMEOUT_SECONDS = 6.0
_COOLDOWN_SECONDS = 4.0
_ANCHORS = 200
_KINDS: dict[str, Kind] = {
    "Crypto": "crypto",
    "Forex": "fx",
    "Fiat": "fx",
    "Commodities": "commodity",
    "Equities": "equity",
}
_UINT64 = (1 << 64) - 1
_INT256_SIGN = 1 << 255


@dataclass(frozen=True)
class Feed:
    symbol: str
    name: str
    asset_name: str
    path: str
    proxy: str
    decimals: int
    kind: Kind
    heartbeat: int

    @property
    def instrument(self) -> Instrument:
        return Instrument(
            symbol=self.symbol,
            name=self.asset_name or self.name,
            kind=self.kind,
            unit="USD" if self.symbol.endswith("/USD") else self.symbol.split("/")[-1],
            measure="percent",
            source="Chainlink Data Feeds (Ethereum mainnet)",
            url=FEED_PAGE.format(path=self.path),
        )


@dataclass(frozen=True)
class _Round:
    answer: float
    updated_at: int


def _words(hexdata: str) -> list[int]:
    body = hexdata[2:]
    return [int(body[i : i + 64], 16) for i in range(0, len(body), 64)]


def _signed(value: int) -> int:
    return value - (1 << 256) if value & _INT256_SIGN else value


def _encode_uint(selector: str, value: int) -> str:
    return selector + hex(value)[2:].rjust(64, "0")


def _feed_symbol(name: str) -> str:
    base = re.sub(r"\s*\(.*?\)\s*", "", name).strip()
    base = re.sub(r"\s*[/-]\s*", "/", base)
    return base.upper()


class Chainlink:
    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher
        self._rounds: dict[tuple[str, int], _Round | None] = {}
        self._resolved: dict[tuple[str, int, int], _Round | None] = {}
        # Public gateways rate-limit bursts; bound concurrent batch requests across all feeds.
        self._gate = asyncio.Semaphore(_MAX_CONCURRENT_BATCHES)
        self._pace_lock = asyncio.Lock()
        self._next_slot = 0.0
        self._cooldown: dict[str, float] = {}
        self._rotation = 0
        self._anchor_cache: dict[tuple[str, int, int], list[tuple[int, int]]] = {}

    # -- catalog -------------------------------------------------------------------------

    async def catalog(self) -> dict[str, Feed]:
        entries = await self.fetcher.request(
            "GET", FEED_DIRECTORY_URL, subject="Chainlink feed directory", ttl=86400
        )
        if not isinstance(entries, list):
            raise MarketDataError("Chainlink feed directory returned an unexpected payload.")
        feeds: dict[str, Feed] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            docs = entry.get("docs") or {}
            path = entry.get("path") or ""
            kind = _KINDS.get(entry.get("feedType") or "")
            if (
                kind is None
                or docs.get("productType") != "Price"
                or "svr" in path
                or entry.get("feedCategory") not in _CATEGORIES
                or not entry.get("proxyAddress")
            ):
                continue
            symbol = _feed_symbol(str(entry.get("name") or path))
            if symbol in feeds:
                continue
            feeds[symbol] = Feed(
                symbol=symbol,
                name=str(entry.get("name") or symbol),
                asset_name=str(entry.get("assetName") or ""),
                path=path,
                proxy=str(entry["proxyAddress"]),
                decimals=int(entry.get("decimals") or 8),
                kind=kind,
                heartbeat=int(entry.get("heartbeat") or 0),
            )
        if not feeds:
            raise MarketDataError("Chainlink feed directory listed no usable price feeds.")
        return feeds

    async def resolve(self, symbol: str) -> Feed | None:
        feeds = await self.catalog()
        compact = re.sub(r"[\s/_:-]+", "", symbol.strip().upper())
        if not compact:
            return None
        by_compact = {feed.symbol.replace("/", ""): feed for feed in feeds.values()}
        return by_compact.get(compact) or by_compact.get(compact + "USD")

    async def search(self, query: str, limit: int) -> list[Feed]:
        feeds = await self.catalog()
        needle = query.strip().lower()
        compact = re.sub(r"[\s/_:-]+", "", needle)
        if not needle:
            return []
        matches = [
            feed
            for feed in feeds.values()
            if needle in feed.name.lower()
            or needle in feed.asset_name.lower()
            or (compact and compact in feed.symbol.replace("/", "").lower())
        ]
        matches.sort(key=lambda feed: (not feed.symbol.lower().startswith(needle), feed.symbol))
        return matches[:limit]

    # -- RPC -----------------------------------------------------------------------------

    async def _rpc(self, calls: list[tuple[str, str]]) -> list[str | None]:
        results: list[str | None] = [None] * len(calls)
        for offset in range(0, len(calls), _BATCH):
            chunk = calls[offset : offset + _BATCH]
            payload = [
                {
                    "jsonrpc": "2.0",
                    "id": index,
                    "method": "eth_call",
                    "params": [{"to": to, "data": data}, "latest"],
                }
                for index, (to, data) in enumerate(chunk)
            ]
            body = await self._post_batch(payload)
            for item in body:
                result = item.get("result") if isinstance(item, dict) else None
                index = int(item["id"]) if isinstance(item, dict) and "id" in item else None
                if index is None or not 0 <= index < len(chunk):
                    continue
                results[offset + index] = (
                    result if isinstance(result, str) and len(result) > 2 else None
                )
        return results

    async def _post_batch(self, payload: list[dict[str, Any]]) -> list[Any]:
        """POST one JSON-RPC batch across the gateways, cooling down any that throttle.

        Per-item errors that mention throttling are treated as a failed batch: a reverted
        `getRoundData` is a legitimate "no such round", a rate-limited item is not.
        """
        last_error = "no response"
        async with self._gate:
            for attempt in range(_ATTEMPTS):
                for url in self._gateways():
                    await self._pace()
                    try:
                        response = await self.fetcher.client.post(
                            url, json=payload, timeout=_BATCH_TIMEOUT_SECONDS
                        )
                    except httpx.HTTPError as exc:
                        last_error = exc.__class__.__name__
                        self._cool(url)
                        continue
                    if response.status_code != 200:
                        last_error = f"HTTP {response.status_code}"
                        self._cool(url)
                        continue
                    try:
                        body = response.json()
                    except ValueError:
                        last_error = "invalid JSON"
                        continue
                    if isinstance(body, dict) and body.get("error"):
                        last_error = str(body["error"].get("message", "RPC error"))[:80]
                        self._cool(url)
                        continue
                    if not isinstance(body, list) or len(body) != len(payload):
                        last_error = "unexpected response"
                        continue
                    messages = [
                        str(item.get("error", {}).get("message", "")).lower()
                        for item in body
                        if isinstance(item, dict) and item.get("error")
                    ]
                    if any(
                        marker in message for message in messages for marker in _THROTTLE_MARKERS
                    ):
                        last_error = "per-item rate limit"
                        self._cool(url)
                        continue
                    return body
                await asyncio.sleep(_BACKOFF_SECONDS * (attempt + 1))
        raise MarketDataError(
            f"Ethereum RPC gateways are unavailable ({last_error}). Try again later."
        )

    def _gateways(self) -> list[str]:
        """Gateways not cooling down, rotated so consecutive batches spread across them."""
        now = asyncio.get_running_loop().time()
        ready = [url for url in RPC_URLS if self._cooldown.get(url, 0.0) <= now] or list(RPC_URLS)
        self._rotation += 1
        shift = self._rotation % len(ready)
        return ready[shift:] + ready[:shift]

    def _cool(self, url: str) -> None:
        self._cooldown[url] = asyncio.get_running_loop().time() + _COOLDOWN_SECONDS

    async def _pace(self) -> None:
        """Keep the global request rate under the public gateways' quotas."""
        async with self._pace_lock:
            wait = self._next_slot - asyncio.get_running_loop().time()
            if wait > 0:
                await asyncio.sleep(wait)
            self._next_slot = asyncio.get_running_loop().time() + _MIN_INTERVAL_SECONDS

    async def _rounds_for(self, feed: Feed, round_ids: list[int]) -> dict[int, _Round | None]:
        missing = [rid for rid in round_ids if (feed.proxy, rid) not in self._rounds]
        if missing:
            raw = await self._rpc(
                [(feed.proxy, _encode_uint(_SELECTOR["getRoundData"], rid)) for rid in missing]
            )
            for rid, result in zip(missing, raw, strict=True):
                if result is None:
                    self._rounds[(feed.proxy, rid)] = None
                    continue
                words = _words(result)
                answer = _signed(words[1]) / 10**feed.decimals
                self._rounds[(feed.proxy, rid)] = _Round(answer=answer, updated_at=words[3])
        return {rid: self._rounds[(feed.proxy, rid)] for rid in round_ids}

    async def latest(self, feed: Feed) -> _Round:
        (result,) = await self._rpc([(feed.proxy, _SELECTOR["latestRoundData"])])
        if result is None:
            raise MarketDataError(f"Chainlink feed {feed.symbol} returned no latest round.")
        words = _words(result)
        return _Round(answer=_signed(words[1]) / 10**feed.decimals, updated_at=words[3])

    async def _latest_round_id(self, feed: Feed) -> int:
        (result,) = await self._rpc([(feed.proxy, _SELECTOR["latestRoundData"])])
        if result is None:
            raise MarketDataError(f"Chainlink feed {feed.symbol} returned no latest round.")
        return _words(result)[0]

    async def _phase_ranges(self, feed: Feed, earliest: int) -> list[tuple[int, int, int]]:
        """Return (phase, max_round, first_updated_at) for phases back to the one covering
        `earliest`, newest first."""
        latest_id = await self._latest_round_id(feed)
        phase, max_round = latest_id >> 64, latest_id & _UINT64
        ranges: list[tuple[int, int, int]] = []
        while phase >= 1:
            first = (await self._rounds_for(feed, [(phase << 64) | 1]))[(phase << 64) | 1]
            first_at = first.updated_at if first else 0
            ranges.append((phase, max_round, first_at))
            if first_at <= earliest or phase == 1:
                break
            phase -= 1
            (aggregator,) = await self._rpc(
                [(feed.proxy, _encode_uint(_SELECTOR["phaseAggregators"], phase))]
            )
            if aggregator is None:
                break
            address = "0x" + aggregator[-40:]
            (latest_round,) = await self._rpc([(address, _SELECTOR["latestRound"])])
            if latest_round is None:
                break
            max_round = _words(latest_round)[0] & _UINT64
        return ranges

    async def closes(self, feed: Feed, targets: list[int]) -> list[tuple[int, _Round | None]]:
        """For each target unix timestamp return the last round updated at or before it."""
        pending = [t for t in targets if (feed.proxy, t, 0) not in self._resolved]
        if pending:
            ranges = await self._phase_ranges(feed, min(pending))
            by_phase: dict[int, list[int]] = {}
            for target in pending:
                for phase, _, first_at in ranges:
                    if first_at <= target:
                        by_phase.setdefault(phase, []).append(target)
                        break
                else:
                    self._resolved[(feed.proxy, target, 0)] = None
            await asyncio.gather(
                *(
                    self._search_phase(
                        feed, phase, next(m for p, m, _ in ranges if p == phase), phase_targets
                    )
                    for phase, phase_targets in by_phase.items()
                )
            )
        return [(t, self._resolved[(feed.proxy, t, 0)]) for t in targets]

    async def _anchors(self, feed: Feed, phase: int, max_round: int) -> list[tuple[int, int]]:
        """Evenly spaced (round, updated_at) anchors across a phase; one batch, cached."""
        cache_key = (feed.proxy, phase, max_round)
        cached = self._anchor_cache.get(cache_key)
        if cached is not None:
            return cached
        count = min(_ANCHORS, max_round)
        rounds = sorted({1 + (i * (max_round - 1)) // max(count - 1, 1) for i in range(count)})
        data = await self._rounds_for(feed, [(phase << 64) | r for r in rounds])
        anchors = [
            (r, data[(phase << 64) | r].updated_at)
            for r in rounds
            if data[(phase << 64) | r] is not None
        ]
        self._anchor_cache[cache_key] = anchors
        return anchors

    async def _search_phase(
        self, feed: Feed, phase: int, max_round: int, targets: list[int]
    ) -> None:
        """Find the last round at or before each target within one aggregator phase.

        A grid of anchor rounds (one batch per phase, cached) narrows every target to the
        interval between two anchors; bisection then needs only log2(anchor spacing) steps, and
        all targets advance together in each batched step.
        """
        key = lambda r: (phase << 64) | r
        anchors = await self._anchors(feed, phase, max_round)
        low: dict[int, int] = {}
        high: dict[int, int] = {}
        for t in targets:
            lo, hi = 1, max_round
            for r, at in anchors:
                if at <= t:
                    lo = r
                else:
                    hi = r - 1
                    break
            low[t], high[t] = lo, max(hi, lo)
        while any(low[t] < high[t] for t in targets):
            probes = {t: (low[t] + high[t] + 1) // 2 for t in targets if low[t] < high[t]}
            data = await self._rounds_for(feed, sorted({key(r) for r in probes.values()}))
            for t, r in probes.items():
                record = data[key(r)]
                if record is not None and record.updated_at <= t:
                    low[t] = r
                else:
                    high[t] = r - 1
        finals = await self._rounds_for(feed, sorted({key(low[t]) for t in targets}))
        for t in targets:
            self._resolved[(feed.proxy, t, 0)] = finals[key(low[t])]

    async def series(self, feed: Feed, start: date, end: date, weekly: bool) -> list[Point]:
        """Closing values per UTC day (or per week ending on the target day) in [start, end].

        Markets that do not trade every day (equities, FX, metals) only yield a point for days
        on which the feed actually updated, so weekends and holidays are not repeated closes.
        """
        step = 7 if weekly else 1
        days: list[date] = []
        cursor = end
        while cursor >= start:
            days.append(cursor)
            cursor -= timedelta(days=step)
        days.reverse()
        targets = [day_start(day + timedelta(days=1)) - 1 for day in days]
        resolved = await self.closes(feed, targets)
        stale_after = 0 if feed.kind == "crypto" else (step * 86400)
        points: list[Point] = []
        for day, target, (_, record) in zip(days, targets, resolved, strict=True):
            if record is None or record.answer <= 0:
                continue
            if stale_after and record.updated_at < target - stale_after:
                continue
            points.append(
                Point(
                    date=day.isoformat(),
                    observed_at=iso_from_unix(record.updated_at),
                    value=record.answer,
                )
            )
        return points
