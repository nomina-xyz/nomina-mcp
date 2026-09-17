"""Financial-data boundaries where plausible mistakes change the research conclusion."""

from datetime import UTC, datetime

import httpx
import pytest

from nomina.market import MarketData, MarketDataError


@pytest.fixture
def anyio_backend():
    return "asyncio"


def chart(symbol, closes, *, adjusted=None, dates=None, timezone="America/New_York"):
    if dates is None:
        dates = ["2026-09-14T13:30:00", "2026-09-15T13:30:00"][: len(closes)]
    timestamps = [
        int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp()) for value in dates
    ]
    indicators = {"quote": [{"close": closes, "high": closes, "low": closes}]}
    if adjusted is not None:
        indicators["adjclose"] = [{"adjclose": adjusted}]
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "symbol": symbol,
                        "currency": "USD",
                        "exchangeTimezoneName": timezone,
                        "regularMarketTime": timestamps[-1] + 3600,
                        "regularMarketPrice": 123.45,
                    },
                    "timestamp": timestamps,
                    "indicators": indicators,
                }
            ],
            "error": None,
        }
    }


def provider(charts, *, search_status=200):
    def respond(request):
        if request.url.path.endswith("/search"):
            return httpx.Response(search_status, json={"quotes": [], "news": []})
        symbol = request.url.path.rsplit("/", 1)[-1]
        if symbol not in charts:
            return httpx.Response(404, json={"chart": {"result": None}})
        return httpx.Response(200, json=charts[symbol])

    return httpx.AsyncClient(transport=httpx.MockTransport(respond), follow_redirects=False)


@pytest.mark.anyio
async def test_latest_quote_is_not_the_last_bar_opening_timestamp():
    async with provider({"AAPL": chart("AAPL", [100, 110])}) as client:
        report = await MarketData(client).research("AAPL")
    assert report["latest_price"]["value"] == 123.45
    assert report["latest_price"]["price_timestamp"] == "2026-09-15T14:30:00Z"
    assert report["price_history"][-1]["close"] == 110


@pytest.mark.anyio
async def test_incomplete_adjusted_series_never_mixes_price_bases():
    async with provider({"AAPL": chart("AAPL", [100, 120], adjusted=[50, None])}) as client:
        report = await MarketData(client).research("AAPL")
    assert report["period_performance"]["return_percent"] == pytest.approx(20)
    assert report["period_performance"]["basis"] == "close"


@pytest.mark.anyio
async def test_comparison_aligns_exchange_sessions_not_utc_calendar_days():
    charts = {
        "NZ": chart(
            "NZ",
            [100, 110],
            dates=["2026-09-13T22:00:00", "2026-09-14T22:00:00"],
            timezone="Pacific/Auckland",
        ),
        "US": chart("US", [200, 250]),
    }
    async with provider(charts) as client:
        report = await MarketData(client).compare(["NZ", "US"])
    assert report["comparison"]["common_first_observation_date"] == "2026-09-14"
    assert report["comparison"]["common_last_observation_date"] == "2026-09-15"
    assert [
        asset["common_period_performance"]["return_percent"] for asset in report["assets"]
    ] == pytest.approx([10, 25])


@pytest.mark.anyio
async def test_insufficient_history_cannot_claim_a_flat_return():
    async with provider({"IPO": chart("IPO", [100])}) as client:
        report = await MarketData(client).research("IPO")
    assert report["period_performance"]["return_percent"] is None


@pytest.mark.anyio
async def test_news_failure_retains_prices_but_chart_failure_is_an_error():
    async with provider({"AAPL": chart("AAPL", [100, 110])}, search_status=429) as client:
        data = MarketData(client)
        report = await data.research("AAPL")
        assert report["period_performance"]["return_percent"] == pytest.approx(10)
        assert report["news"] == []
        assert report["partial_errors"][0]["source"] == "Yahoo Finance search"
        with pytest.raises(MarketDataError, match="404"):
            await data.research("MISSING")


@pytest.mark.anyio
async def test_partial_comparison_does_not_invent_missing_asset_returns():
    charts = {"AAPL": chart("AAPL", [100, 110]), "SPY": chart("SPY", [200, 230])}
    async with provider(charts) as client:
        report = await MarketData(client).compare(["AAPL", "MISSING", "SPY"])
    assert report["assets"][1]["available"] is False
    assert [item["symbol"] for item in report["partial_errors"]] == ["MISSING"]
    assert report["assets"][0]["common_period_performance"]["return_percent"] == pytest.approx(10)
    assert report["assets"][2]["common_period_performance"]["return_percent"] == pytest.approx(15)


@pytest.mark.anyio
async def test_mixed_adjustment_bases_are_not_declared_comparable():
    charts = {
        "SPLIT": chart("SPLIT", [100, 60], adjusted=[50, 60]),
        "RAW": chart("RAW", [100, 120]),
    }
    async with provider(charts) as client:
        report = await MarketData(client).compare(["SPLIT", "RAW"])
    assert report["comparison"]["returns_comparable"] is False


@pytest.mark.anyio
async def test_negative_starting_prices_do_not_produce_misleading_percent_returns():
    async with provider({"FUTURE": chart("FUTURE", [-10, 20])}) as client:
        report = await MarketData(client).research("FUTURE")
    assert report["period_performance"]["return_percent"] is None
    assert report["price_history"][0]["close"] == -10
