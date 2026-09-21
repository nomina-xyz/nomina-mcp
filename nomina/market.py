"""Research orchestration over public sources: on-chain oracle prices and public statistics."""

from __future__ import annotations

import asyncio
import math
import statistics
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from typing import Any, Literal

import httpx

from nomina.sources import bls, treasury
from nomina.sources.bls import BLS
from nomina.sources.chainlink import Chainlink, Feed
from nomina.sources.common import Fetcher, Instrument, MarketDataError, Point, Series, now_iso
from nomina.sources.edgar import Edgar
from nomina.sources.gdelt import Gdelt
from nomina.sources.treasury import Treasury

Period = Literal["1mo", "3mo", "6mo", "1y", "5y", "ytd"]

OVERVIEW_SYMBOLS = (
    "BTC/USD",
    "ETH/USD",
    "SOL/USD",
    "XAU/USD",
    "SPY/USD",
    "QQQ/USD",
    "EUR/USD",
    "US2Y",
    "US10Y",
    "CPI",
)

_PERIOD_DAYS = {"1mo": 30, "3mo": 91, "6mo": 182, "1y": 365, "5y": 1826}
_MAX_WINDOW_DAYS = 9131  # 25 years
_WEEKLY_AFTER_DAYS = 730
_WINDOW_CAVEAT = (
    "Explicit date window; observations are the source's available sessions inside the window."
)
_STATISTICS_CAVEAT = (
    "Volatility and drawdown are descriptive statistics of the returned series, not forecasts."
)
_LATEST_CAVEAT = (
    "The most recent observation can be a partial day; on-chain feeds update on heartbeat or "
    "deviation, so a day's close is its last update before midnight UTC."
)


def _source_terms(loaded: Iterable[Series]) -> list[str]:
    """Statements a source's terms require wherever its data are shown."""
    if any(series.instrument.source == bls.SOURCE_NAME for series in loaded):
        return [bls.TERMS_STATEMENT]
    return []


_PERIODS_PER_YEAR = {"1d": 252, "1wk": 52, "1mo": 12}

__all__ = ["OVERVIEW_SYMBOLS", "MarketData", "MarketDataError", "Period"]


def _today() -> date:
    return datetime.now(UTC).date()


def _normalize_period(period: str) -> str:
    if period not in _PERIOD_DAYS and period != "ytd":
        raise MarketDataError("Period must be one of: 1mo, 3mo, 6mo, 1y, 5y, ytd.")
    return period


def _period_window(period: str) -> tuple[date, date]:
    end = _today()
    if period == "ytd":
        return date(end.year, 1, 1), end
    return end - timedelta(days=_PERIOD_DAYS[period]), end


def _normalize_window(start: date | None, end: date | None) -> tuple[date, date] | None:
    if start is None and end is None:
        return None
    if start is None or end is None:
        raise MarketDataError("Provide both start and end dates, or neither.")
    if not isinstance(start, date) or not isinstance(end, date):
        raise MarketDataError("start and end must be ISO dates (YYYY-MM-DD).")
    if isinstance(start, datetime):
        start = start.date()
    if isinstance(end, datetime):
        end = end.date()
    if start >= end:
        raise MarketDataError("start must be earlier than end.")
    if end > _today():
        raise MarketDataError("end cannot be in the future.")
    if (end - start).days > _MAX_WINDOW_DAYS:
        raise MarketDataError("Date windows are limited to 25 years.")
    return start, end


def _weekly_downsample(points: list[Point]) -> list[Point]:
    """Keep the last observation of each ISO week."""
    kept: dict[tuple[int, int], Point] = {}
    for point in points:
        iso = date.fromisoformat(point.date).isocalendar()
        kept[(iso.year, iso.week)] = point
    return [kept[key] for key in sorted(kept)]


def _source_error(exc: BaseException) -> str:
    return str(exc) if isinstance(exc, MarketDataError) else "Source retrieval failed."


