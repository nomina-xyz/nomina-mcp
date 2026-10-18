"""Streamable HTTP hosting for the Nomina MCP server."""

import os
from pathlib import Path

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from nomina.server import mcp

# Largest request body /mcp accepts. The biggest legitimate call (compare_assets with six
# 32-character symbols and two dates) is well under 1 KiB; the cap bounds memory per request.
MAX_BODY_BYTES = 64 * 1024

_ROOT = Path(__file__).resolve().parents[1]
# The same 256x256 PNG the MCPB bundle ships; MCP hosts show the server URL's favicon.
_ICON = (_ROOT / "icon.png").read_bytes()
# The product site (site/): static HTML served at / with its assets under /assets.
_SITE = _ROOT / "site"
_INDEX = (_SITE / "index.html").read_text()


async def index(request: Request) -> HTMLResponse:
    return HTMLResponse(_INDEX)


async def healthz(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def openai_apps_challenge(request: Request) -> PlainTextResponse:
    """Domain-verification token for OpenAI's plugin directory; the token alone, or 404 if unset."""
    token = os.environ.get("OPENAI_APPS_CHALLENGE", "").strip()
    if not token:
        return PlainTextResponse("not configured", status_code=404)
    return PlainTextResponse(token)


async def icon(request: Request) -> Response:
    return Response(
        _ICON, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"}
    )


class _McpRequestGuard:
    """Bound what /mcp will accept before the MCP transport reads anything.

    The server is stateless with JSON responses, so the standalone GET event stream is never
    used; without this guard every GET holds an open SSE connection and a server task for as
    long as the client keeps it alive. Bodies above MAX_BODY_BYTES are refused by declared
    length or, for chunked uploads, as soon as the limit is crossed.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != "/mcp":
            await self.app(scope, receive, send)
            return
        if scope["method"] != "POST":
            await PlainTextResponse(
                "Method Not Allowed", status_code=405, headers={"Allow": "POST"}
            )(scope, receive, send)
            return
        headers = dict(scope["headers"])
        declared = headers.get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > MAX_BODY_BYTES):
            await PlainTextResponse("Payload Too Large", status_code=413)(scope, receive, send)
            return
        received = 0
        response_started = False

        async def limited_receive() -> dict:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_BODY_BYTES:
                    raise _BodyTooLarge
            return message

        async def tracked_send(message: dict) -> None:
            nonlocal response_started
            response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _BodyTooLarge:
            if response_started:
                raise  # nothing sane to send; the server closes the connection
            await PlainTextResponse("Payload Too Large", status_code=413)(scope, receive, send)


class _BodyTooLarge(Exception):
    pass


def build_app(hosts: list[str]) -> Starlette:
    """Serve MCP at /mcp (stateless, JSON responses), the product site at / and /assets,
    /healthz, and the icon.

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
    app.add_route("/.well-known/openai-apps-challenge", openai_apps_challenge, methods=["GET"])
    app.add_route("/favicon.ico", icon, methods=["GET"])
    app.add_route("/icon.png", icon, methods=["GET"])
    app.mount("/assets", StaticFiles(directory=_SITE / "assets"), name="assets")
    app.add_middleware(_McpRequestGuard)
    return app
