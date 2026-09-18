# Privacy policy

This policy covers the Nomina MCP server published at
<https://github.com/nomina-xyz/nomina-mcp>, in every distribution form: the Claude Desktop
extension (`Nomina.mcpb`), the stdio server launched from a clone, the Gemini CLI extension,
the Agent Plugins manifest, and any hosted build of the same code.

## Data sent

When a tool is called, Nomina sends only the inputs needed to answer it to Yahoo Finance's
public endpoints at `query1.finance.yahoo.com`:

- the search terms you submit to `search_markets`;
- the symbols you submit to `research_asset` and `compare_assets`;
- the requested history period or date window.

Nothing else is sent anywhere. Yahoo receives ordinary connection metadata for those
requests, such as your IP address and Nomina's `User-Agent` header.

## Data stored

None. Nomina stores no queries, conversation history, account details, or credentials. The
server writes no log of requests or their contents, has no accounts, and sends no telemetry.
Provider responses are held in process memory for up to 60 seconds so that repeated identical
requests are not re-sent to Yahoo; nothing is written to disk. Whoever operates a hosted
instance (a reverse proxy or hosting platform in front of it) may keep infrastructure
connection logs under their own policy; Nomina itself adds none.

## Third parties

- **Yahoo Finance** processes the requests above under its own policy:
  <https://legal.yahoo.com/us/en/yahoo/privacy/index.html>.
- **Your MCP host** (Claude Desktop, Claude Code, Gemini CLI, or any other client) handles
  your conversation, including tool inputs and outputs, under its own policy. Nomina has no
  access to that data beyond the tool arguments it receives.

## Contact

Questions and reports: <https://github.com/nomina-xyz/nomina-mcp/issues>.

## Effective date

2026-09-18.
