# Nomina

Markets research for agents.

Four read-only tools, no API key, no account, no trading access:

- **`search_markets`** — find ticker symbols and dated headlines for a company, asset, sector,
  or market topic.
- **`research_asset`** — quote, period return, drawdown and volatility, dated price history,
  and related news for one symbol, over a named period or an exact date window.
- **`compare_assets`** — align 2–6 symbols on shared observation dates, in local currencies,
  with an explicit adjusted-vs-raw basis.
- **`market_overview`** — period returns for major indexes, rates, the dollar, gold, oil,
  BTC, ETH and EURUSD.

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

**Self-hosted (Streamable HTTP):** `docker run --rm -p 8000:8000 ghcr.io/nomina-xyz/nomina-mcp:1.3.3`,
then connect to `http://localhost:8000/mcp`. Details in the docs below.

## Docs

Install guides, tool reference, privacy policy, and data-source limits:
https://nomina-xyz.github.io/nomina-mcp/ — see especially
[Data sources and limits](https://nomina-xyz.github.io/nomina-mcp/data-sources/).

## Privacy Policy

Full policy: https://nomina-xyz.github.io/nomina-mcp/privacy/

- **Collection:** when a tool runs, only its inputs — search terms, symbols, and the requested
  period or date window — are sent to Yahoo Finance's public endpoints
  (`query1.finance.yahoo.com`). Nothing else leaves the process.
- **Usage and storage:** Nomina stores nothing. No accounts, no logs of requests or their
  contents, no telemetry. Provider responses are held in memory for up to 60 seconds to avoid
  repeat requests; nothing is written to disk.
- **Third parties:** Yahoo Finance processes those requests under its own policy
  (https://legal.yahoo.com/us/en/yahoo/privacy/index.html). Your MCP host handles the
  conversation under its own policy. Operators of a hosted instance may keep infrastructure
  connection logs; Nomina adds none.
- **Retention:** none beyond the 60-second in-memory cache of the running process.
- **Contact:** https://github.com/nomina-xyz/nomina-mcp/issues

## Build from source

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run python scripts/build_bundle.py   # writes dist/Nomina.mcpb
uv run pytest -q                        # 14 tests
uv run ruff check .
```

## License

Code in this repository is MIT-licensed (see `LICENSE`).
