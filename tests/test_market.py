"""Data boundaries where plausible mistakes change the research conclusion (v2 sources)."""

import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from nomina.market import OVERVIEW_SYMBOLS, MarketData, MarketDataError
from nomina.sources import bls
from nomina.sources import chainlink as cl

PHASE = 3
DAY = 86400


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _ts(day: date, hour: int = 23) -> int:
    return int(datetime(day.year, day.month, day.day, hour, 30, tzinfo=UTC).timestamp())


class FakeFeed:
    """One Chainlink feed with one round per calendar day (or per given timestamps)."""

    def __init__(self, proxy, decimals, rounds):
        self.proxy = proxy.lower()
        self.decimals = decimals
        self.rounds = rounds  # list of (updated_at, answer) in chronological order

    def call(self, data: str) -> str | None:
        selector = data[:10]
        if selector == cl._SELECTOR["decimals"]:
            return "0x" + hex(self.decimals)[2:].rjust(64, "0")
        if selector == cl._SELECTOR["latestRoundData"]:
            return self._round(len(self.rounds))
        if selector == cl._SELECTOR["getRoundData"]:
            rid = int(data[10:], 16)
            phase, agg = rid >> 64, rid & ((1 << 64) - 1)
            if phase != PHASE or not 1 <= agg <= len(self.rounds):
                return None
            return self._round(agg)
        if selector == cl._SELECTOR["phaseAggregators"]:
            return None
        return None

    def _round(self, agg: int) -> str:
        updated_at, answer = self.rounds[agg - 1]
        rid = (PHASE << 64) | agg
        raw = round(answer * 10**self.decimals)
        words = [rid, raw % (1 << 256), updated_at, updated_at, rid]
        return "0x" + "".join(hex(w)[2:].rjust(64, "0") for w in words)


def directory(*feeds):
    return [
        {
            "name": name,
            "assetName": asset,
            "path": path,
            "proxyAddress": proxy,
            "decimals": 8,
            "feedType": feed_type,
            "feedCategory": "low",
            "heartbeat": 3600,
            "docs": {"productType": "Price"},
        }
        for name, asset, path, proxy, feed_type in feeds
    ]


def daily_rounds(start: date, values: list[float]):
    return [(_ts(start + timedelta(days=i)), value) for i, value in enumerate(values)]


def treasury_csv(rows: list[tuple[date, float]]) -> str:
    header = 'Date,"1 Mo","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"'
    body = "\n".join(
        f"{d.strftime('%m/%d/%Y')},4.0,4.0,4.0,4.0,4.0,4.0,4.0,4.0,4.0,4.0,{v},4.0,4.0"
        for d, v in rows
    )
    return header + "\n" + body + "\n"


