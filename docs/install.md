# Install

Nomina is a stdio MCP server that can also serve Streamable HTTP. Every surface below
launches the same `server.py` with [uv](https://docs.astral.sh/uv/); nothing needs an API
key, account, or environment variable.

## Hosted endpoint (no install)

Nomina runs as a public Streamable HTTP server at:

```
https://nomina-mcp.onrender.com/mcp
```

- **Claude (web, desktop, mobile):** Settings → Connectors → *Add custom connector* → name
  `Nomina`, URL `https://nomina-mcp.onrender.com/mcp`. No authentication is required.
- **Claude Code:** `claude mcp add --transport http nomina https://nomina-mcp.onrender.com/mcp`
- Any other Streamable HTTP client: the same URL. `GET /healthz` returns `ok`.

It runs on a free instance that sleeps after 15 idle minutes; the first request after a pause
can take about a minute. Nothing is stored server-side (see the [privacy policy](../privacy/)).

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

## Self-hosted (Docker)

The container image `ghcr.io/nomina-xyz/nomina-mcp` serves Streamable HTTP at `/mcp` and a
liveness probe at `/healthz`, with no per-session state, so it can run behind any load
balancer:

```sh
docker run --rm -p 8000:8000 ghcr.io/nomina-xyz/nomina-mcp:2.0.0
```

Then point a Streamable HTTP client at `http://localhost:8000/mcp`. For Claude Code:

```sh
claude mcp add --transport http nomina http://localhost:8000/mcp
```

Other clients take the same URL in their own remote-server configuration.

DNS-rebinding protection accepts requests addressed to `localhost`, `127.0.0.1`, or the
public hostname; anything else is rejected with HTTP 421. Requests that carry a browser
`Origin` header are accepted only from `localhost` origins (HTTP 403 otherwise);
server-to-server clients send none. On a public hostname set `PUBLIC_HOST`
(`docker run -e PUBLIC_HOST=mcp.example.com …`) or pass `--public-host mcp.example.com`.
The port follows `PORT` or `--port`, default 8000.

Without Docker, the same mode runs from a clone:

```sh
uv run --frozen --no-dev server.py --transport streamable-http --port 8000
```

## For agents

An AI agent installing Nomina on a user's behalf should follow
[`llms-install.md`](https://github.com/nomina-xyz/nomina-mcp/blob/main/llms-install.md),
which includes a stdio handshake to confirm the five tools are exposed.
