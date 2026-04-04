"""Execute Lambda — Proxy tool execution to hosted MCP servers.

MLP supports 3-5 pre-registered servers only.  This handler:
1. Parses tool_id into server_id + tool_name
2. Looks up the server URL from Supabase mcp_servers
3. Validates the server is in the allowed list
4. Forwards the request as MCP tools/call via HTTP
5. Logs execution to Supabase query_logs
6. Returns the result (or a structured error)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Any

# ---------------------------------------------------------------------------
# PYTHONPATH: import from src/ directly (no file copying)
# ---------------------------------------------------------------------------
_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC_DIR))

import httpx  # noqa: E402
from loguru import logger  # noqa: E402

from config import Settings  # noqa: E402
from models import TOOL_ID_SEPARATOR  # noqa: E402

# ---------------------------------------------------------------------------
# Global initialisation
# ---------------------------------------------------------------------------
settings = Settings()

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# MLP: only pre-registered hosted servers can be executed.
# Populated from Supabase at init; Phase 2 will make this dynamic.
ALLOWED_EXECUTION_SERVERS: set[str] = set()


def _supabase_headers() -> dict[str, str]:
    return {
        "apikey": _SUPABASE_KEY,
        "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------
async def _fetch_server(server_id: str) -> dict[str, Any] | None:
    """Fetch server metadata from Supabase by server_id."""
    url = f"{_SUPABASE_URL}/rest/v1/mcp_servers?server_id=eq.{server_id}&select=server_id,name,url"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=_supabase_headers())
        resp.raise_for_status()
        rows = resp.json()
    return rows[0] if rows else None


async def _log_execution(
    tool_id: str,
    server_id: str,
    success: bool,
    latency_ms: float,
    error_message: str | None = None,
) -> None:
    """Best-effort log to Supabase query_logs (fire-and-forget)."""
    if not _SUPABASE_URL:
        return
    payload = {
        "tool_id": tool_id,
        "server_id": server_id,
        "event_type": "execute",
        "success": success,
        "latency_ms": latency_ms,
        "error_message": error_message,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{_SUPABASE_URL}/rest/v1/query_logs",
                headers=_supabase_headers(),
                json=payload,
            )
    except Exception as exc:
        logger.warning(f"Failed to log execution: {exc}")


# ---------------------------------------------------------------------------
# Proxy execution
# ---------------------------------------------------------------------------
async def _proxy_execute(tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Forward tools/call to the hosted MCP server."""
    if TOOL_ID_SEPARATOR not in tool_id:
        return {
            "error": f"Invalid tool_id format. Expected 'server_id{TOOL_ID_SEPARATOR}tool_name'"
        }

    server_id, tool_name = tool_id.split(TOOL_ID_SEPARATOR, 1)
    start = time.monotonic()

    # 1. Fetch server metadata
    server = await _fetch_server(server_id)
    if server is None:
        await _log_execution(tool_id, server_id, False, 0, "Server not found")
        return {"error": f"Server '{server_id}' not found"}

    server_url: str | None = server.get("url")
    if not server_url:
        await _log_execution(tool_id, server_id, False, 0, "No execution URL")
        return {"error": f"Server '{server_id}' does not support execution yet"}

    # 2. Allowed-list check (when populated)
    if ALLOWED_EXECUTION_SERVERS and server_id not in ALLOWED_EXECUTION_SERVERS:
        await _log_execution(tool_id, server_id, False, 0, "Server not allowed")
        return {"error": f"Server '{server_id}' is not in the allowed execution list"}

    # 3. Forward as MCP tools/call
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                f"{server_url.rstrip('/')}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": params},
                    "id": 1,
                },
            )
            resp.raise_for_status()
            result = resp.json()
    except httpx.TimeoutException:
        latency = (time.monotonic() - start) * 1000
        await _log_execution(tool_id, server_id, False, latency, "Proxy timeout")
        return {"error": "Upstream MCP server timed out (25s limit)"}
    except httpx.HTTPStatusError as exc:
        latency = (time.monotonic() - start) * 1000
        await _log_execution(tool_id, server_id, False, latency, str(exc))
        return {"error": f"Upstream error: HTTP {exc.response.status_code}"}
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        await _log_execution(tool_id, server_id, False, latency, str(exc))
        return {"error": "Failed to reach upstream MCP server"}

    latency = (time.monotonic() - start) * 1000
    await _log_execution(tool_id, server_id, True, latency)
    return result


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------
async def _async_handler(event: dict) -> dict[str, Any]:
    """Parse the API Gateway event and proxy execution."""
    raw_body = event.get("body", "{}")
    if event.get("isBase64Encoded"):
        import base64

        raw_body = base64.b64decode(raw_body).decode()

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Invalid JSON in request body"}),
        }

    tool_id: str = body.get("tool_id", "")
    params: dict = body.get("params", {})

    if not tool_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing required field: tool_id"}),
        }

    result = await _proxy_execute(tool_id, params)

    # Determine status code from result
    is_error = "error" in result
    if is_error:
        err_msg: str = result.get("error", "")
        if "not found" in err_msg:
            status = 404
        elif "not support" in err_msg or "not in the allowed" in err_msg:
            status = 400
        elif "timed out" in err_msg:
            status = 504
        elif "Upstream error" in err_msg:
            status = 502
        else:
            status = 400
    else:
        status = 200

    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result),
    }


def lambda_handler(event: dict, context: Any) -> dict:
    """AWS Lambda entry-point."""
    return asyncio.run(_async_handler(event))