def provider(
    *,
    feeds=(),
    directory_entries=None,
    treasury_rows=None,
    bls=None,
    gdelt_status=200,
    requests=None,
):
    fake_feeds = {f.proxy: f for f in feeds}

    def respond(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        host = request.url.host
        if host == "reference-data-directory.vercel.app":
            return httpx.Response(200, json=directory_entries or [])
        if host in {
            "ethereum.publicnode.com",
            "ethereum-rpc.publicnode.com",
            "eth.drpc.org",
            "rpc.flashbots.net",
        }:
            batch = json.loads(request.content)
            out = []
            for call in batch:
                to = call["params"][0]["to"].lower()
                result = (
                    fake_feeds[to].call(call["params"][0]["data"]) if to in fake_feeds else None
                )
                out.append(
                    {"jsonrpc": "2.0", "id": call["id"], "result": result}
                    if result
                    else {
                        "jsonrpc": "2.0",
                        "id": call["id"],
                        "error": {"code": 3, "message": "execution reverted"},
                    }
                )
            return httpx.Response(200, json=out)
        if host == "home.treasury.gov":
            return httpx.Response(
                200, text=treasury_csv(treasury_rows or []), headers={"content-type": "text/csv"}
            )
        if host == "api.bls.gov":
            return httpx.Response(
                200, json=bls or {"status": "REQUEST_SUCCEEDED", "Results": {"series": []}}
            )
        if host == "api.gdeltproject.org":
            if gdelt_status != 200:
                return httpx.Response(gdelt_status, text="Please limit requests")
            return httpx.Response(
                200,
                json={
                    "articles": [
                        {
                            "url": "https://news.example/a",
                            "title": "Headline A",
                            "domain": "news.example",
                            "seendate": "20260920T120000Z",
                        }
                    ]
                },
            )
        if host == "www.sec.gov":
            return httpx.Response(
                200, json={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
            )
        if host == "data.sec.gov":
            if "companyfacts" in request.url.path:
                return httpx.Response(200, json=COMPANY_FACTS)
            return httpx.Response(
                200,
                json={
                    "filings": {
                        "recent": {
                            "form": ["10-Q", "4"],
                            "filingDate": ["2026-07-31", "2026-08-01"],
                            "accessionNumber": ["0000320193-26-000020", "0000320193-26-000021"],
                            "primaryDocument": ["aapl-20260627.htm", "x.xml"],
                        }
                    }
                },
            )
        return httpx.Response(404, json={"error": "unexpected host " + host})

    return httpx.AsyncClient(transport=httpx.MockTransport(respond), follow_redirects=False)


COMPANY_FACTS = {
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {
                            "val": 265_595_000_000,
                            "start": "2017-10-01",
                            "end": "2018-09-29",
                            "fy": 2018,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2018-11-05",
                        },
                    ]
                }
            },
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {
                    "USD": [
                        {
                            "val": 416_161_000_000,
                            "start": "2024-09-29",
                            "end": "2025-09-27",
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2025-10-31",
                        },
                        {
                            "val": 109_417_000_000,
                            "start": "2026-03-29",
                            "end": "2026-06-27",
                            "fy": 2026,
                            "fp": "Q3",
                            "form": "10-Q",
                            "filed": "2026-07-31",
                        },
                        {
                            "val": 300_000_000_000,
                            "start": "2025-09-28",
                            "end": "2026-06-27",
                            "fy": 2026,
                            "fp": "Q3",
                            "form": "10-Q",
                            "filed": "2026-07-31",
                        },
                    ]
                }
            },
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        {
                            "val": 112_010_000_000,
                            "start": "2024-09-29",
                            "end": "2025-09-27",
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2025-10-31",
                        },
                    ]
                }
            },
        }
    }
}

BTC = "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c"
ETH = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
SPY = "0x25efbA0d9b115D233cfA849F16BA743E8FFba2a1"
DIRECTORY = directory(
    ("BTC / USD", "Bitcoin", "btc-usd", BTC, "Crypto"),
    ("ETH / USD", "Ethereum", "eth-usd", ETH, "Crypto"),
    ("SPY-USD (24/5)", "SPDR S&P 500 ETF", "spy-usd-kalman-24-5", SPY, "Equities"),
) + [
    {
        "name": "BTC / USD",
        "assetName": "Bitcoin",
        "path": "btc-usd-svr",
        "proxyAddress": "0x8adE2c8d55F7ee2C9234ad868D44a60Eb9C07f8c",
        "decimals": 8,
        "feedType": "Crypto",
        "feedCategory": "low",
        "heartbeat": 3600,
        "docs": {"productType": "Price"},
    },
    {
        "name": "DAI / USD",
        "assetName": "Dai",
        "path": "dai-usd",
        "proxyAddress": "0x0000000000000000000000000000000000000d01",
        "decimals": 8,
        "feedType": "Crypto",
        "feedCategory": "deprecating",
        "heartbeat": 3600,
        "docs": {"productType": "Price"},
    },
]


def window(days: int) -> tuple[date, date]:
    end = datetime.now(UTC).date() - timedelta(days=1)
    return end - timedelta(days=days - 1), end


@pytest.mark.anyio
async def test_daily_close_is_the_last_round_before_midnight_utc_not_the_first():
    start, end = window(3)
    # two rounds per day: a morning value and an evening value; the evening one must win
    rounds = []
    for i, (morning, evening) in enumerate([(100, 110), (120, 130), (140, 150)]):
        day = start + timedelta(days=i)
        rounds += [(_ts(day, 9), morning), (_ts(day, 21), evening)]
    async with provider(feeds=[FakeFeed(BTC, 8, rounds)], directory_entries=DIRECTORY) as client:
        report = await MarketData(client).research("btc-usd", start=start, end=end)
    assert [p["value"] for p in report["history"]] == [110, 130, 150]
    assert report["period_performance"]["return_percent"] == pytest.approx((150 / 110 - 1) * 100)
    assert report["symbol"] == "BTC/USD"


@pytest.mark.anyio
async def test_equity_feed_does_not_repeat_fridays_close_over_the_weekend():
    # Friday..Monday window; feed updates Friday and Monday only
    monday = datetime.now(UTC).date() - timedelta(days=1)
    while monday.weekday() != 0:
        monday -= timedelta(days=1)
    friday = monday - timedelta(days=3)
    rounds = [(_ts(friday, 21), 500.0), (_ts(monday, 21), 505.0)]
    async with provider(feeds=[FakeFeed(SPY, 8, rounds)], directory_entries=DIRECTORY) as client:
        report = await MarketData(client).research("SPY", start=friday, end=monday)
    assert [p["date"] for p in report["history"]] == [friday.isoformat(), monday.isoformat()]


