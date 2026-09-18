"""Streamable HTTP hosting for the Nomina MCP server."""

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from nomina.server import mcp


async def healthz(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def build_app(host: str) -> Starlette:
    """Serve MCP at /mcp (stateless, JSON responses) plus a GET /healthz liveness probe.

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
    return app
