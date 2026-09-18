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

## Docs

Install guides, tool reference, privacy policy, and data-source limits:
https://nomina-xyz.github.io/nomina-mcp/ — see especially
[Data sources and limits](https://nomina-xyz.github.io/nomina-mcp/data-sources/).

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