@pytest.mark.anyio
async def test_svr_and_deprecating_feeds_are_excluded_from_the_catalog():
    async with provider(directory_entries=DIRECTORY) as client:
        data = MarketData(client)
        catalog = await data.chainlink.catalog()
        assert set(catalog) == {"BTC/USD", "ETH/USD", "SPY/USD"}
        assert catalog["BTC/USD"].proxy == BTC
        with pytest.raises(MarketDataError, match="Unknown symbol"):
            await data.research("DAI/USD")


@pytest.mark.anyio
async def test_yields_change_in_points_and_carry_no_return_percent():
    start, end = window(5)
    rows = [(start + timedelta(days=i), v) for i, v in enumerate([4.00, 4.10, 4.05, 4.30, 4.25])]
    async with provider(treasury_rows=rows) as client:
        report = await MarketData(client).research("US10Y", start=start, end=end)
    perf = report["period_performance"]
    assert perf["measure"] == "points"
    assert perf["return_percent"] is None
    assert perf["change"] == pytest.approx(0.25)
    assert report["statistics"]["max_drawdown_percent"] is None


@pytest.mark.anyio
async def test_comparison_of_a_price_and_a_yield_is_flagged_not_comparable():
    start, end = window(3)
    rounds = daily_rounds(start, [100, 105, 110])
    rows = [(start + timedelta(days=i), v) for i, v in enumerate([4.0, 4.1, 4.2])]
    async with provider(
        feeds=[FakeFeed(BTC, 8, rounds)], directory_entries=DIRECTORY, treasury_rows=rows
    ) as client:
        report = await MarketData(client).compare(["BTC/USD", "US10Y"], start=start, end=end)
    assert report["comparison"]["common_observation_count"] == 3
    assert report["comparison"]["returns_comparable"] is False
    assert (
        "percentage points" in report["comparison"]["note"]
        or "point changes" in report["comparison"]["note"]
    )


@pytest.mark.anyio
async def test_partial_comparison_keeps_available_series_and_names_the_failure():
    start, end = window(3)
    async with provider(
        feeds=[
            FakeFeed(BTC, 8, daily_rounds(start, [100, 110, 120])),
            FakeFeed(ETH, 8, daily_rounds(start, [10, 11, 12])),
        ],
        directory_entries=DIRECTORY,
    ) as client:
        report = await MarketData(client).compare(
            ["BTC/USD", "NOPE/USD", "ETH/USD"], start=start, end=end
        )
    assert [e["symbol"] for e in report["partial_errors"]] == ["NOPE/USD"]
    assert report["assets"][1]["available"] is False
    assert report["assets"][0]["common_period_performance"]["return_percent"] == pytest.approx(20)
    assert report["assets"][2]["common_period_performance"]["return_percent"] == pytest.approx(20)
    assert report["comparison"]["returns_comparable"] is True


@pytest.mark.anyio
async def test_overview_reports_failed_basket_members_without_dropping_the_rest():
    start, _end = window(30)
    async with provider(
        feeds=[FakeFeed(BTC, 8, daily_rounds(start, [100.0] * 30))], directory_entries=DIRECTORY
    ) as client:
        report = await MarketData(client).overview("1mo")
    symbols = [a["symbol"] for a in report["assets"]]
    assert symbols == list(OVERVIEW_SYMBOLS)
    available = {a["symbol"] for a in report["assets"] if a["available"]}
    assert "BTC/USD" in available
    assert "XAU/USD" in {e["symbol"] for e in report["partial_errors"]}


@pytest.mark.anyio
async def test_news_failure_is_partial_but_series_failure_is_an_error():
    start, end = window(3)
    async with provider(
        feeds=[FakeFeed(BTC, 8, daily_rounds(start, [1, 2, 3]))],
        directory_entries=DIRECTORY,
        gdelt_status=429,
    ) as client:
        data = MarketData(client)
        report = await data.research("BTC", start=start, end=end)
        assert report["news"] == []
        assert report["partial_errors"][0]["source"] == "GDELT article search"
        with pytest.raises(MarketDataError, match="Unknown symbol"):
            await data.research("MISSING")


