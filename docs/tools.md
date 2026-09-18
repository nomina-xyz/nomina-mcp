# Tools

All four tools are read-only, idempotent, and non-destructive; they reach Yahoo Finance's
public endpoints and nothing else. Every response carries `retrieved_at`, `sources` with
provider timestamps, and `caveats` that name the limits of what was returned. Identical
provider requests within 60 seconds are served from a short in-process cache; `retrieved_at`
is still the time of the call.

Common parameter types:

- **Query** — text, 1–200 characters after trimming whitespace.
- **Symbol** — a Yahoo Finance symbol, 1–32 characters matching `^[A-Za-z0-9^=._-]+$`
  (for example `AAPL`, `^GSPC`, `BTC-USD`, `EURUSD=X`, `GC=F`). Symbols are upper-cased.
- **period** — one of `1mo`, `3mo`, `6mo`, `1y`, `5y`, `ytd`; default `3mo`. Daily bars,
  or weekly bars for `5y`.
- **start / end** — ISO dates (`YYYY-MM-DD`), both inclusive, always given together. They
  replace `period` with an exact window: `end` must be after `start`, not in the future,
  and at most 25 years later. Windows up to two years use daily bars, longer ones weekly.
  The response reports `period` as `start..end`.

## `search_markets` — Search financial markets

Find ticker symbols and dated news links for a company, asset, sector, or market topic.

| Parameter | Type | Constraints |
|---|---|---|
| `query` | Query | required |
| `limit` | integer | 1–10, default 6; maximum symbols and headlines each |

Response keys: `query`, `retrieved_at`, `sources`, `instruments`, `news`, `caveats`.

## `research_asset` — Research an asset

One symbol with dated prices, period performance, risk statistics, price history, and
related news links.

| Parameter | Type | Constraints |
|---|---|---|
| `symbol` | Symbol | required |
| `period` | period | default `3mo`; ignored when `start` and `end` are given |
| `start`, `end` | start / end | optional, both or neither |

Response keys: `symbol`, `period`, `interval`, `retrieved_at`, `sources`, `asset`,
`latest_price`, `period_performance`, `statistics`, `price_history`, `news`,
`partial_errors`, `caveats`.

`statistics` holds `observation_count`, `max_drawdown_percent` (largest peak-to-trough
decline in the returned series), `annualized_volatility_percent` (sample standard deviation
of log returns, scaled by √252 for daily or √52 for weekly bars), and `explanation`. Both
figures are `null` with an explanation when the series has fewer than three positive
observations. They describe the returned series only; they are not forecasts.

A news failure is reported in `partial_errors` while prices are still returned; a chart
failure is a tool error.

## `compare_assets` — Compare assets

Compare 2–6 distinct symbols over aligned observation dates in their local currencies.

| Parameter | Type | Constraints |
|---|---|---|
| `symbols` | list of Symbol | 2–6 entries, duplicates removed |
| `period` | period | default `3mo`; ignored when `start` and `end` are given |
| `start`, `end` | start / end | optional, both or neither |

Response keys: `symbols`, `period`, `interval`, `retrieved_at`, `assets`, `partial_errors`,
`comparison`, `caveats`.

Returns are computed only over session dates shared by every available asset. Symbols that
fail are listed in `partial_errors` and marked `available: false`; mixed adjusted-close and
raw-close bases are flagged as not comparable rather than blended.

## `market_overview` — Market overview

Period returns for a fixed basket: `^GSPC`, `^IXIC`, `^DJI`, `^RUT`, `^VIX`, `^TNX`,
`DX-Y.NYB`, `GC=F`, `CL=F`, `BTC-USD`, `ETH-USD`, `EURUSD=X`. The basket is chosen by
Nomina; it is not a provider index.

| Parameter | Type | Constraints |
|---|---|---|
| `period` | period | default `1mo` |

Response keys: `period`, `interval`, `retrieved_at`, `assets`, `partial_errors`, `caveats`.
Each asset carries `symbol`, `available`, `name`, `asset_type`, `currency`, `latest_price`,
`period_performance`, and `source`, or `available: false` with an `error`. The tool fails
only when every basket member fails.

## What it is not

- Unofficial public endpoints may be delayed, incomplete, unavailable, or rate limited.
- No real-time data guarantee; always use the provider's quote and observation timestamps.
- Headlines and links only, not full articles or an exhaustive news search.
- No financial statements, analyst estimates, order execution, or account access.
- Adjusted closes are provider-defined; do not assume an audited total-return series.
- Returns exclude investor-specific fees, taxes and currency conversion.
- Short or unavailable histories and partial comparisons are explicitly identified.

## Resource and prompt

- **Resource `nomina://sources`** (`application/json`) — provider, coverage, the limitations
  above, the privacy statement, and links to the [privacy policy](../privacy/), this
  documentation, Yahoo's privacy policy and terms of use.
- **Prompt `research_brief`** (`topic`: Query) — starts a concise, source-backed research
  brief that cites links and observation dates and separates facts from interpretation.
