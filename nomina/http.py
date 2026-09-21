"""Streamable HTTP hosting for the Nomina MCP server."""

from pathlib import Path

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, Response

from nomina.server import mcp

# The same 256x256 PNG the MCPB bundle ships; MCP hosts show the server URL's favicon.
_ICON = (Path(__file__).resolve().parents[1] / "icon.png").read_bytes()


_INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Nomina MCP</title>
<link rel="icon" type="image/png" href="/icon.png">
<meta name="description" content="Markets research for agents from public data. Read-only MCP server.">
</head><body style="font-family:system-ui;max-width:40rem;margin:4rem auto;padding:0 1rem">
<h1>Nomina MCP</h1>
<p>Markets research for agents from public data: on-chain prices, Treasury yields, macro series,
SEC filings, headlines. Read-only, no API key.</p>
<p>MCP endpoint (Streamable HTTP): <code>POST /mcp</code></p>
<p><a href="https://nomina-xyz.github.io/nomina-mcp/">Documentation</a> ·
<a href="https://nomina-xyz.github.io/nomina-mcp/privacy/">Privacy policy</a> ·
<a href="https://github.com/nomina-xyz/nomina-mcp">Source</a></p>
</body></html>
"""


async def index(request: Request) -> HTMLResponse:
    return HTMLResponse(_INDEX)


async def healthz(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def icon(request: Request) -> Response:
    return Response(
        _ICON, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"}
    )


def build_app(hosts: list[str]) -> Starlette:
    """Serve MCP at /mcp (stateless, JSON responses), GET /, /healthz, and the icon.

    `hosts` are the names clients address the server by; DNS-rebinding protection rejects
    requests whose Host header is anything else (loopback names always pass).
    """
    allowed = [entry for host in hosts for entry in (host, f"{host}:*")]
    app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[*allowed, "localhost:*", "127.0.0.1:*"],
            allowed_origins=["http://localhost:*", "http://127.0.0.1:*"],
        ),
    )
    app.add_route("/", index, methods=["GET"])
    app.add_route("/healthz", healthz, methods=["GET"])
    app.add_route("/favicon.ico", icon, methods=["GET"])
    app.add_route("/icon.png", icon, methods=["GET"])
    return app
