# Agent install guide

Instructions for an AI agent installing Nomina for a user. No API key, no account,
and no credentials of any kind are required.

## Prerequisites

[uv](https://docs.astral.sh/uv/) must be on PATH. Check with `uv --version`; if it is
missing, install it with `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS/Linux)
or `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` (Windows).

Python is not a separate prerequisite: `uv run` provisions the interpreter pinned in
`.python-version` (>=3.12,<3.14).

## Install

Clone the repository to a stable location the user will not delete:

```sh
git clone https://github.com/nomina-xyz/nomina-mcp.git
cd nomina-mcp
uv sync --frozen --no-dev
```

## Configure

Add this to the client's MCP configuration, replacing `/absolute/path/to/nomina-mcp`
with the absolute path of the clone:

```json
{
  "mcpServers": {
    "nomina": {
      "command": "uv",
      "args": ["run", "--frozen", "--no-dev", "--directory", "/absolute/path/to/nomina-mcp", "server.py"]
    }
  }
}
```

Do not add an `env` block. The server reads no environment variables and takes no
secrets.

## Verify

Restart the client and confirm five tools are exposed: `search_markets`,
`research_asset`, `compare_assets`, `market_overview`, and `company_fundamentals`. A direct check without a client:

```sh
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | uv run --frozen --no-dev --directory /absolute/path/to/nomina-mcp server.py
```

The `tools/list` response must list all five tool names. `tools/list` sent before the
`notifications/initialized` line returns nothing useful, so keep the order above.

A first run downloads the interpreter and dependencies and may take a minute; later
starts are fast.

## Troubleshooting

- `command not found: uv` — uv is not on the PATH of the process that launches the
  client. Use the absolute path to the `uv` binary (`which uv`) as `command`.
- `No such file or directory` — `--directory` must be the absolute path to the clone
  root, the directory holding `server.py` and `pyproject.toml`.
- Tool calls return explicit upstream errors — expected when a public source (Ethereum RPC
  gateways, GDELT, SEC EDGAR) throttles or omits data. The server surfaces the error rather
  than inventing values. See https://nomina-xyz.github.io/nomina-mcp/data-sources/.
