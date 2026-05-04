"""
vlab_client.py — MCP client for NYU V-Lab via the `mcp-remote` stdio bridge.

V-Lab (https://vlab.stern.nyu.edu) — Robert Engle's volatility lab at NYU
Stern — exposes its institutional-grade analytics over the Model Context
Protocol at https://vlab.stern.nyu.edu/mcp. The endpoint requires OAuth, so
we proxy through `mcp-remote`, an npm package that:
  - Speaks stdio MCP locally
  - Forwards JSON-RPC to V-Lab's HTTP endpoint
  - Handles the OAuth dance in the user's browser on first call
  - Caches the token in ~/.mcp-auth so subsequent calls are silent

Requirements:
  - Node.js / npm installed (`npx` must be on PATH)
  - First chat call opens a browser tab for V-Lab login

If npx isn't found or V-Lab is unreachable, the chat falls back gracefully
to local tools only.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from typing import Any

logger = logging.getLogger("veris.vlab")

VLAB_MCP_URL = os.getenv("VLAB_MCP_URL", "https://vlab.stern.nyu.edu/mcp")
VLAB_DISABLED = os.getenv("VLAB_DISABLED", "").strip().lower() in ("1", "true", "yes")
VLAB_DISCOVERY_TIMEOUT = float(os.getenv("VLAB_DISCOVERY_TIMEOUT", "12"))
VLAB_CALL_TIMEOUT = float(os.getenv("VLAB_CALL_TIMEOUT", "30"))
TOOL_CACHE_TTL_SECONDS = 3600  # refresh tool list once per hour

_cached_tools: list[dict] = []
_cache_time: float = 0.0
_discovery_lock = asyncio.Lock()


def _resolve_npx() -> str | None:
    """Return the absolute path to npx, or None if it isn't installed."""
    # On Windows, npx is typically `npx.cmd` rather than a plain executable.
    for name in ("npx.cmd", "npx.bat", "npx"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _stdio_params():
    """
    Build the StdioServerParameters that spawn `npx mcp-remote <V-Lab URL>`.

    The first run will install mcp-remote (npx -y), open a browser for OAuth,
    and cache the token. Subsequent runs reuse the cached token.
    """
    from mcp import StdioServerParameters

    npx = _resolve_npx()
    if not npx:
        raise RuntimeError(
            "npx is not on PATH. Install Node.js (https://nodejs.org) so the "
            "V-Lab MCP bridge can run via `npx -y mcp-remote`."
        )
    return StdioServerParameters(
        command=npx,
        args=["-y", "mcp-remote", VLAB_MCP_URL],
    )


class _stdio_session:
    """Async context manager: spawn mcp-remote, init MCP session, yield it."""

    def __init__(self):
        self._stdio_cm = None
        self._session_cm = None

    async def __aenter__(self):
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        params = _stdio_params()
        self._stdio_cm = stdio_client(params)
        read, write = await self._stdio_cm.__aenter__()
        self._session_cm = ClientSession(read, write)
        session = await self._session_cm.__aenter__()
        await session.initialize()
        return session

    async def __aexit__(self, exc_type, exc, tb):
        if self._session_cm:
            try:
                await self._session_cm.__aexit__(exc_type, exc, tb)
            except Exception:
                pass
        if self._stdio_cm:
            try:
                await self._stdio_cm.__aexit__(exc_type, exc, tb)
            except Exception:
                pass


async def list_tools(force_refresh: bool = False) -> list[dict]:
    """
    Return V-Lab's tool list. Cached for one hour; pass force_refresh=True to
    bypass the cache. Returns an empty list (and logs a warning) if V-Lab is
    unreachable, so the chat can degrade gracefully.
    """
    global _cached_tools, _cache_time
    if VLAB_DISABLED:
        return _cached_tools  # always [] when disabled
    async with _discovery_lock:
        if (
            not force_refresh
            and _cached_tools
            and time.time() - _cache_time < TOOL_CACHE_TTL_SECONDS
        ):
            return _cached_tools

        async def _do_discover() -> list[dict]:
            async with _stdio_session() as session:
                resp = await session.list_tools()
                tools: list[dict] = []
                for t in (resp.tools or []):
                    tools.append({
                        "name": t.name,
                        "description": (t.description or "").strip(),
                        "inputSchema": t.inputSchema or {"type": "object", "properties": {}},
                    })
                return tools

        try:
            tools = await asyncio.wait_for(_do_discover(), timeout=VLAB_DISCOVERY_TIMEOUT)
            _cached_tools = tools
            _cache_time = time.time()
            logger.info("V-Lab MCP: discovered %d tools", len(tools))
            return _cached_tools
        except asyncio.TimeoutError:
            logger.warning(
                "V-Lab MCP discovery timed out after %.0fs — likely waiting on "
                "OAuth login. Chat will fall back to local tools. Set "
                "VLAB_DISABLED=1 to skip V-Lab entirely.",
                VLAB_DISCOVERY_TIMEOUT,
            )
            return _cached_tools  # keep stale cache if any, else []
        except Exception as e:
            logger.warning("V-Lab MCP discovery failed: %s", e)
            return _cached_tools


async def call_tool(name: str, arguments: dict[str, Any] | None) -> dict:
    """Forward a tool call to V-Lab via mcp-remote. Returns a dict for the LLM."""

    async def _do_call() -> dict:
        async with _stdio_session() as session:
            result = await session.call_tool(name, arguments=arguments or {})
            parts: list[str] = []
            for c in (result.content or []):
                text = getattr(c, "text", None)
                parts.append(text if text is not None else str(c))
            text_blob = "\n".join(parts).strip()
            payload: dict[str, Any] = {
                "source": "NYU V-Lab",
                "tool": name,
                "content": text_blob,
            }
            if getattr(result, "isError", False):
                payload["error"] = True
            return payload

    try:
        return await asyncio.wait_for(_do_call(), timeout=VLAB_CALL_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("V-Lab MCP call %s timed out after %.0fs", name, VLAB_CALL_TIMEOUT)
        return {
            "source": "NYU V-Lab",
            "tool": name,
            "error": True,
            "message": f"V-Lab tool {name} timed out after {VLAB_CALL_TIMEOUT:.0f}s",
        }
    except Exception as e:
        logger.exception("V-Lab MCP call failed: %s", name)
        return {
            "source": "NYU V-Lab",
            "tool": name,
            "error": True,
            "message": f"{type(e).__name__}: {e}",
        }
