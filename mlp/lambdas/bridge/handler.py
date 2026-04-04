"""Bridge MCP Server — Streamable HTTP via awslabs.mcp-lambda-handler.

Exposes find_best_tool and execute_tool as MCP tools so LLM agents can
connect to this Lambda as a standard MCP server.

Primary: awslabs.mcp-lambda-handler decorator pattern.
Fallback: Manual JSON-RPC dispatch (if library unavailable).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# PYTHONPATH: import from src/ directly (no file copying)
# ---------------------------------------------------------------------------
_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC_DIR))

from loguru import logger  # noqa: E402
from qdrant_client import AsyncQdrantClient  # noqa: E402

from config import Settings  # noqa: E402
from embedding.openai_embedder import OpenAIEmbedder  # noqa: E402
from models import TOOL_ID_SEPARATOR  # noqa: E402
from pipeline.confidence import compute_confidence  # noqa: E402
from pipeline.sequential import SequentialStrategy  # noqa: E402
from reranking.cohere_reranker import CohereReranker  # noqa: E402
from retrieval.qdrant_store import QdrantStore  # noqa: E402

# ---------------------------------------------------------------------------
# Global initialisation (warm across Lambda invocations)
# ---------------------------------------------------------------------------
settings = Settings()
_embedder = OpenAIEmbedder(
    api_key=settings.openai_api_key or "",
    model=settings.embedding_model,
    dimension=settings.embedding_dimension,
)
_qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
_tool_store = QdrantStore(client=_qdrant, collection_name="mcp_tools")
_server_store = QdrantStore(client=_qdrant, collection_name="mcp_servers")
_reranker = CohereReranker(api_key=settings.cohere_api_key) if settings.cohere_api_key else None
_strategy = SequentialStrategy(
    embedder=_embedder,
    tool_store=_tool_store,
    server_store=_server_store,
    reranker=_reranker,
)


# ---------------------------------------------------------------------------
# Core tool logic (shared by both library and fallback paths)
# ---------------------------------------------------------------------------
async def _find_best_tool(query: str, top_k: int = 3) -> dict[str, Any]:
    """Search for the best MCP tool matching a natural-language query."""
    results = await _strategy.search(query, top_k=top_k)
    confidence, needs_disamb = compute_confidence(results, settings.confidence_gap_threshold)
    return {
        "results": [r.model_dump() for r in results],
        "confidence": confidence,
        "disambiguation_needed": needs_disamb,
    }


async def _execute_tool(tool_id: str, params: dict | None = None) -> dict[str, Any]:
    """Proxy execution to the Execute Lambda (or direct MCP call)."""
    if TOOL_ID_SEPARATOR not in tool_id:
        return {
            "error": f"Invalid tool_id format. Expected 'server_id{TOOL_ID_SEPARATOR}tool_name'"
        }

    # In production this would invoke the Execute Lambda or call the
    # hosted MCP server directly.  For MLP we return a stub directing
    # the caller to the dedicated /api/execute endpoint.
    return {
        "error": "Direct execution via Bridge is not yet supported. "
        "Use the /api/execute REST endpoint instead.",
        "tool_id": tool_id,
    }


# ===================================================================
# PRIMARY PATH: awslabs.mcp-lambda-handler
# ===================================================================
try:
    from awslabs.mcp_lambda_handler import MCPLambdaHandler  # type: ignore[import-untyped]

    mcp = MCPLambdaHandler(name="mcp-discovery-bridge", version="1.0.0")

    @mcp.tool()
    def find_best_tool(query: str, top_k: int = 3) -> dict:
        """Find the best MCP tool for a given natural language query.

        Args:
            query: Natural language description of what you need
            top_k: Number of results to return (default 3)
        """
        return asyncio.get_event_loop().run_until_complete(_find_best_tool(query, top_k))

    @mcp.tool()
    def execute_tool(tool_id: str, params: str = "{}") -> dict:
        """Execute an MCP tool by its ID.

        Args:
            tool_id: The tool ID in format 'server_id::tool_name'
            params: JSON-encoded parameters to pass to the tool
        """
        parsed = json.loads(params) if isinstance(params, str) else params
        return asyncio.get_event_loop().run_until_complete(_execute_tool(tool_id, parsed))

    def lambda_handler(event: dict, context: Any) -> dict:
        """AWS Lambda entry-point (library path)."""
        return mcp.handle_request(event, context)

    logger.info("Bridge MCP handler: using awslabs.mcp-lambda-handler")

except ImportError:
    # ===============================================================
    # FALLBACK PATH: Manual Streamable HTTP / JSON-RPC dispatch
    # ===============================================================
    logger.warning("awslabs.mcp-lambda-handler not installed — using manual JSON-RPC fallback")

    _TOOL_SCHEMAS: list[dict[str, Any]] = [
        {
            "name": "find_best_tool",
            "description": "Find the best MCP tool for a given natural language query.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language description of what you need",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "execute_tool",
            "description": "Execute an MCP tool by its ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tool_id": {
                        "type": "string",
                        "description": "Tool ID in format 'server_id::tool_name'",
                    },
                    "params": {
                        "type": "object",
                        "description": "Parameters to pass to the tool",
                        "default": {},
                    },
                },
                "required": ["tool_id"],
            },
        },
    ]

    async def _dispatch_jsonrpc(body: dict) -> dict[str, Any]:
        """Route a single JSON-RPC request to the correct handler."""
        method = body.get("method", "")
        req_id = body.get("id")
        params = body.get("params", {})

        if method == "initialize":
            return _jsonrpc_ok(
                req_id,
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "mcp-discovery-bridge", "version": "1.0.0"},
                },
            )

        if method == "tools/list":
            return _jsonrpc_ok(req_id, {"tools": _TOOL_SCHEMAS})

        if method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments", {})
            if name == "find_best_tool":
                result = await _find_best_tool(
                    query=args.get("query", ""),
                    top_k=args.get("top_k", 3),
                )
            elif name == "execute_tool":
                result = await _execute_tool(
                    tool_id=args.get("tool_id", ""),
                    params=args.get("params"),
                )
            else:
                return _jsonrpc_error(req_id, -32601, f"Unknown tool: {name}")
            return _jsonrpc_ok(
                req_id,
                {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                },
            )

        if method == "ping":
            return _jsonrpc_ok(req_id, {})

        return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")

    def _jsonrpc_ok(req_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    async def _async_handler(event: dict) -> dict[str, Any]:
        http_method = event.get("requestContext", {}).get("http", {}).get("method", "POST")

        # GET /mcp → 405 (spec-compliant for stateless server)
        if http_method == "GET":
            return {
                "statusCode": 405,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Method Not Allowed. Use POST."}),
            }

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
                "body": json.dumps(_jsonrpc_error(None, -32700, "Parse error")),
            }

        result = await _dispatch_jsonrpc(body)
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "MCP-Version": "2025-03-26",
            },
            "body": json.dumps(result),
        }

    def lambda_handler(event: dict, context: Any) -> dict:
        """AWS Lambda entry-point (fallback JSON-RPC path)."""
        return asyncio.get_event_loop().run_until_complete(_async_handler(event))
