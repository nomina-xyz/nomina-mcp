"""Streamable HTTP hosting for the Nomina MCP server."""

from pathlib import Path

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from nomina.server import mcp

# The same 256x256 PNG the MCPB bundle ships; MCP hosts show the server URL's favicon.
_ICON = (Path(__file__).resolve().parents[1] / "icon.png").read_bytes()


async def healthz(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def icon(request: Request) -> Response:
    return Response(
        _ICON, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"}
    )


def build_app(host: str) -> Starlette:
    """Serve MCP at /mcp (stateless, JSON responses), GET /healthz, and the icon.

    `host` is the name clients address the server by; DNS-rebinding protection rejects
    requests whose Host header is anything else (loopback names always pass).
    """
    app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[host, f"{host}:*", "localhost:*", "127.0.0.1:*"],
            allowed_origins=["http://localhost:*", "http://127.0.0.1:*"],
        ),
    )
    app.add_route("/healthz", healthz, methods=["GET"])
    app.add_route("/favicon.ico", icon, methods=["GET"])
    app.add_route("/icon.png", icon, methods=["GET"])
    return app
