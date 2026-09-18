# Install

Nomina is a local stdio MCP server. Every surface below launches the same
`server.py` with [uv](https://docs.astral.sh/uv/); nothing needs an API key, account,
or environment variable.

## Claude Desktop

Settings → Extensions → Advanced settings → Extension Developer → Install Extension… →
select `Nomina.mcpb` from a [release](https://github.com/nomina-xyz/nomina-mcp/releases)
(or build it yourself with `uv run python scripts/build_bundle.py`). Requires a Claude Desktop
release with MCPB v0.4 UV-runtime support and internet access on first install.

## Claude Code and any other stdio client

Clone the repository, then point the client at it as a local stdio server:

```json
{
  "mcpServers": {
    "nomina": {
      "command": "uv",
      "args": ["run", "--frozen", "--no-dev", "--directory", "/path/to/nomina-mcp", "server.py"]
    }
  }
}
```

## Gemini CLI

```sh
gemini extensions install https://github.com/nomina-xyz/nomina-mcp
```

The repository ships `gemini-extension.json`, so the extension is installed straight from
the Git URL.
<!-- Command format verified against Google's Gemini CLI extensions docs, not tested on this machine. -->

## Agent Plugins

`plugin.json` and `mcp.json` at the repository root follow the
[Agent Plugins](https://agent-plugins.org) 1.0.0 schema. Clients that read that format
(for example Cursor) can install the clone as a local plugin directory; `mcp.json` declares
the same stdio launch as above with the repository root as the working directory.

## MCP Registry

Nomina is published in the official MCP Registry as `io.github.nomina-xyz/nomina-mcp`.
Registry-aware clients can install it by that name; verify the current entry with:

```sh
curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.nomina-xyz/nomina-mcp"
```

## For agents

An AI agent installing Nomina on a user's behalf should follow
[`llms-install.md`](https://github.com/nomina-xyz/nomina-mcp/blob/main/llms-install.md),
which includes a stdio handshake to confirm the three tools are exposed.
