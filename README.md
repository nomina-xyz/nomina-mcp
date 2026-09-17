# Nomina

Markets research for agents. Ask Claude the questions you'd ask an analyst — Nomina finds the
symbols, pulls the history, lines up the dates, and brings back the news behind the moves.

Three read-only tools, no API key, no account, no trading access:

- **`search_markets`** — find ticker symbols and dated headlines for a company, asset, sector,
  or market topic.
- **`research_asset`** — quote, period return, dated price history, and related news for one
  symbol.
- **`compare_assets`** — align 2–6 symbols on shared observation dates, in local currencies,
  with an explicit adjusted-vs-raw basis.

Plus one resource (`nomina://sources`: provenance, privacy, and methodology limits) and one
prompt (`research_brief`: a cited research-brief starter).

Data comes from Yahoo Finance's public chart/search endpoints. This is research, not a
real-time execution feed or a financial-statements service — see
[Data sources and limits](#data-sources-and-limits) below before relying on it.

## Install

**Claude Desktop:** Settings → Extensions → Advanced settings → Extension Developer →
Install Extension… → select `Nomina.mcpb` from a
[release](../../releases) (or build it yourself, see below). Requires a Claude Desktop
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

## Build from source

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run python scripts/build_bundle.py   # writes dist/Nomina.mcpb
uv run pytest -q                        # 8 tests
uv run ruff check .
```

## Data sources and limits

- Source: Yahoo Finance's unofficial public chart and search endpoints. No key, no
  guaranteed uptime, no rate-limit SLA — expect delayed, incomplete, or throttled responses,
  surfaced as explicit tool errors rather than fabricated data.
- **Yahoo's terms restrict automated collection without prior permission and prohibit
  redistributing the data.** Keyless HTTP access does not establish that permission. This
  project discloses that limitation; it does not resolve it. Review Yahoo's terms and obtain
  any permission you need before operating this at scale or on others' behalf.
- Headlines are links and titles only — not article text, not a complete news search.
- No fundamentals, no macroeconomic series, no order execution, no account access.
- Adjusted-close and raw-close bases are never mixed within a return calculation; if a full
  adjusted series isn't available, the whole series falls back to raw closes and says so.
- Comparisons align on shared exchange-local session dates and report local currencies with
  no FX conversion; a return with no valid shared basis is reported as unavailable, not
  estimated.

## Branding

The name "Nomina" and `icon.png` belong to [Nomina](https://www.nomina.io) (formerly Omni).
`icon.png` is their own unmodified square icon asset, sourced from their public brand page —
see `manifest.json`'s `_meta` field for exact provenance. That is not an independent
trademark grant; confirm brand-use rights with Nomina before relying on this outside
internal/personal use.

## License

Code in this repository is MIT-licensed (see `LICENSE`). The Nomina name and icon are excluded
from that grant — see [Branding](#branding).
