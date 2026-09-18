"""Yahoo Finance-backed market research helpers for Nomina."""

from __future__ import annotations

import asyncio
import math
import re
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from typing import Any, Literal
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

Period = Literal["1mo", "3mo", "6mo", "1y", "5y", "ytd"]

OVERVIEW_SYMBOLS = (
    "^GSPC",
    "^IXIC",
    "^DJI",
    "^RUT",
    "^VIX",
    "^TNX",
    "DX-Y.NYB",
    "GC=F",
    "CL=F",
    "BTC-USD",
    "ETH-USD",
    "EURUSD=X",
)

_YAHOO_ORIGIN = "https://query1.finance.yahoo.com"
_CHART_URL = _YAHOO_ORIGIN + "/v8/finance/chart/{}"
_SEARCH_URL = _YAHOO_ORIGIN + "/v1/finance/search"
_QUOTE_PAGE = "https://finance.yahoo.com/quote/{}"
_PERIODS = {"1mo", "3mo", "6mo", "1y", "5y", "ytd"}
_SYMBOL = re.compile(r"[A-Za-z0-9^=._-]{1,32}\Z")
_MAX_WINDOW_DAYS = 9131  # 25 years
_CACHE_TTL_SECONDS = 60
_CACHE_MAX_ENTRIES = 256
_WINDOW_CAVEAT = (
    "Explicit date window; observations are the provider's available sessions inside the window."
)
_STATISTICS_CAVEAT = (
    "Volatility and drawdown are descriptive statistics of the returned series, not forecasts."
)


class MarketDataError(Exception):
    """An actionable problem retrieving or interpreting provider data."""


@dataclass(frozen=True)
class _Bar:
    timestamp: int
    observed_at: str
    date: str
    close: float
    adjusted_close: float | None
    high: float | None
    low: float | None


@dataclass(frozen=True)
class _Chart:
    symbol: str
    period: str
    interval: str
    source_url: str
    name: str | None
    asset_type: str | None
    currency: str | None
    exchange: str | None
    bars: list[_Bar]
    provider_as_of: str | None
    timezone: str | None
    quote_price: float | None
    day_high: float | None
    day_low: float | None

    @property
    def return_basis(self) -> str:
        return (
            "adjusted_close"
            if all(bar.adjusted_close is not None for bar in self.bars)
            else "close"
        )


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _iso_timestamp(value: float) -> str:
    try:
        return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError) as exc:
        raise MarketDataError("Yahoo Finance returned an invalid timestamp.") from exc


def _finite_number(value: Any, field: str, *, allow_none: bool = True) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise MarketDataError(f"Yahoo Finance returned a non-finite or invalid {field} value.")
    return float(value)


def _timestamp(value: Any) -> int:
    number = _finite_number(value, "timestamp", allow_none=False)
    assert number is not None
    if not number.is_integer() or number < 0:
        raise MarketDataError("Yahoo Finance returned an invalid timestamp.")
    return int(number)


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def _normalize_symbol(symbol: str) -> str:
    if not isinstance(symbol, str):
        raise MarketDataError("A symbol must be text containing 1 to 32 supported characters.")
    normalized = symbol.strip().upper()
    if not _SYMBOL.fullmatch(normalized):
        raise MarketDataError(
            "A symbol must contain 1 to 32 letters, digits, or ^ = . _ - characters."
        )
    return normalized


def _normalize_period(period: str) -> str:
    if period not in _PERIODS:
        raise MarketDataError("Period must be one of: 1mo, 3mo, 6mo, 1y, 5y, ytd.")
    return period


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
    if end > datetime.now(UTC).date():
        raise MarketDataError("end cannot be in the future.")
    if (end - start).days > _MAX_WINDOW_DAYS:
        raise MarketDataError("Date windows are limited to 25 years.")
    return start, end


def _period_interval(period: str) -> str:
    return "1wk" if period == "5y" else "1d"


def _window_interval(start: date, end: date) -> str:
    return "1d" if (end - start).days <= 730 else "1wk"


def _window_label(start: date, end: date) -> str:
    return f"{start.isoformat()}..{end.isoformat()}"


