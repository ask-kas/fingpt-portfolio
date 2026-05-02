"""
mcp_server.py — Standalone MCP server exposing Veris volatility tools.

Run with stdio transport (default for MCP):
    python -m backend.mcp_server

Or wire into Claude Desktop by adding to its config:
    {
      "mcpServers": {
        "veris-volatility": {
          "command": "python",
          "args": ["-m", "backend.mcp_server"],
          "cwd": "/absolute/path/to/fingpt-portfolio"
        }
      }
    }

The same tool registry (`backend/mcp_tools.TOOLS`) is reused by the FastAPI
chat endpoint, so any tool added here is automatically available to the
in-app assistant as well.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from backend.mcp_tools import TOOLS, call_tool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,  # stdout is reserved for the MCP wire protocol
)
logger = logging.getLogger("veris.mcp")

server: Server = Server("veris-volatility")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name=t["name"],
            description=t["description"],
            inputSchema=t["parameters"],
        )
        for t in TOOLS
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    logger.info("call_tool name=%s args=%s", name, arguments)
    # Tool handlers are sync (they hit yfinance synchronously). Run them in
    # a worker thread so they don't block the MCP event loop.
    result = await asyncio.to_thread(call_tool, name, arguments or {})
    return [TextContent(type="text", text=json.dumps(result, default=str))]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
