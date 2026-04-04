"""Register Lambda — Provider registers an MCP server with its tools."""

import asyncio
import json
import os
import sys

# ---------------------------------------------------------------------------
# PYTHONPATH: import from src/ directly (no file copying)
# ---------------------------------------------------------------------------
_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC_DIR))

import boto3  # noqa: E402
import httpx  # noqa: E402
from loguru import logger  # noqa: E402

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
MAX_DESCRIPTION_LENGTH = 2000
INJECTION_PATTERNS = [
    "ignore previous",
    "ignore above",
    "system:",
    "[inst]",
    "you are now",
    "forget everything",
    "<|im_start|>",
    "do not follow",
    "disregard",
    "override",
]
eventbridge = boto3.client("events")


def validate_description(desc: str) -> str | None:
    """Return error message if invalid, None if OK."""
    if len(desc) > MAX_DESCRIPTION_LENGTH:
        return f"Description exceeds {MAX_DESCRIPTION_LENGTH} character limit"
    lower = desc.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in lower:
            return "Description contains prohibited pattern"
    return None


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


async def _supabase_insert(table: str, data: dict | list, *, upsert: bool = False) -> list:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    prefer_parts = ["return=representation"]
    if upsert:
        prefer_parts.append("resolution=merge-duplicates")
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": ", ".join(prefer_parts),
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=data, headers=headers, timeout=10.0)
        resp.raise_for_status()
        return resp.json()


async def _async_handler(event: dict, _context: object) -> dict:
    try:
        body = json.loads(event.get("body", "{}"))
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"error": "Invalid JSON body"})

    server_id = body.get("server_id")
    name = body.get("name")
    description = body.get("description", "")
    url = body.get("url")
    tags = body.get("tags", [])
    tools = body.get("tools", [])

    if not server_id or not name or not url:
        return _response(400, {"error": "Missing required fields: server_id, name, url"})
    if not tools:
        return _response(400, {"error": "At least one tool is required"})

    # Validate server description (anti-gaming)
    if description:
        if err := validate_description(description):
            return _response(400, {"error": f"Server description: {err}"})

    # Validate each tool description
    for tool in tools:
        if tool_desc := tool.get("description", ""):
            if err := validate_description(tool_desc):
                return _response(400, {"error": f"Tool '{tool.get('tool_name', '?')}': {err}"})

    # Insert server into Supabase
    server_row = {
        "server_id": server_id,
        "name": name,
        "description": description,
        "url": url,
        "tags": tags,
    }
    try:
        await _supabase_insert("mcp_servers", server_row, upsert=True)
    except httpx.HTTPStatusError as e:
        logger.error(f"Supabase server insert failed: {e.response.status_code}")
        return _response(500, {"error": "Failed to register server"})

    # Insert tools into Supabase (bulk, index_status='pending')
    tool_rows = [
        {
            "tool_id": f"{server_id}::{t['tool_name']}",
            "server_id": server_id,
            "tool_name": t["tool_name"],
            "description": t.get("description", ""),
            "input_schema": t.get("input_schema"),
            "index_status": "pending",
        }
        for t in tools
    ]
    try:
        await _supabase_insert("mcp_tools", tool_rows)
    except httpx.HTTPStatusError as e:
        logger.error(f"Supabase tools insert failed: {e.response.status_code}")
        return _response(500, {"error": "Failed to register tools"})

    # Publish EventBridge event for async indexing
    try:
        eventbridge.put_events(
            Entries=[
                {
                    "Source": "mcp-discovery",
                    "DetailType": "server.registered",
                    "Detail": json.dumps({"server_id": server_id}),
                }
            ]
        )
    except Exception as e:
        logger.error(f"EventBridge publish failed: {e}")
        # Non-fatal: tools in DB with pending status, retryable via DLQ

    return _response(
        201,
        {
            "server_id": server_id,
            "tools_count": len(tools),
            "message": "Server registered. Indexing in progress.",
        },
    )


def lambda_handler(event: dict, context: object) -> dict:
    """AWS Lambda entry point."""
    return asyncio.run(_async_handler(event, context))
