"""US Treasury daily par yield curve rates (public domain, no key)."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime

from nomina.sources.common import Fetcher, Instrument, MarketDataError, Point

CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
)
PAGE_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "TextView?type=daily_treasury_yield_curve&field_tdr_date_value={year}"
)
# Nomina symbol -> CSV column header
TENORS: dict[str, str] = {
    "US1M": "1 Mo",
    "US2M": "2 Mo",
    "US3M": "3 Mo",
    "US4M": "4 Mo",
    "US6M": "6 Mo",
    "US1Y": "1 Yr",
    "US2Y": "2 Yr",
    "US3Y": "3 Yr",
    "US5Y": "5 Yr",
    "US7Y": "7 Yr",
    "US10Y": "10 Yr",
    "US20Y": "20 Yr",
    "US30Y": "30 Yr",
}
_NAMES = {
    "US1M": "US Treasury 1-month yield",
    "US2M": "US Treasury 2-month yield",
    "US3M": "US Treasury 3-month yield",
    "US4M": "US Treasury 4-month yield",
    "US6M": "US Treasury 6-month yield",
    "US1Y": "US Treasury 1-year yield",
    "US2Y": "US Treasury 2-year yield",
    "US3Y": "US Treasury 3-year yield",
    "US5Y": "US Treasury 5-year yield",
    "US7Y": "US Treasury 7-year yield",
    "US10Y": "US Treasury 10-year yield",
    "US20Y": "US Treasury 20-year yield",
    "US30Y": "US Treasury 30-year yield",
}


def instrument(symbol: str) -> Instrument:
    return Instrument(
        symbol=symbol,
        name=_NAMES[symbol],
        kind="yield",
        unit="percent",
        measure="points",
        source="US Department of the Treasury (daily par yield curve)",
        url=PAGE_URL.format(year=datetime.now(UTC).year),
    )


def resolve(symbol: str) -> str | None:
    key = symbol.strip().upper().replace("-", "").replace("_", "")
    return key if key in TENORS else None


def search(query: str, limit: int) -> list[str]:
    needle = query.strip().lower()
    if not needle:
        return []
    hits = [
        symbol
        for symbol, name in _NAMES.items()
        if needle in name.lower()
        or needle in symbol.lower()
        or needle in ("yield", "yields", "rates", "treasury", "treasuries")
    ]
    return hits[:limit]


class Treasury:
    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher

    async def _year(self, year: int) -> list[dict[str, str]]:
        text = await self.fetcher.request(
            "GET",
            CSV_URL.format(year=year),
            params={
                "type": "daily_treasury_yield_curve",
                "field_tdr_date_value": str(year),
                "page": "",
                "_format": "csv",
            },
            subject="US Treasury yield curve",
            ttl=3600,
            as_text=True,
            timeout=45.0,
        )
        rows = list(csv.DictReader(io.StringIO(text)))
        if rows and "Date" not in rows[0]:
            raise MarketDataError("US Treasury yield curve CSV has an unexpected layout.")
        return rows

    async def series(self, symbol: str, start: date, end: date) -> list[Point]:
        column = TENORS[symbol]
        points: list[Point] = []
        for year in range(start.year, end.year + 1):
            for row in await self._year(year):
                try:
                    observed = datetime.strptime(row["Date"], "%m/%d/%Y").replace(tzinfo=UTC).date()
                except (KeyError, ValueError):
                    continue
                if not start <= observed <= end:
                    continue
                raw = (row.get(column) or "").strip()
                if not raw or raw == "N/A":
                    continue
                try:
                    value = float(raw)
                except ValueError:
                    continue
                points.append(
                    Point(date=observed.isoformat(), observed_at=observed.isoformat(), value=value)
                )
        points.sort(key=lambda point: point.date)
        return points

    def source_url(self, start: date) -> str:
        return PAGE_URL.format(year=start.year)
