# Nomina MCP

Markets research for agents from public data. Research only — no trading,
no accounts, no API keys.

Five read-only tools:

- **`search_markets`** — find symbols in Nomina's catalog (on-chain price feeds, Treasury
  tenors, macro series, SEC registrants) and recent headlines.
- **`research_asset`** — latest value, period change, drawdown and volatility, dated history,
  and headlines for one symbol, over a named period or an exact date window.
- **`compare_assets`** — align 2–6 symbols on shared observation dates, each in its own unit.
- **`market_overview`** — period changes for BTC, ETH, SOL, gold, SPY, QQQ, EUR/USD, US 2y and
  10y yields and CPI.
- **`company_fundamentals`** — latest annual and quarterly financials and filings for an SEC
  registrant.

Data: Chainlink price feeds read from the Ethereum blockchain, the US Treasury yield curve,
Bureau of Labor Statistics series, SEC EDGAR filings, GDELT headlines.

## Pages

- [Install](install/) — hosted endpoint, Claude Desktop, Claude Code and other stdio clients, Gemini CLI, Agent Plugins, MCP Registry, self-hosted Docker (Streamable HTTP).
- [Hosting](deploy/) — the Render deployment; Fly.io and Cloud Run alternatives.
- [Tools](tools/) — symbols, parameters, constraints, response keys, and what the tools are not.
- [Privacy policy](privacy/) — what is sent, what is stored (nothing), third parties.
- [Data sources and limits](data-sources/) — each source's terms, methodology limits, branding.
- [Changelog](announcements/) — release notes, one file per version.

## Where it is listed

- Hosted endpoint: `https://mcp.nomina.io/mcp`
- MCP Registry: `io.github.nomina-xyz/nomina-mcp`
- Releases: <https://github.com/nomina-xyz/nomina-mcp/releases>
- Source: <https://github.com/nomina-xyz/nomina-mcp>