class MarketData:
    """Read-only research over Chainlink feeds, US Treasury, BLS, SEC EDGAR and GDELT."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.fetcher = Fetcher(client)
        self.chainlink = Chainlink(self.fetcher)
        self.treasury = Treasury(self.fetcher)
        self.bls = BLS(self.fetcher)
        self.edgar = Edgar(self.fetcher)
        self.gdelt = Gdelt(self.fetcher)

    # -- resolution ----------------------------------------------------------------------

    async def _resolve(self, symbol: str) -> tuple[Instrument, Feed | None]:
        if not isinstance(symbol, str) or not symbol.strip():
            raise MarketDataError("A symbol must be non-empty text.")
        tenor = treasury.resolve(symbol)
        if tenor:
            return treasury.instrument(tenor), None
        macro = bls.resolve(symbol)
        if macro:
            return bls.instrument(macro), None
        feed = await self.chainlink.resolve(symbol)
        if feed:
            return feed.instrument, feed
        raise MarketDataError(
            f"Unknown symbol {symbol!r}. Use search_markets to find on-chain feeds (e.g. BTC/USD, "
            "SPY/USD, EUR/USD, XAU/USD), Treasury tenors (US2Y, US10Y) or macro series (CPI, UNRATE)."
        )

    async def _series(
        self, instrument: Instrument, feed: Feed | None, start: date, end: date, label: str
    ) -> Series:
        weekly = (end - start).days > _WEEKLY_AFTER_DAYS
        notes: list[str] = []
        if feed is not None:
            points = await self.chainlink.series(feed, start, end, weekly)
            latest = await self.chainlink.latest(feed)
            latest_value: float | None = latest.answer
            latest_at: str | None = datetime.fromtimestamp(latest.updated_at, UTC).isoformat()
            latest_at = latest_at.replace("+00:00", "Z")
            interval = "1wk" if weekly else "1d"
            source_url = instrument.url
        elif instrument.kind == "yield":
            points = await self.treasury.series(instrument.symbol, start, end)
            if weekly:
                points = _weekly_downsample(points)
            interval = "1wk" if weekly else "1d"
            source_url = self.treasury.source_url(start)
            latest_value = points[-1].value if points else None
            latest_at = points[-1].observed_at if points else None
        else:
            # Monthly releases lag by weeks; always include the two most recent months.
            macro_start = min(start, end - timedelta(days=75))
            points = await self.bls.series(instrument.symbol, macro_start, end)
            if macro_start < start:
                notes.append(
                    "Monthly series: the window was widened to include the latest two releases."
                )
            notes.append(bls.TERMS_STATEMENT)
            interval = "1mo"
            source_url = instrument.url
            latest_value = points[-1].value if points else None
            latest_at = points[-1].observed_at if points else None
        if not points:
            raise MarketDataError(
                f"{instrument.source} returned no observations for {instrument.symbol} in this window."
            )
        if feed is not None and points[0].date > start.isoformat():
            notes.append(
                f"The on-chain feed's history starts {points[0].date}; earlier dates are unavailable."
            )
        return Series(
            instrument=instrument,
            period=label,
            interval=interval,
            points=points,
            source_url=source_url,
            latest_value=latest_value,
            latest_at=latest_at,
            notes=notes,
        )

    async def _load(
        self, symbol: str, period: str | None, window: tuple[date, date] | None
    ) -> Series:
        instrument, feed = await self._resolve(symbol)
        if window:
            start, end = window
            label = f"{start.isoformat()}..{end.isoformat()}"
        else:
            start, end = _period_window(period or "3mo")
            label = period or "3mo"
        return await self._series(instrument, feed, start, end, label)

    # -- tools ---------------------------------------------------------------------------

    async def search(self, query: str, limit: int = 6) -> dict[str, Any]:
        if not isinstance(query, str) or not (query := query.strip()) or len(query) > 200:
            raise MarketDataError("Search query must contain 1 to 200 non-whitespace characters.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
            raise MarketDataError("Search limit must be an integer from 1 to 10.")
        feeds_task = self.chainlink.search(query, limit)
        companies_task = self.edgar.search(query, limit)
        news_task = self.gdelt.headlines(query, limit)
        feeds, companies, news_result = await asyncio.gather(
            feeds_task, companies_task, news_task, return_exceptions=True
        )
        partial_errors: list[dict[str, str]] = []
        instruments: list[dict[str, Any]] = []
        if isinstance(feeds, BaseException):
            partial_errors.append(
                {"source": "Chainlink feed directory", "message": _source_error(feeds)}
            )
        else:
            for feed in feeds:
                inst = feed.instrument
                instruments.append(
                    {
                        "symbol": inst.symbol,
                        "name": inst.name,
                        "asset_type": inst.kind,
                        "source": inst.source,
                        "url": inst.url,
                        "tools": ["research_asset", "compare_assets"],
                    }
                )
        for tenor in treasury.search(query, limit):
            inst = treasury.instrument(tenor)
            instruments.append(
                {
                    "symbol": inst.symbol,
                    "name": inst.name,
                    "asset_type": inst.kind,
                    "source": inst.source,
                    "url": inst.url,
                    "tools": ["research_asset", "compare_assets"],
                }
            )
        for macro in bls.search(query, limit):
            inst = bls.instrument(macro)
            instruments.append(
                {
                    "symbol": inst.symbol,
                    "name": inst.name,
                    "asset_type": inst.kind,
                    "source": inst.source,
                    "url": inst.url,
                    "tools": ["research_asset", "compare_assets"],
                }
            )
        if isinstance(companies, BaseException):
            partial_errors.append(
                {"source": "SEC EDGAR company list", "message": _source_error(companies)}
            )
        else:
            for company in companies:
                instruments.append(
                    {
                        "symbol": company["ticker"],
                        "name": company["name"],
                        "asset_type": "company",
                        "source": "SEC EDGAR",
                        "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={company['cik']:010d}",
                        "tools": ["company_fundamentals"],
                    }
                )
        news: list[dict[str, str | None]] = []
        sources: list[dict[str, Any]] = [
            {
                "name": "Chainlink feed directory",
                "url": "https://data.chain.link/feeds/ethereum/mainnet",
                "as_of": None,
            },
            {
                "name": "SEC EDGAR company list",
                "url": "https://www.sec.gov/files/company_tickers.json",
                "as_of": None,
            },
        ]
        if isinstance(news_result, BaseException):
            partial_errors.append(
                {"source": "GDELT article search", "message": _source_error(news_result)}
            )
        else:
            news = news_result
            sources.append(self.gdelt.source(query))
        caveats = [
            (
                "Instruments are matches from Nomina's catalog of on-chain feeds, Treasury tenors, "
                "BLS series and SEC registrants; it is not an exhaustive market search."
            ),
            "Headlines are GDELT article records (title and link), not article text.",
        ]
        if not instruments:
            caveats.append("No catalog instrument matched this query.")
        if not news:
            caveats.append("No usable recent headlines were returned.")
        return {
            "query": query,
            "retrieved_at": now_iso(),
            "sources": sources,
            "instruments": instruments[: max(limit, 1) * 2],
            "news": news,
            "partial_errors": partial_errors,
            "caveats": caveats,
        }

    async def research(
        self,
        symbol: str,
        period: Period = "3mo",
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> dict[str, Any]:
        window = _normalize_window(start, end)
        selected = None if window else _normalize_period(period)
        instrument, _ = await self._resolve(symbol)
        series_result, news_result = await asyncio.gather(
            self._load(symbol, selected, window),
            self.gdelt.headlines(instrument.name, 6),
            return_exceptions=True,
        )
        if isinstance(series_result, BaseException):
            if isinstance(series_result, MarketDataError):
                raise series_result
            raise MarketDataError("Source retrieval failed.") from series_result
        series = series_result
        partial_errors: list[dict[str, str]] = []
        news: list[dict[str, str | None]] = []
        sources: list[dict[str, Any]] = [
            {"name": instrument.source, "url": series.source_url, "as_of": series.latest_at}
        ]
        if isinstance(news_result, BaseException):
            partial_errors.append(
                {"source": "GDELT article search", "message": _source_error(news_result)}
            )
        else:
            news = news_result
            sources.append(self.gdelt.source(instrument.name))
        performance = self._performance(series.points, instrument.measure, instrument.unit)
        caveats = [
            _LATEST_CAVEAT,
            "Period performance uses the first and last available observations in the selected range.",
        ]
        caveats.extend(series.notes)
        if window:
            caveats.append(_WINDOW_CAVEAT)
        if instrument.measure == "percent":
            caveats.append(_STATISTICS_CAVEAT)
        else:
            caveats.append("Changes are in percentage points of the reported rate, not returns.")
        if not news:
            caveats.append("No usable recent headlines were returned.")
        return {
            "symbol": instrument.symbol,
            "period": series.period,
            "interval": series.interval,
            "retrieved_at": now_iso(),
            "sources": sources,
            "asset": {
                "name": instrument.name,
                "asset_type": instrument.kind,
                "unit": instrument.unit,
                "source": instrument.source,
                "frequency": instrument.frequency,
            },
            "latest": {"value": series.latest_value, "observed_at": series.latest_at},
            "period_performance": performance,
            "statistics": self._statistics(series.points, instrument.measure, series.interval),
            "history": [
                {"date": point.date, "observed_at": point.observed_at, "value": point.value}
                for point in series.points
            ],
            "news": news,
            "partial_errors": partial_errors,
            "caveats": caveats,
        }

    async def compare(
        self,
        symbols: list[str],
        period: Period = "3mo",
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> dict[str, Any]:
        if not isinstance(symbols, list):
            raise MarketDataError("Symbols must be a list containing 2 to 6 unique symbols.")
        unique: list[str] = []
        for symbol in symbols:
            if not isinstance(symbol, str) or not symbol.strip():
                raise MarketDataError("A symbol must be non-empty text.")
            key = symbol.strip().upper()
            if key not in unique:
                unique.append(key)
        if not 2 <= len(unique) <= 6:
            raise MarketDataError("Comparison requires 2 to 6 unique symbols.")
        window = _normalize_window(start, end)
        selected = None if window else _normalize_period(period)
        results = await asyncio.gather(
            *(self._load(symbol, selected, window) for symbol in unique), return_exceptions=True
        )
        loaded: dict[str, Series] = {}
        assets: dict[str, dict[str, Any]] = {}
        errors: list[dict[str, str]] = []
        for symbol, result in zip(unique, results, strict=True):
            if isinstance(result, BaseException):
                message = _source_error(result)
                errors.append({"symbol": symbol, "message": message})
                assets[symbol] = {"symbol": symbol, "available": False, "error": message}
            else:
                loaded[symbol] = result
        if not loaded:
            details = "; ".join(f"{e['symbol']}: {e['message']}" for e in errors)
            raise MarketDataError(f"No requested series could be retrieved. {details}")

        common: set[str] | None = None
        by_date: dict[str, dict[str, Point]] = {}
        for symbol, series in loaded.items():
            mapping = {point.date: point for point in series.points}
            by_date[symbol] = mapping
            common = set(mapping) if common is None else common & set(mapping)
        ordered = sorted(common or set())
        possible = len(loaded) >= 2 and len(ordered) >= 2
        first_date = ordered[0] if possible else None
        last_date = ordered[-1] if possible else None
        measures = {series.instrument.measure for series in loaded.values()}
        frequencies = {series.instrument.frequency for series in loaded.values()}

        for symbol, series in loaded.items():
            inst = series.instrument
            if possible and first_date and last_date:
                performance = self._performance(
                    [by_date[symbol][first_date], by_date[symbol][last_date]],
                    inst.measure,
                    inst.unit,
                )
            else:
                performance = {
                    "measure": inst.measure,
                    "return_percent": None,
                    "change": None,
                    "first_value": None,
                    "last_value": None,
                    "first_observation_date": None,
                    "last_observation_date": None,
                    "explanation": "Comparison needs two retrieved series and two shared observation dates.",
                }
            assets[symbol] = {
                "symbol": inst.symbol,
                "available": True,
                "name": inst.name,
                "asset_type": inst.kind,
                "unit": inst.unit,
                "source": {
                    "name": inst.source,
                    "url": series.source_url,
                    "as_of": series.latest_at,
                },
                "common_period_performance": performance,
            }

        returns = [assets[s]["common_period_performance"].get("return_percent") for s in loaded]
        comparable = possible and measures == {"percent"} and all(r is not None for r in returns)
        if not possible:
            note = "Comparison needs two retrieved series and two shared observation dates."
        elif measures != {"percent"}:
            note = (
                "Returns are not directly comparable: the selection mixes prices (percent returns) "
                "with rates or indexes (point changes). Compare the per-asset changes instead."
            )
        elif not comparable:
            note = "Returns are not directly comparable because at least one common-period return is unavailable."
        else:
            note = "Returns use common observation dates; prices are in each instrument's own unit."
        if frequencies == {"daily", "monthly"}:
            note += " Monthly series only share month-start dates with daily series."

        if window:
            label = f"{window[0].isoformat()}..{window[1].isoformat()}"
        else:
            label = selected or "3mo"
        interval = sorted({series.interval for series in loaded.values()})
        return {
            "symbols": unique,
            "period": label,
            "interval": interval[0] if len(interval) == 1 else "mixed",
            "retrieved_at": now_iso(),
            "assets": [assets[symbol] for symbol in unique],
            "partial_errors": errors,
            "comparison": {
                "common_first_observation_date": first_date,
                "common_last_observation_date": last_date,
                "common_observation_count": len(ordered),
                "returns_comparable": comparable,
                "note": note,
            },
            "caveats": [
                "Each series is reported in its own unit; no currency conversion is performed.",
                _LATEST_CAVEAT,
                "Shared dates are UTC calendar dates of the observations.",
            ]
            + ([_WINDOW_CAVEAT] if window else [])
            + _source_terms(loaded.values()),
        }

    async def overview(self, period: Period = "1mo") -> dict[str, Any]:
        selected = _normalize_period(period)
        results = await asyncio.gather(
            *(self._load(symbol, selected, None) for symbol in OVERVIEW_SYMBOLS),
            return_exceptions=True,
        )
        assets: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for symbol, result in zip(OVERVIEW_SYMBOLS, results, strict=True):
            if isinstance(result, BaseException):
                message = _source_error(result)
                errors.append({"symbol": symbol, "message": message})
                assets.append({"symbol": symbol, "available": False, "error": message})
                continue
            inst = result.instrument
            assets.append(
                {
                    "symbol": inst.symbol,
                    "available": True,
                    "name": inst.name,
                    "asset_type": inst.kind,
                    "unit": inst.unit,
                    "latest": {"value": result.latest_value, "observed_at": result.latest_at},
                    "period_performance": self._performance(result.points, inst.measure, inst.unit),
                    "source": {
                        "name": inst.source,
                        "url": result.source_url,
                        "as_of": result.latest_at,
                    },
                }
            )
        if len(errors) == len(OVERVIEW_SYMBOLS):
            raise MarketDataError("No overview series could be retrieved.")
        return {
            "period": selected,
            "retrieved_at": now_iso(),
            "assets": assets,
            "partial_errors": errors,
            "caveats": [
                "Each series is reported in its own unit; no currency conversion is performed.",
                _LATEST_CAVEAT,
                "Yields and rates change in percentage points; prices change in percent.",
                "Basket membership is fixed by Nomina, not a provider index.",
            ]
            + _source_terms(r for r in results if isinstance(r, Series)),
        }

    async def fundamentals(self, ticker: str) -> dict[str, Any]:
        if not isinstance(ticker, str) or not ticker.strip():
            raise MarketDataError("A ticker must be non-empty text.")
        company = await self.edgar.resolve(ticker)
        if company is None:
            raise MarketDataError(
                f"No SEC registrant with ticker {ticker.strip().upper()!r}. Use search_markets to find one."
            )
        report = await self.edgar.fundamentals(company)
        report["retrieved_at"] = now_iso()
        report["caveats"] = [
            (
                "Values are as reported in XBRL filings (US-GAAP), in the filer's reporting currency; "
                "restatements appear as later filings."
            ),
            "Latest annual figures come from 10-K filings; latest quarterly figures from 10-Q filings.",
            "This is filing data, not a valuation, forecast, or recommendation.",
        ]
        return report

    # -- analytics -----------------------------------------------------------------------

    @staticmethod
    def _performance(points: list[Point], measure: str, unit: str) -> dict[str, Any]:
        first, last = points[0], points[-1]
        explanation = None
        return_percent = None
        change = None
        if len(points) < 2 or first.date == last.date:
            explanation = "Change needs at least two distinct observations."
        else:
            change = last.value - first.value
            if measure == "percent":
                if first.value <= 0:
                    explanation = "Percent return is unavailable because the starting value is zero or negative."
                else:
                    computed = (last.value / first.value - 1) * 100
                    if math.isfinite(computed):
                        return_percent = computed
                    else:
                        explanation = "Percent return exceeds the supported numeric range."
            else:
                explanation = f"Change is in percentage points of the reported {unit} rate."
        return {
            "measure": measure,
            "return_percent": return_percent,
            "change": change,
            "first_value": first.value,
            "last_value": last.value,
            "first_observation_date": first.date,
            "last_observation_date": last.date,
            "explanation": explanation,
        }

    @staticmethod
    def _statistics(points: list[Point], measure: str, interval: str) -> dict[str, Any]:
        values = [point.value for point in points]
        result: dict[str, Any] = {
            "observation_count": len(values),
            "max_drawdown_percent": None,
            "annualized_volatility_percent": None,
            "explanation": None,
        }
        if measure != "percent":
            result["explanation"] = (
                "Drawdown and volatility apply to prices, not to rates or indexes."
            )
            return result
        if len(values) < 3 or any(value <= 0 for value in values):
            result["explanation"] = "Statistics need at least three positive observations."
            return result
        peak = values[0]
        drawdown = 0.0
        for value in values:
            peak = max(peak, value)
            drawdown = min(drawdown, (value / peak - 1) * 100)
        log_returns = [math.log(later / earlier) for earlier, later in pairwise(values)]
        result["max_drawdown_percent"] = drawdown
        result["annualized_volatility_percent"] = (
            statistics.stdev(log_returns) * math.sqrt(_PERIODS_PER_YEAR.get(interval, 252)) * 100
        )
        return result