def _unix_midnight(value: date) -> int:
    return int(datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp())


def _chart_error_message(exc: BaseException) -> str:
    return str(exc) if isinstance(exc, MarketDataError) else "Yahoo Finance chart retrieval failed."


def _https_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value)
        return (
            value if parsed.scheme == "https" and parsed.hostname and not parsed.username else None
        )
    except ValueError:
        return None


def _news_url(item: dict[str, Any]) -> str | None:
    canonical = item.get("canonicalUrl")
    if isinstance(canonical, dict):
        url = _https_url(canonical.get("url"))
        if url:
            return url
    return _https_url(item.get("link"))


def _published_at(item: dict[str, Any]) -> str | None:
    value = item.get("providerPublishTime")
    if value is None:
        return None
    return _iso_timestamp(_timestamp(value))


def _normalise_news(items: list[Any], limit: int) -> list[dict[str, str | None]]:
    normalised: list[dict[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for item in items:
        if not isinstance(item, dict):
            raise MarketDataError("Yahoo Finance returned malformed news data.")
        title = _text(item.get("title"))
        url = _news_url(item)
        if title is None or url is None:
            continue
        published_at = _published_at(item)
        key = (url, published_at)
        if key in seen:
            continue
        seen.add(key)
        normalised.append(
            {
                "title": title,
                "publisher": _text(item.get("publisher")),
                "url": url,
                "published_at": published_at,
            }
        )
    normalised.sort(key=lambda entry: entry["published_at"] or "", reverse=True)
    return normalised[:limit]


def _source(name: str, url: str, as_of: str | None) -> dict[str, str | None]:
    return {"name": name, "url": url, "as_of": as_of}


class MarketData:
    """Read-only Yahoo Finance data access using an injected HTTP client."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client
        self._cache: dict[str, tuple[float, Any]] = {}

    async def search(self, query: str, limit: int = 6) -> dict[str, Any]:
        """Return Yahoo Finance's bounded related instruments and linked headlines."""
        if not isinstance(query, str) or not (query := query.strip()) or len(query) > 200:
            raise MarketDataError("Search query must contain 1 to 200 non-whitespace characters.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
            raise MarketDataError("Search limit must be an integer from 1 to 10.")

        payload, source_url = await self._search_payload(query, limit)
        quotes = payload.get("quotes", [])
        news = payload.get("news", [])
        if not isinstance(quotes, list) or not isinstance(news, list):
            raise MarketDataError("Yahoo Finance returned a malformed search response.")

        instruments: list[dict[str, str | None]] = []
        seen: set[str] = set()
        for item in quotes:
            if not isinstance(item, dict):
                raise MarketDataError("Yahoo Finance returned malformed instrument data.")
            raw_symbol = _text(item.get("symbol"))
            if raw_symbol is None:
                continue
            try:
                symbol = _normalize_symbol(raw_symbol)
            except MarketDataError:
                continue
            if symbol in seen:
                continue
            seen.add(symbol)
            instruments.append(
                {
                    "symbol": symbol,
                    "name": _text(item.get("longname"))
                    or _text(item.get("shortname"))
                    or _text(item.get("displayName")),
                    "exchange": _text(item.get("exchDisp")) or _text(item.get("exchange")),
                    "asset_type": _text(item.get("quoteType")),
                    "url": _QUOTE_PAGE.format(quote(symbol, safe="")),
                }
            )
            if len(instruments) == limit:
                break

        headlines = _normalise_news(news, limit)
        latest_headline = max(
            (item["published_at"] for item in headlines if item["published_at"]), default=None
        )
        caveats = [
            "Results are Yahoo Finance search matches and linked headlines, not a complete market or news search.",
            "Headlines are not article text; Nomina does not summarise or fetch linked articles.",
        ]
        if not instruments:
            caveats.append("Yahoo Finance returned no matching instruments for this query.")
        if not headlines:
            caveats.append("Yahoo Finance returned no usable recent headlines for this query.")
        return {
            "query": query,
            "retrieved_at": _now(),
            "sources": [_source("Yahoo Finance search", source_url, latest_headline)],
            "instruments": instruments,
            "news": headlines,
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
        """Return a chart-backed asset report, retaining chart data if news is unavailable."""
        normalized = _normalize_symbol(symbol)
        window = _normalize_window(start, end)
        chart_request = (
            self._fetch_chart_window(normalized, *window)
            if window
            else self._fetch_chart(normalized, _normalize_period(period))
        )
        chart_result, news_result = await asyncio.gather(
            chart_request,
            self._search_payload(normalized, 6),
            return_exceptions=True,
        )
        if isinstance(chart_result, Exception):
            if isinstance(chart_result, MarketDataError):
                raise chart_result
            raise MarketDataError("Yahoo Finance chart retrieval failed.") from chart_result
        chart = chart_result
        assert isinstance(chart, _Chart)

        news: list[dict[str, str | None]] = []
        partial_errors: list[dict[str, str]] = []
        sources = [_source("Yahoo Finance chart", chart.source_url, chart.provider_as_of)]
        if isinstance(news_result, Exception):
            message = (
                str(news_result)
                if isinstance(news_result, MarketDataError)
                else "Yahoo Finance news retrieval failed."
            )
            partial_errors.append({"source": "Yahoo Finance search", "message": message})
        else:
            news_payload, news_url = news_result
            raw_news = news_payload.get("news", [])
            if not isinstance(raw_news, list):
                partial_errors.append(
                    {
                        "source": "Yahoo Finance search",
                        "message": "Yahoo Finance returned malformed news data.",
                    }
                )
            else:
                try:
                    news = _normalise_news(raw_news, 6)
                except MarketDataError as exc:
                    partial_errors.append({"source": "Yahoo Finance search", "message": str(exc)})
                else:
                    news_as_of = max(
                        (item["published_at"] for item in news if item["published_at"]),
                        default=None,
                    )
                    sources.append(_source("Yahoo Finance search", news_url, news_as_of))

        performance = self._performance(chart.bars, chart.return_basis)
        caveats = [
            "The latest chart bar can be incomplete; Yahoo Finance prices may be delayed.",
            "Period performance uses the first and last available chart observations in the selected range.",
            "Observation dates use the exchange timezone; bar timestamps mark the interval start, not the quote time.",
        ]
        if chart.return_basis == "close":
            caveats.append(
                "Yahoo Finance did not provide a complete adjusted-close series, so the return uses raw closes for every observation."
            )
        else:
            caveats.append(
                "Period performance uses adjusted closes consistently across the full return series."
            )
        if not news:
            caveats.append("No usable recent linked headlines were returned by Yahoo Finance.")
        if chart.quote_price is None or chart.provider_as_of is None:
            caveats.append(
                "The provider did not return a complete current quote and timestamp; consult the dated price history."
            )
        if chart.timezone is None:
            caveats.append(
                "The provider did not supply an exchange timezone; historical dates use UTC."
            )
        if window:
            caveats.append(_WINDOW_CAVEAT)
        caveats.append(_STATISTICS_CAVEAT)

        return {
            "symbol": chart.symbol,
            "period": chart.period,
            "interval": chart.interval,
            "retrieved_at": _now(),
            "sources": sources,
            "asset": {
                "name": chart.name,
                "asset_type": chart.asset_type,
                "currency": chart.currency,
                "exchange": chart.exchange,
                "date_timezone": chart.timezone or "UTC (provider timezone unavailable)",
            },
            "latest_price": {
                "value": chart.quote_price,
                "price_timestamp": chart.provider_as_of,
                "day_high": chart.day_high,
                "day_low": chart.day_low,
            },
            "period_performance": performance,
            "statistics": self._statistics(chart.bars, chart.return_basis, chart.interval),
            "price_history": [
                {
                    "date": bar.date,
                    "timestamp": bar.observed_at,
                    "close": bar.close,
                    "adjusted_close": bar.adjusted_close,
                }
                for bar in chart.bars
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
        """Compare chart returns only over common observation dates among available assets."""
        if not isinstance(symbols, list):
            raise MarketDataError("Symbols must be a list containing 2 to 6 unique symbols.")
        normalised: list[str] = []
        for symbol in symbols:
            candidate = _normalize_symbol(symbol)
            if candidate not in normalised:
                normalised.append(candidate)
        if not 2 <= len(normalised) <= 6:
            raise MarketDataError("Comparison requires 2 to 6 unique symbols.")
        window = _normalize_window(start, end)
        if window:
            requests = [self._fetch_chart_window(symbol, *window) for symbol in normalised]
            period_label, interval = _window_label(*window), _window_interval(*window)
        else:
            selected_period = _normalize_period(period)
            requests = [self._fetch_chart(symbol, selected_period) for symbol in normalised]
            period_label, interval = selected_period, _period_interval(selected_period)

        results = await asyncio.gather(*requests, return_exceptions=True)
        charts: dict[str, _Chart] = {}
        assets: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for symbol, result in zip(normalised, results, strict=True):
            if isinstance(result, Exception):
                message = _chart_error_message(result)
                errors.append({"symbol": symbol, "message": message})
                assets.append({"symbol": symbol, "available": False, "error": message})
            else:
                assert isinstance(result, _Chart)
                charts[symbol] = result

        if not charts:
            details = "; ".join(f"{item['symbol']}: {item['message']}" for item in errors)
            raise MarketDataError(
                f"Yahoo Finance could not retrieve any requested charts. {details}"
            )

        common_dates: set[str] | None = None
        date_maps: dict[str, dict[str, _Bar]] = {}
        for symbol, chart in charts.items():
            date_map = {bar.date: bar for bar in chart.bars}
            date_maps[symbol] = date_map
            common_dates = set(date_map) if common_dates is None else common_dates & set(date_map)
        ordered_common_dates = sorted(common_dates or set())
        comparison_possible = (
            len(charts) >= 2
            and len(ordered_common_dates) >= 2
            and all(chart.timezone is not None for chart in charts.values())
        )
        first_date = ordered_common_dates[0] if comparison_possible else None
        last_date = ordered_common_dates[-1] if comparison_possible else None

        bases = {chart.return_basis for chart in charts.values()}
        all_returns: list[float | None] = []
        for symbol in normalised:
            chart = charts.get(symbol)
            if chart is None:
                continue
            performance: dict[str, Any]
            if comparison_possible and first_date is not None and last_date is not None:
                performance = self._performance(
                    [date_maps[symbol][first_date], date_maps[symbol][last_date]],
                    chart.return_basis,
                )
            else:
                performance = {
                    "return_percent": None,
                    "basis": chart.return_basis,
                    "first_observation_date": None,
                    "last_observation_date": None,
                    "explanation": "Comparison needs two successful assets with known exchange timezones and two shared session dates.",
                }
            all_returns.append(performance["return_percent"])
            assets.append(
                {
                    "symbol": chart.symbol,
                    "available": True,
                    "name": chart.name,
                    "asset_type": chart.asset_type,
                    "currency": chart.currency,
                    "exchange": chart.exchange,
                    "date_timezone": chart.timezone or "UTC (provider timezone unavailable)",
                    "source": _source(
                        "Yahoo Finance chart", chart.source_url, chart.provider_as_of
                    ),
                    "common_period_performance": performance,
                }
            )

        returns_comparable = (
            comparison_possible
            and len(bases) == 1
            and all(value is not None for value in all_returns)
        )
        if not comparison_possible:
            comparison_note = "Comparison needs two successful assets with known exchange timezones and two shared session dates."
        elif len(bases) != 1:
            comparison_note = "Returns are not directly comparable because adjusted-close and raw-close bases differ between assets."
        elif not returns_comparable:
            comparison_note = "Returns are not directly comparable because at least one common-period return is unavailable."
        else:
            comparison_note = "Returns use common observation dates and a shared price basis; local-currency returns are shown without FX conversion."

        assets_by_symbol = {asset["symbol"]: asset for asset in assets}
        ordered_assets = [assets_by_symbol[symbol] for symbol in normalised]
        caveats = [
            "Each asset is reported in its local currency; no foreign-exchange conversion is performed.",
            "The latest chart bar can be incomplete; Yahoo Finance prices may be delayed.",
            "Shared exchange-local session dates need not have identical market closing times.",
        ]
        if window:
            caveats.append(_WINDOW_CAVEAT)
        return {
            "symbols": normalised,
            "period": period_label,
            "interval": interval,
            "retrieved_at": _now(),
            "assets": ordered_assets,
            "partial_errors": errors,
            "comparison": {
                "common_first_observation_date": first_date,
                "common_last_observation_date": last_date,
                "common_observation_count": len(ordered_common_dates),
                "returns_comparable": returns_comparable,
                "note": comparison_note,
            },
            "caveats": caveats,
        }

    async def overview(self, period: Period = "1mo") -> dict[str, Any]:
        """Return period returns for a fixed basket of indexes, rates, commodities and crypto."""
        selected_period = _normalize_period(period)
        results = await asyncio.gather(
            *(self._fetch_chart(symbol, selected_period) for symbol in OVERVIEW_SYMBOLS),
            return_exceptions=True,
        )
        assets: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for symbol, result in zip(OVERVIEW_SYMBOLS, results, strict=True):
            if isinstance(result, Exception):
                message = _chart_error_message(result)
                errors.append({"symbol": symbol, "message": message})
                assets.append({"symbol": symbol, "available": False, "error": message})
                continue
            assert isinstance(result, _Chart)
            assets.append(
                {
                    "symbol": result.symbol,
                    "available": True,
                    "name": result.name,
                    "asset_type": result.asset_type,
                    "currency": result.currency,
                    "latest_price": {
                        "value": result.quote_price,
                        "price_timestamp": result.provider_as_of,
                    },
                    "period_performance": self._performance(result.bars, result.return_basis),
                    "source": _source(
                        "Yahoo Finance chart", result.source_url, result.provider_as_of
                    ),
                }
            )
        if len(errors) == len(OVERVIEW_SYMBOLS):
            raise MarketDataError("Yahoo Finance could not retrieve any overview charts.")
        return {
            "period": selected_period,
            "interval": _period_interval(selected_period),
            "retrieved_at": _now(),
            "assets": assets,
            "partial_errors": errors,
            "caveats": [
                "Each asset is reported in its local currency; no foreign-exchange conversion is performed.",
                "The latest chart bar can be incomplete; Yahoo Finance prices may be delayed.",
                "Shared exchange-local session dates need not have identical market closing times.",
                "Basket membership is fixed by Nomina, not a provider index.",
            ],
        }

    async def _search_payload(self, query: str, limit: int) -> tuple[dict[str, Any], str]:
        params = {"q": query, "quotesCount": str(limit), "newsCount": str(limit)}
        source_url = str(httpx.URL(_SEARCH_URL, params=params))
        payload = await self._get_json(_SEARCH_URL, params, "search")
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("quotes"), list)
            or not isinstance(payload.get("news"), list)
        ):
            raise MarketDataError("Yahoo Finance returned a malformed search response.")
        return payload, source_url

    async def _fetch_chart(self, symbol: str, period: str) -> _Chart:
        interval = _period_interval(period)
        url = _CHART_URL.format(quote(symbol, safe=""))
        params = {"range": period, "interval": interval}
        source_url = str(httpx.URL(url, params=params))
        payload = await self._get_json(url, params, f"chart for {symbol}")
        return self._parse_chart(
            symbol, payload, period_label=period, interval=interval, source_url=source_url
        )

    async def _fetch_chart_window(self, symbol: str, start: date, end: date) -> _Chart:
        interval = _window_interval(start, end)
        url = _CHART_URL.format(quote(symbol, safe=""))
        params = {
            "period1": str(_unix_midnight(start)),
            "period2": str(_unix_midnight(end + timedelta(days=1))),
            "interval": interval,
        }
        source_url = str(httpx.URL(url, params=params))
        payload = await self._get_json(url, params, f"chart for {symbol}")
        return self._parse_chart(
            symbol,
            payload,
            period_label=_window_label(start, end),
            interval=interval,
            source_url=source_url,
        )

    @staticmethod
    def _parse_chart(
        symbol: str, payload: Any, *, period_label: str, interval: str, source_url: str
    ) -> _Chart:
        if not isinstance(payload, dict):
            raise MarketDataError(
                f"Yahoo Finance returned a malformed chart response for {symbol}."
            )
        chart = payload.get("chart")
        if not isinstance(chart, dict):
            raise MarketDataError(
                f"Yahoo Finance returned a malformed chart response for {symbol}."
            )
        provider_error = chart.get("error")
        if provider_error:
            description = (
                provider_error.get("description") if isinstance(provider_error, dict) else None
            )
            message = _text(description) or "Yahoo Finance did not recognise this symbol."
            raise MarketDataError(f"Chart for {symbol} is unavailable: {message}")
        result = chart.get("result")
        if not isinstance(result, list) or not result or not isinstance(result[0], dict):
            raise MarketDataError(f"Yahoo Finance returned no chart data for {symbol}.")
        result_item = result[0]
        meta = result_item.get("meta")
        timestamps = result_item.get("timestamp")
        indicators = result_item.get("indicators")
        if (
            not isinstance(meta, dict)
            or not isinstance(timestamps, list)
            or not isinstance(indicators, dict)
        ):
            raise MarketDataError(f"Yahoo Finance returned malformed chart data for {symbol}.")
        quote_data = indicators.get("quote")
        if (
            not isinstance(quote_data, list)
            or not quote_data
            or not isinstance(quote_data[0], dict)
        ):
            raise MarketDataError(f"Yahoo Finance returned malformed chart prices for {symbol}.")
        quote_item = quote_data[0]
        closes = quote_item.get("close")
        highs = quote_item.get("high")
        lows = quote_item.get("low")
        if not all(isinstance(values, list) for values in (closes, highs, lows)):
            raise MarketDataError(f"Yahoo Finance returned malformed chart prices for {symbol}.")
        if not (len(timestamps) == len(closes) == len(highs) == len(lows)):
            raise MarketDataError(f"Yahoo Finance returned misaligned chart prices for {symbol}.")

        adjusted: list[Any] | None = None
        adjusted_sets = indicators.get("adjclose")
        if adjusted_sets is not None:
            if (
                not isinstance(adjusted_sets, list)
                or not adjusted_sets
                or not isinstance(adjusted_sets[0], dict)
                or not isinstance(adjusted_sets[0].get("adjclose"), list)
            ):
                raise MarketDataError(
                    f"Yahoo Finance returned malformed adjusted chart prices for {symbol}."
                )
            adjusted = adjusted_sets[0]["adjclose"]
            if len(adjusted) != len(timestamps):
                raise MarketDataError(
                    f"Yahoo Finance returned misaligned adjusted chart prices for {symbol}."
                )

        timezone_name = _text(meta.get("exchangeTimezoneName"))
        try:
            exchange_timezone = ZoneInfo(timezone_name) if timezone_name else UTC
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise MarketDataError(
                f"Yahoo Finance returned an unknown exchange timezone for {symbol}."
            ) from exc

        bars: list[_Bar] = []
        for index, raw_timestamp in enumerate(timestamps):
            timestamp = _timestamp(raw_timestamp)
            close = _finite_number(closes[index], "close")
            high = _finite_number(highs[index], "high")
            low = _finite_number(lows[index], "low")
            adjusted_close = _finite_number(adjusted[index], "adjusted close") if adjusted else None
            if close is None:
                continue
            observed_at = _iso_timestamp(timestamp)
            bars.append(
                _Bar(
                    timestamp=timestamp,
                    observed_at=observed_at,
                    date=datetime.fromtimestamp(timestamp, exchange_timezone).date().isoformat(),
                    close=close,
                    adjusted_close=adjusted_close,
                    high=high,
                    low=low,
                )
            )
        if not bars:
            raise MarketDataError(
                f"Yahoo Finance returned no usable price observations for {symbol}."
            )
        bars.sort(key=lambda bar: bar.timestamp)

        provider_as_of = None
        market_time = meta.get("regularMarketTime")
        if market_time is not None:
            provider_as_of = _iso_timestamp(_timestamp(market_time))
        return _Chart(
            symbol=symbol,
            period=period_label,
            interval=interval,
            source_url=source_url,
            name=_text(meta.get("longName")) or _text(meta.get("shortName")),
            asset_type=_text(meta.get("instrumentType")),
            currency=_text(meta.get("currency")),
            exchange=_text(meta.get("fullExchangeName")) or _text(meta.get("exchangeName")),
            bars=bars,
            provider_as_of=provider_as_of,
            timezone=timezone_name,
            quote_price=_finite_number(meta.get("regularMarketPrice"), "quote price"),
            day_high=_finite_number(meta.get("regularMarketDayHigh"), "day high"),
            day_low=_finite_number(meta.get("regularMarketDayLow"), "day low"),
        )

    async def _get_json(self, url: str, params: dict[str, str], subject: str) -> Any:
        key = str(httpx.URL(url, params=params))
        cached = self._cache.get(key)
        if cached is not None and time.monotonic() < cached[0]:
            return cached[1]
        try:
            response = await self.client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise MarketDataError(
                f"Yahoo Finance timed out while retrieving {subject}. Try again later."
            ) from exc
        except httpx.RequestError as exc:
            raise MarketDataError(
                f"Yahoo Finance request failed while retrieving {subject}: {exc.__class__.__name__}."
            ) from exc
        if response.status_code == 429:
            raise MarketDataError(
                "Yahoo Finance rate-limited this request (HTTP 429). Try again later."
            )
        if response.status_code == 404:
            raise MarketDataError(
                f"Yahoo Finance could not find {subject} (HTTP 404). Check the symbol or query."
            )
        if not response.is_success:
            raise MarketDataError(
                f"Yahoo Finance returned HTTP {response.status_code} while retrieving {subject}. Try again later."
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise MarketDataError(
                f"Yahoo Finance returned invalid JSON while retrieving {subject}."
            ) from exc
        if key not in self._cache and len(self._cache) >= _CACHE_MAX_ENTRIES:
            del self._cache[min(self._cache, key=lambda entry: self._cache[entry][0])]
        self._cache[key] = (time.monotonic() + _CACHE_TTL_SECONDS, payload)
        return payload

    @staticmethod
    def _performance(bars: list[_Bar], basis: str) -> dict[str, Any]:
        first = bars[0]
        last = bars[-1]
        first_value = first.adjusted_close if basis == "adjusted_close" else first.close
        last_value = last.adjusted_close if basis == "adjusted_close" else last.close
        assert first_value is not None and last_value is not None
        explanation = None
        return_percent = None
        if len(bars) < 2 or first.timestamp == last.timestamp:
            explanation = "Percent return needs at least two distinct price observations."
        elif first_value <= 0:
            explanation = (
                "Percent return is unavailable because the starting price is zero or negative."
            )
        else:
            computed = ((last_value / first_value) - 1) * 100
            if math.isfinite(computed):
                return_percent = computed
            else:
                explanation = "Percent return exceeds the supported numeric range."
        return {
            "return_percent": return_percent,
            "basis": basis,
            "first_observation_date": first.date,
            "last_observation_date": last.date,
            "explanation": explanation,
        }

    @staticmethod
    def _statistics(bars: list[_Bar], basis: str, interval: str) -> dict[str, Any]:
        values = [bar.adjusted_close if basis == "adjusted_close" else bar.close for bar in bars]
        result: dict[str, Any] = {
            "observation_count": len(values),
            "max_drawdown_percent": None,
            "annualized_volatility_percent": None,
            "explanation": None,
        }
        if len(values) < 3 or any(value is None or value <= 0 for value in values):
            result["explanation"] = "Statistics need at least three positive price observations."
            return result
        series = [value for value in values if value is not None]
        peak = series[0]
        drawdown = 0.0
        for value in series:
            peak = max(peak, value)
            drawdown = min(drawdown, (value / peak - 1) * 100)
        log_returns = [math.log(later / earlier) for earlier, later in pairwise(series)]
        periods_per_year = 52 if interval == "1wk" else 252
        result["max_drawdown_percent"] = drawdown
        result["annualized_volatility_percent"] = (
            statistics.stdev(log_returns) * math.sqrt(periods_per_year) * 100
        )
        return result
