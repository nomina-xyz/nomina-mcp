"""US Bureau of Labor Statistics public API v1 (public domain, no key).

v1 allows 25 requests per day per IP address, 25 series and ten years per request. Every
caller therefore shares one request shape - all of Nomina's series together, in ten-year
blocks anchored at the current year - so distinct symbols and windows hit the same cached
responses (six-hour TTL), and a process-wide counter refuses to send more than the daily
allowance instead of exceeding it. Values are monthly.

BLS's API terms of service require users to cite the retrieval date and to state the
disclaimer in TERMS_STATEMENT wherever the data are shown.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from nomina.sources.common import Fetcher, Instrument, MarketDataError, Point

API_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
SOURCE_NAME = "US Bureau of Labor Statistics"
TERMS_STATEMENT = (
    "BLS.gov cannot vouch for the data or analyses derived from these data after the data "
    "have been retrieved from BLS.gov."
)
SERIES_PAGE = "https://data.bls.gov/timeseries/{series_id}"
# Nomina symbol -> (BLS series id, name, unit, measure)
SERIES: dict[str, tuple[str, str, str, str]] = {
    "CPI": (
        "CUSR0000SA0",
        "US CPI-U, all items, seasonally adjusted (index 1982-84=100)",
        "index",
        "percent",
    ),
    "UNRATE": ("LNS14000000", "US unemployment rate, seasonally adjusted", "percent", "points"),
    "PAYEMS": (
        "CES0000000001",
        "US nonfarm payroll employment, seasonally adjusted",
        "thousands",
        "percent",
    ),
    "AHE": (
        "CES0500000003",
        "US average hourly earnings, private, seasonally adjusted",
        "USD",
        "percent",
    ),
}
_MONTHS = {f"M{month:02d}": month for month in range(1, 13)}
_ALL_SERIES_IDS = [entry[0] for entry in SERIES.values()]
_DAILY_LIMIT = 25
_BLOCK_YEARS = 10


def _blocks(start: date, end: date, today: date) -> list[tuple[int, int]]:
    """Ten-year blocks anchored at the current year that overlap [start, end], newest first."""
    blocks: list[tuple[int, int]] = []
    last_year = today.year
    while last_year >= start.year:
        first_year = last_year - _BLOCK_YEARS + 1
        if first_year <= end.year:
            blocks.append((first_year, last_year))
        last_year = first_year - 1
    return blocks


def instrument(symbol: str) -> Instrument:
    series_id, name, unit, measure = SERIES[symbol]
    return Instrument(
        symbol=symbol,
        name=name,
        kind="macro",
        unit=unit,
        measure=measure,  # type: ignore[arg-type]
        source=SOURCE_NAME,
        url=SERIES_PAGE.format(series_id=series_id),
        frequency="monthly",
    )


def resolve(symbol: str) -> str | None:
    key = symbol.strip().upper()
    return key if key in SERIES else None


def search(query: str, limit: int) -> list[str]:
    needle = query.strip().lower()
    if not needle:
        return []
    keywords = {
        "CPI": ("cpi", "inflation", "consumer price"),
        "UNRATE": ("unemployment", "jobless"),
        "PAYEMS": ("payroll", "jobs", "employment", "nonfarm"),
        "AHE": ("wages", "earnings", "hourly"),
    }
    hits = [
        symbol
        for symbol, words in keywords.items()
        if needle in symbol.lower() or any(word in needle or needle in word for word in words)
    ]
    return hits[:limit]


class BLS:
    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher
        self._budget_day: date | None = None
        self._sent_today = 0

    def _spend(self) -> None:
        """Count one network request against the daily allowance; refuse before exceeding it."""
        today = datetime.now(UTC).date()
        if today != self._budget_day:
            self._budget_day, self._sent_today = today, 0
        if self._sent_today >= _DAILY_LIMIT:
            raise MarketDataError(
                "Bureau of Labor Statistics daily request allowance (25 per address) is used up "
                "for this server; it resets daily."
            )
        self._sent_today += 1

    async def series(self, symbol: str, start: date, end: date) -> list[Point]:
        series_id = SERIES[symbol][0]
        points: list[Point] = []
        for first_year, last_year in _blocks(start, end, datetime.now(UTC).date()):
            payload = await self.fetcher.request(
                "POST",
                API_URL,
                json_body={
                    "seriesid": _ALL_SERIES_IDS,
                    "startyear": str(first_year),
                    "endyear": str(last_year),
                },
                subject="Bureau of Labor Statistics API",
                ttl=6 * 3600,
                before_send=self._spend,
            )
            if not isinstance(payload, dict) or payload.get("status") != "REQUEST_SUCCEEDED":
                message = "; ".join(payload.get("message", [])) if isinstance(payload, dict) else ""
                raise MarketDataError(
                    f"Bureau of Labor Statistics API rejected the request. {message}".strip()
                )
            series_list = (payload.get("Results") or {}).get("series") or []
            for item in series_list:
                if item.get("seriesID") != series_id:
                    continue
                for observation in item.get("data") or []:
                    month = _MONTHS.get(observation.get("period", ""))
                    if month is None:
                        continue
                    try:
                        observed = date(int(observation["year"]), month, 1)
                        value = float(observation["value"])
                    except (KeyError, ValueError):
                        continue
                    if start <= observed <= end:
                        points.append(
                            Point(
                                date=observed.isoformat(),
                                observed_at=observed.isoformat(),
                                value=value,
                            )
                        )
        points.sort(key=lambda point: point.date)
        return points
