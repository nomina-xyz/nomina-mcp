# Privacy policy

This policy covers the Nomina MCP server published at
<https://github.com/nomina-xyz/nomina-mcp>, in every distribution form: the Claude Desktop
extension (`Nomina.mcpb`), the stdio server launched from a clone, the Gemini CLI extension,
the Agent Plugins manifest, the container image, and the hosted endpoint
`https://nomina-mcp.onrender.com/mcp`.

## Data sent

When a tool is called, Nomina sends only the inputs needed to answer it to the public sources
below:

- the search terms you submit to `search_markets` (to GDELT; catalog matching is local);
- the symbols you submit to `research_asset`, `compare_assets` and `market_overview`, as
  feed contract addresses and round numbers (to Ethereum JSON-RPC gateways), Treasury year
  pages, or BLS series identifiers;
- the ticker you submit to `company_fundamentals` (to SEC EDGAR);
- the requested history period or date window.

Nomina sends nothing else to any source. Each source receives ordinary connection metadata for those
requests, such as your IP address and Nomina's `User-Agent` header. SEC's fair-access policy
requires an identifying `User-Agent`; Nomina sends `Nomina MCP` with the maintainer's contact
address, never anything about you.

Hosts contacted: `ethereum.publicnode.com`, `rpc.mevblocker.io`,
`reference-data-directory.vercel.app` (Chainlink's feed directory), `home.treasury.gov`,
`api.bls.gov`, `www.sec.gov`, `data.sec.gov`, `api.gdeltproject.org`.

## Data stored

None. Nomina stores no queries, conversation history, account details, or credentials. The
server writes no log of requests or their contents, has no accounts, and sends no telemetry.
Source responses are held in process memory so repeated identical requests are not re-sent:
headlines for ten minutes, yields for an hour, macro series and company facts for six hours,
catalogs for a day, and on-chain rounds (immutable public data) for the life of the process.
Nothing is written to disk. Whoever operates a hosted instance (a reverse proxy or hosting
platform in front of it) may keep infrastructure connection logs under their own policy;
Nomina itself adds none.

## Third parties

- **Ethereum JSON-RPC gateways** (`ethereum.publicnode.com`, `rpc.mevblocker.io`) serve
  public blockchain state under their operators' policies.
- **Chainlink** publishes the feed directory: <https://chain.link/privacy-policy>.
- **US Department of the Treasury**, **US Bureau of Labor Statistics** and **US Securities and
  Exchange Commission** are US government sites with their own privacy notices.
- **The GDELT Project** processes headline searches under its own policy:
  <https://www.gdeltproject.org/>.
- **Render** hosts the public endpoint and keeps platform connection logs under
  <https://render.com/privacy>.
- **Your MCP host** (Claude Desktop, Claude Code, Gemini CLI, or any other client) handles
  your conversation, including tool inputs and outputs, under its own policy. Nomina has no
  access to that data beyond the tool arguments it receives.

## Contact

Questions and reports: <https://github.com/nomina-xyz/nomina-mcp/issues>.

## Effective date

2026-09-21 (supersedes the 2026-09-18 policy, which described Yahoo Finance as the data
source; Yahoo Finance is no longer contacted).
