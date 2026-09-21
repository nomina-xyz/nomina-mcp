# Tools

All five tools are read-only, idempotent, and non-destructive. They reach only the public
sources listed on [Data sources and limits](../data-sources/). Every response carries
`retrieved_at`, `sources` with observation timestamps, and `caveats` naming the limits of what
was returned. Identical upstream requests are served from a short in-process cache; on-chain
rounds, once resolved, are cached for the life of the process.

## Symbols

| Class | Examples | Source | Frequency |
|---|---|---|---|
| Crypto | `BTC/USD`, `ETH/USD`, `SOL/USD`, `LINK/USD` (also `BTC`, `btc-usd`, `BTCUSD`) | Chainlink feed on Ethereum | daily (weekly beyond 2 years) |
| FX | `EUR/USD`, `GBP/USD`, `JPY/USD`, `CHF/USD`, `AUD/USD`, `CAD/USD` | Chainlink feed | trading days |
| Metals | `XAU/USD` (gold), `XAG/USD` (silver) | Chainlink feed | trading days |
| Equities/ETFs | `SPY/USD`, `QQQ/USD`, `NVDA/USD`, `TSLA/USD`, `GOOGL/USD` | Chainlink feed | trading days |
| US Treasury yields | `US1M` … `US6M`, `US1Y`, `US2Y`, `US3Y`, `US5Y`, `US7Y`, `US10Y`, `US20Y`, `US30Y` | US Treasury | trading days |
| US macro | `CPI`, `UNRATE`, `PAYEMS`, `AHE` | BLS | monthly |
| Companies | any US-listed ticker, e.g. `AAPL` | SEC EDGAR | per filing |

Use `search_markets` to discover feeds; the on-chain catalog is loaded from Chainlink's public
feed directory at runtime (about 140 price feeds).

Common parameters: **period** is one of `1mo`, `3mo`, `6mo`, `1y`, `5y`, `ytd` (default
`3mo`); **start / end** are inclusive ISO dates that replace `period` (both required, `end`
not in the future, at most 25 years).

## `search_markets` — Search markets catalog

| Parameter | Constraints |
|---|---|
| `query` | text, 1–200 characters |
| `limit` | 1–10, default 6 |

Response keys: `query`, `retrieved_at`, `sources`, `instruments`, `news`, `partial_errors`,
`caveats`. Each instrument names the tool(s) that accept it.

## `research_asset` — Research an asset

| Parameter | Constraints |
|---|---|
| `symbol` | see the symbol table |
| `period` | default `3mo`; ignored when `start`/`end` given |
| `start`, `end` | optional, both or neither |

Response keys: `symbol`, `period`, `interval`, `retrieved_at`, `sources`, `asset`, `latest`,
`period_performance`, `statistics`, `history`, `news`, `partial_errors`, `caveats`.

`period_performance.measure` is `percent` for prices (with `return_percent`) or `points` for
yields and rates (with `change` in percentage points). `statistics` (max drawdown, annualized
volatility from sample standard deviation of log returns, √252 daily / √52 weekly / √12
monthly) applies to prices only. A headline failure is reported in `partial_errors` while the
series is still returned; a series failure is a tool error.

## `compare_assets` — Compare assets

| Parameter | Constraints |
|---|---|
| `symbols` | 2–6 entries, duplicates removed |
| `period`, `start`, `end` | as above |

Response keys: `symbols`, `period`, `interval`, `retrieved_at`, `assets`, `partial_errors`,
`comparison`, `caveats`. Changes are computed over dates shared by every retrieved series.
Selections that mix prices with yields or indexes are flagged `returns_comparable: false`.

## `market_overview` — Market overview

`period` default `1mo`. Basket: `BTC/USD`, `ETH/USD`, `SOL/USD`, `XAU/USD`, `SPY/USD`,
`QQQ/USD`, `EUR/USD`, `US2Y`, `US10Y`, `CPI`. Members that fail are listed in
`partial_errors`; the tool fails only when every member fails.

## `company_fundamentals` — Company fundamentals

| Parameter | Constraints |
|---|---|
| `ticker` | US-listed ticker of an SEC registrant |

Response keys: `ticker`, `name`, `cik`, `source`, `latest_annual`, `latest_quarterly`,
`recent_filings`, `retrieved_at`, `caveats`. Figures: revenue, net income, operating income,
diluted EPS, total assets, total liabilities, stockholders' equity, cash, operating cash flow —
each with `value`, `unit`, `period_start`, `period_end`, `fiscal_year`, `fiscal_period`,
`form`, `filed`. Annual figures come from 10-K filings, quarterly from 10-Q filings; the
latest period wins across the XBRL concepts a filer may use.

## What it is not

- No individual stock prices beyond the equities with on-chain feeds.
- Oracle prices are aggregates updating on heartbeat or deviation; a day's close is the last
  on-chain update before midnight UTC and can lag exchange closes.
- On-chain history begins when a feed launched; earlier dates are reported as unavailable.
- Headlines are GDELT records (title and link), not article text; GDELT throttles to one
  request per five seconds.
- Macro series are monthly and revised by the agency.
- Returns exclude fees, taxes and currency conversion; yields change in percentage points.

## Resource and prompt

- **Resource `nomina://sources`** (`application/json`) — every source with coverage, access
  terms and URL, the limitations above, the privacy statement, and citations.
- **Prompt `research_brief`** (`topic`) — starts a concise, source-backed research brief that
  cites links and observation dates and separates facts from interpretation.
