# Tools

All three tools are read-only, idempotent, and non-destructive; they reach Yahoo Finance's
public endpoints and nothing else. Every response carries `retrieved_at`, `sources` with
provider timestamps, and `caveats` that name the limits of what was returned.

Common parameter types:

- **Query** — text, 1–200 characters after trimming whitespace.
- **Symbol** — a Yahoo Finance symbol, 1–32 characters matching `^[A-Za-z0-9^=._-]+$`
  (for example `AAPL`, `^GSPC`, `BTC-USD`, `EURUSD=X`, `GC=F`). Symbols are upper-cased.
- **period** — one of `1mo`, `3mo`, `6mo`, `1y`, `5y`, `ytd`; default `3mo`. Daily bars,
  or weekly bars for `5y`.

## `search_markets` — Search financial markets

Find ticker symbols and dated news links for a company, asset, sector, or market topic.

| Parameter | Type | Constraints |
|---|---|---|
| `query` | Query | required |
| `limit` | integer | 1–10, default 6; maximum symbols and headlines each |

Response keys: `query`, `retrieved_at`, `sources`, `instruments`, `news`, `caveats`.

## `research_asset` — Research an asset

One symbol with dated prices, period performance, price history, and related news links.

| Parameter | Type | Constraints |
|---|---|---|
| `symbol` | Symbol | required |
| `period` | period | default `3mo` |

Response keys: `symbol`, `period`, `interval`, `retrieved_at`, `sources`, `asset`,
`latest_price`, `period_performance`, `price_history`, `news`, `partial_errors`, `caveats`.

A news failure is reported in `partial_errors` while prices are still returned; a chart
failure is a tool error.

## `compare_assets` — Compare assets

Compare 2–6 distinct symbols over aligned observation dates in their local currencies.

| Parameter | Type | Constraints |
|---|---|---|
| `symbols` | list of Symbol | 2–6 entries, duplicates removed |
| `period` | period | default `3mo` |

Response keys: `symbols`, `period`, `interval`, `retrieved_at`, `assets`, `partial_errors`,
`comparison`, `caveats`.

Returns are computed only over session dates shared by every available asset. Symbols that
fail are listed in `partial_errors` and marked `available: false`; mixed adjusted-close and
raw-close bases are flagged as not comparable rather than blended.

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
