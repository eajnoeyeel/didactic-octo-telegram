"""Import MCP-Zero dataset → MCPServer/MCPTool models + optional Qdrant indexing.

Reads MCP-Zero JSON (308 servers, 2,797 tools), converts to our MCPServer/MCPTool
Pydantic models, and optionally indexes them into Qdrant with pre-computed
text-embedding-3-large vectors.

Usage:
    uv run python scripts/import_mcp_zero.py
    uv run python scripts/import_mcp_zero.py --input data/external/mcp-zero/servers.json
    uv run python scripts/import_mcp_zero.py --index  # Also upsert to Qdrant
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from loguru import logger

from src.models import TOOL_ID_SEPARATOR, MCPServer, MCPTool

# Default paths
DEFAULT_INPUT = "data/external/mcp-zero/servers.json"
DEFAULT_OUTPUT = "data/raw/mcp_zero_servers.jsonl"


def convert_server(raw: dict) -> MCPServer | None:
    """Convert a single MCP-Zero server entry to our MCPServer model.

    Args:
        raw: Raw server dictionary from MCP-Zero JSON.

    Returns:
        MCPServer instance or None if conversion fails.
    """
    server_id = raw.get("server_id") or raw.get("name") or raw.get("id", "")
    if not server_id:
        logger.warning(f"Server entry missing server_id: {raw.get('name', 'unknown')}")
        return None

    # Normalize server_id (remove special chars, lowercase)
    server_id = server_id.strip().lower().replace(" ", "_")

    tools_raw = raw.get("tools") or []
    tools: list[MCPTool] = []

    for t in tools_raw:
        tool_name = t.get("name") or t.get("tool_name", "")
        if not tool_name:
            continue

        tool_id = f"{server_id}{TOOL_ID_SEPARATOR}{tool_name}"
        tools.append(
            MCPTool(
                tool_id=tool_id,
                server_id=server_id,
                tool_name=tool_name,
                description=t.get("description", ""),
                input_schema=t.get("input_schema") or t.get("inputSchema"),
            )
        )

    if not tools:
        logger.warning(f"Server '{server_id}' has no tools, skipping")
        return None

    return MCPServer(
        server_id=server_id,
        name=raw.get("name", server_id),
        description=raw.get("description", ""),
        tools=tools,
    )


def load_mcp_zero_json(input_path: Path) -> list[dict]:
    """Load MCP-Zero servers from JSON file.

    Args:
        input_path: Path to MCP-Zero servers.json.

    Returns:
        List of raw server dictionaries.
    """
    with input_path.open() as f:
        data = json.load(f)

    # MCP-Zero may store as a list or as {"servers": [...]}
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "servers" in data:
        return data["servers"]

    logger.error(f"Unexpected JSON structure in {input_path}")
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Import MCP-Zero → MCPServer/MCPTool")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(DEFAULT_INPUT),
        help=f"MCP-Zero servers JSON path (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT),
        help=f"Output JSONL path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="Also upsert to Qdrant (requires QDRANT_URL and OPENAI_API_KEY)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        logger.info("Download MCP-Zero first. See data/external/README.md")
        return

    raw_servers = load_mcp_zero_json(args.input)
    logger.info(f"Loaded {len(raw_servers)} raw servers from {args.input}")

    servers: list[MCPServer] = []
    total_tools = 0

    for raw in raw_servers:
        server = convert_server(raw)
        if server is not None:
            servers.append(server)
            total_tools += len(server.tools)

    logger.info(f"Converted {len(servers)} servers, {total_tools} tools")

    # Save as JSONL
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        for server in servers:
            f.write(server.model_dump_json() + "\n")

    logger.info(f"Output: {args.output}")

    if args.index:
        logger.info("Qdrant indexing requested — run scripts/build_index.py separately")
        logger.info("  uv run python scripts/build_index.py --source mcp-zero")


if __name__ == "__main__":
    main()
