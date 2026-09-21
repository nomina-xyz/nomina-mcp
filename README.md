# Nomina

Markets research for agents from public data.

Five read-only tools, no API key, no account, no trading access:

- **`search_markets`** — find symbols in Nomina's catalog (on-chain price feeds, Treasury
  tenors, macro series, SEC registrants) and recent headlines.
- **`research_asset`** — latest value, period change, drawdown and volatility, dated history,
  and headlines for one symbol, over a named period or an exact date window.
- **`compare_assets`** — align 2–6 symbols on shared observation dates, each in its own unit.
- **`market_overview`** — period changes for BTC, ETH, SOL, gold, SPY, QQQ, EUR/USD, US 2y
  and 10y yields and CPI.
- **`company_fundamentals`** — latest annual and quarterly financials and filings for an SEC
  registrant.

Data: Chainlink price feeds read from the Ethereum blockchain (crypto, FX, gold and silver, a
few US equities/ETFs), the US Treasury yield curve, Bureau of Labor Statistics series, SEC
EDGAR filings, and GDELT headlines: public-domain government statistics, public blockchain
state, and openly released news records, each source's obligations documented and met in
[Data sources and limits](https://nomina-xyz.github.io/nomina-mcp/data-sources/).

## Install

**Hosted (no install):** add `https://nomina-mcp.onrender.com/mcp` as a custom connector in
Claude (Settings → Connectors → Add custom connector), or
`claude mcp add --transport http nomina https://nomina-mcp.onrender.com/mcp`. First request
after an idle period can take about a minute.

**Claude Desktop:** Settings → Extensions → Advanced settings → Extension Developer →
Install Extension… → select `Nomina.mcpb` from a
[release](https://github.com/nomina-xyz/nomina-mcp/releases) (or build it yourself, see below). Requires a Claude Desktop
release with MCPB v0.4 UV-runtime support and internet access on first install.

**Any other MCP client (Claude Code, etc.):** point it at this as a local stdio server:

```json
{
  "mcpServers": {
    "nomina": {
      "command": "uv",
      "args": ["run", "--frozen", "--no-dev", "--directory", "/path/to/nomp", "server.py"]
    }
  }
}
```

**Self-hosted (Streamable HTTP):** `docker run --rm -p 8000:8000 ghcr.io/nomina-xyz/nomina-mcp:2.0.1`,
then connect to `http://localhost:8000/mcp`. Details in the docs below.

## Docs

Install guides, tool reference, privacy policy, and data-source limits:
https://nomina-xyz.github.io/nomina-mcp/ — see especially
[Data sources and limits](https://nomina-xyz.github.io/nomina-mcp/data-sources/).

## Privacy Policy

Full policy: https://nomina-xyz.github.io/nomina-mcp/privacy/

- **Collection:** when a tool runs, only its inputs — search terms, symbols, tickers, and the
  requested period or date window — are sent to the public sources that answer it: Ethereum
  JSON-RPC gateways (`ethereum.publicnode.com`, `rpc.mevblocker.io`) and Chainlink's feed
  directory, `home.treasury.gov`, `api.bls.gov`, `www.sec.gov`/`data.sec.gov`, and
  `api.gdeltproject.org`. Nothing else leaves the process.
- **Usage and storage:** Nomina stores nothing. No accounts, no logs of requests or their
  contents, no telemetry. Source responses are held in memory (ten minutes for headlines up
  to a day for catalogs; immutable on-chain rounds for the process lifetime) to avoid repeat
  requests; nothing is written to disk.
- **Third parties:** each source processes those requests under its own policy. Your MCP host
  handles the conversation under its own policy. Operators of a hosted instance may keep
  infrastructure connection logs; Nomina adds none.
- **Retention:** none beyond the in-memory cache of the running process.
- **Contact:** https://github.com/nomina-xyz/nomina-mcp/issues

## Build from source

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run python scripts/build_bundle.py   # writes dist/Nomina.mcpb
uv run pytest -q                        # 12 tests
uv run ruff check .
```

## License

Code in this repository is MIT-licensed (see `LICENSE`).
