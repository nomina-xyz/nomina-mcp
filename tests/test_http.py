"""Streamable HTTP app guards: host allow-list, no standalone GET stream, bounded bodies."""

import httpx
import pytest

from nomina.http import build_app

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "probe", "version": "0"},
    },
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _status_for_host(app, host: str) -> int:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://server"
    ) as client:
        response = await client.post(
            "/mcp",
            json=INIT,
            headers={
                "Host": host,
                "accept": "application/json, text/event-stream",
                "mcp-protocol-version": "2025-06-18",
            },
        )
        return response.status_code


@pytest.mark.anyio
async def test_only_listed_hosts_are_served():
    app = build_app(["mcp.nomina.io", "nomina-mcp.onrender.com"])
    async with app.router.lifespan_context(app):
        assert await _status_for_host(app, "mcp.nomina.io") == 200
        assert await _status_for_host(app, "nomina-mcp.onrender.com") == 200
        assert await _status_for_host(app, "evil.example") == 421
        assert await _status_for_host(app, "nomina-mcp.onrender.com.evil.example") == 421


@pytest.mark.anyio
async def test_mcp_rejects_non_post_and_oversized_bodies():
    app = build_app(["mcp.nomina.io"])
    headers = {"Host": "mcp.nomina.io", "accept": "application/json, text/event-stream"}
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://server"
        ) as client,
    ):
        get = await client.get("/mcp", headers=headers)
        assert get.status_code == 405
        assert get.headers["allow"] == "POST"

        too_big = dict(INIT, params={**INIT["params"], "pad": "x" * (64 * 1024)})
        assert (await client.post("/mcp", json=too_big, headers=headers)).status_code == 413

        lying = await client.post(
            "/mcp", content=b"{}", headers={**headers, "content-length": "999999"}
        )
        assert lying.status_code == 413

        ok = await client.post("/mcp", json=INIT, headers=headers)
        assert ok.status_code == 200
        assert (await client.get("/healthz")).status_code == 200


@pytest.mark.anyio
async def test_site_is_served_with_assets_and_no_traversal():
    app = build_app(["mcp.nomina.io"])
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://server") as c,
    ):
        page = await c.get("/")
        assert page.status_code == 200
        assert "Nomina MCP" in page.text
        assert 'rel="canonical" href="https://mcp.nomina.io/"' in page.text
        assert "noindex" not in page.text
        css = await c.get("/assets/css/site.css")
        assert css.status_code == 200
        assert css.headers["content-type"].startswith("text/css")
        font = await c.get("/assets/fonts/LayGrotesk-Regular.woff")
        assert font.status_code == 200
        assert (await c.get("/assets/../nomina/http.py")).status_code == 404
        assert (await c.get("/assets/%2e%2e/nomina/http.py")).status_code == 404
