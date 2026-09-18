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

None. Nomina stores no queries, conversation history, account details, or credentials. It
keeps no logs, has no accounts, and sends no telemetry. A hosted build of Nomina keeps no
request logs beyond the lifetime of the running process.

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