@pytest.mark.anyio
async def test_fundamentals_take_the_latest_period_across_candidate_concepts_and_reject_ytd_spans():
    async with provider() as client:
        report = await MarketData(client).fundamentals("aapl")
    assert report["latest_annual"]["revenue"]["value"] == 416_161_000_000
    assert report["latest_annual"]["revenue"]["fiscal_year"] == 2025
    # the 9-month year-to-date figure (2025-09-28..2026-06-27) must not be reported as a quarter
    assert report["latest_quarterly"]["revenue"]["value"] == 109_417_000_000
    assert report["recent_filings"] == [
        {
            "form": "10-Q",
            "filed": "2026-07-31",
            "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/aapl-20260627.htm",
        }
    ]


@pytest.mark.anyio
async def test_drawdown_uses_running_peak_and_volatility_uses_sample_stdev():
    start, end = window(4)
    async with provider(
        feeds=[FakeFeed(BTC, 8, daily_rounds(start, [100, 120, 90, 110]))],
        directory_entries=DIRECTORY,
    ) as client:
        report = await MarketData(client).research("BTC/USD", start=start, end=end)
    assert report["statistics"]["max_drawdown_percent"] == pytest.approx(-25.0)
    assert report["statistics"]["annualized_volatility_percent"] == pytest.approx(
        439.4155, abs=1e-3
    )


@pytest.mark.anyio
async def test_one_sided_window_is_rejected_before_any_request():
    requests = []
    async with provider(requests=requests) as client:
        with pytest.raises(MarketDataError) as excinfo:
            await MarketData(client).research("BTC/USD", start=date(2024, 1, 2))
    assert str(excinfo.value) == "Provide both start and end dates, or neither."
    assert requests == []


@pytest.mark.anyio
async def test_resolved_rounds_are_reused_across_calls():
    start, end = window(3)
    requests = []
    async with provider(
        feeds=[FakeFeed(BTC, 8, daily_rounds(start, [1, 2, 3]))],
        directory_entries=DIRECTORY,
        requests=requests,
    ) as client:
        data = MarketData(client)
        await data.research("BTC", start=start, end=end)
        rpc_calls_first = sum(1 for r in requests if r.url.host.endswith("publicnode.com"))
        await data.research("BTC", start=start, end=end)
        rpc_calls_second = (
            sum(1 for r in requests if r.url.host.endswith("publicnode.com")) - rpc_calls_first
        )
    assert rpc_calls_first >= 2
    assert rpc_calls_second == 1  # only the latest-round lookup repeats


def bls_payload(series: dict[str, list[float]]) -> dict:
    """One BLS v1 response holding the last len(values) months of each series, newest first."""
    today = datetime.now(UTC).date()
    out = []
    for series_id, values in series.items():
        data, year, month = [], today.year, today.month
        for value in values:
            data.append({"year": str(year), "period": f"M{month:02d}", "value": str(value)})
            year, month = (year, month - 1) if month > 1 else (year - 1, 12)
        out.append({"seriesID": series_id, "data": data})
    return {"status": "REQUEST_SUCCEEDED", "Results": {"series": out}}


@pytest.mark.anyio
async def test_bls_symbols_and_windows_share_one_request_and_keep_their_own_values():
    requests = []
    payload = bls_payload({"CUSR0000SA0": [334.9, 334.1, 333.0], "LNS14000000": [4.3, 4.2, 4.1]})
    async with provider(bls=payload, requests=requests) as client:
        data = MarketData(client)
        cpi = await data.research("CPI", "1y")
        unrate = await data.research("UNRATE", "3mo")
        overview = await data.overview("6mo")
    assert sum(1 for r in requests if r.url.host == "api.bls.gov") == 1
    assert [p["value"] for p in cpi["history"]] == [333.0, 334.1, 334.9]
    assert [p["value"] for p in unrate["history"]] == [4.1, 4.2, 4.3]
    assert all(bls.TERMS_STATEMENT in report["caveats"] for report in (cpi, unrate, overview))


@pytest.mark.anyio
async def test_bls_daily_allowance_is_refused_before_it_is_exceeded(monkeypatch):
    monkeypatch.setattr(bls, "_DAILY_LIMIT", 1)
    requests = []
    end = datetime.now(UTC).date()
    start = end - timedelta(days=11 * 365)  # spans two ten-year blocks
    async with provider(
        bls=bls_payload({"CUSR0000SA0": [300.0, 299.0]}), requests=requests
    ) as client:
        with pytest.raises(MarketDataError, match="allowance"):
            await MarketData(client).research("CPI", start=start, end=end)
    assert sum(1 for r in requests if r.url.host == "api.bls.gov") == 1
