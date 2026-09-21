"""US Bureau of Labor Statistics public API v1 (public domain, no key).

v1 allows 25 requests per day per IP and ten years per request, so results are cached for six
hours and every series in one request. Values are monthly.

BLS's API terms of service require users to cite the retrieval date and to state the
disclaimer in TERMS_STATEMENT wherever the data are shown.
"""

from __future__ import annotations

from datetime import date

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

    async def series(self, symbol: str, start: date, end: date) -> list[Point]:
        series_id = SERIES[symbol][0]
        points: list[Point] = []
        # v1 caps each request at ten years; walk the window in ten-year slices.
        first_year = start.year
        while first_year <= end.year:
            last_year = min(first_year + 9, end.year)
            payload = await self.fetcher.request(
                "POST",
                API_URL,
                json_body={
                    "seriesid": [series_id],
                    "startyear": str(first_year),
                    "endyear": str(last_year),
                },
                subject="Bureau of Labor Statistics API",
                ttl=6 * 3600,
            )
            if not isinstance(payload, dict) or payload.get("status") != "REQUEST_SUCCEEDED":
                message = "; ".join(payload.get("message", [])) if isinstance(payload, dict) else ""
                raise MarketDataError(
                    f"Bureau of Labor Statistics API rejected the request. {message}".strip()
                )
            series_list = (payload.get("Results") or {}).get("series") or []
            for item in series_list:
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
            first_year = last_year + 1
        points.sort(key=lambda point: point.date)
        return points
