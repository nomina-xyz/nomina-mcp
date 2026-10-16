"""Call the hosted Nomina endpoint from Python with the official MCP SDK.

    uv run --frozen python examples/hosted_client.py [SYMBOL]

Lists the tools, then runs `research_asset` for one symbol and prints the sourced summary.
Works against any Streamable HTTP MCP client stack the same way; swap the URL for a
self-hosted instance (`http://localhost:8000/mcp`).
"""

import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = "https://mcp.nomina.io/mcp"


async def main(symbol: str) -> None:
    async with (
        streamable_http_client(URL) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        print("tools:", ", ".join(t.name for t in tools.tools))

        result = await session.call_tool("research_asset", {"symbol": symbol, "period": "3mo"})
        report = result.structured_content
        latest = report["latest"]
        perf = report["period_performance"]
        print(f"{report['symbol']}: {latest['value']} {report['asset']['unit']} as of {latest['observed_at']}")
        print(f"3mo return: {perf['return_percent']:.2f}%")
        for source in report["sources"]:
            print(" -", source["url"])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "BTC"))
