"""Host allow-list of the Streamable HTTP app: DNS-rebinding protection must hold."""

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
