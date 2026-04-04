"""Index Lambda — Async tool indexing triggered by EventBridge."""

import asyncio
import json
import os

import httpx
from loguru import logger
from qdrant_client import AsyncQdrantClient

from config import Settings
from embedding.openai_embedder import OpenAIEmbedder
from models import MCPTool
from retrieval.qdrant_store import QdrantStore

# Global init (reused across warm Lambda invocations)
settings = Settings()
embedder = OpenAIEmbedder(
    api_key=settings.openai_api_key or "",
    model=settings.embedding_model,
    dimension=settings.embedding_dimension,
)
qdrant_store = QdrantStore(
    client=AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key),
    collection_name=settings.qdrant_collection_name,
)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
}


async def _fetch_pending_tools(server_id: str) -> list[dict]:
    url = f"{SUPABASE_URL}/rest/v1/mcp_tools"
    params = {"server_id": f"eq.{server_id}", "index_status": "eq.pending", "select": "*"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=SUPABASE_HEADERS, params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json()


async def _update_tool_status(tool_ids: list[str], status: str) -> None:
    if not tool_ids:
        return
    url = f"{SUPABASE_URL}/rest/v1/mcp_tools"
    params = {"tool_id": f"in.({','.join(tool_ids)})"}
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            url,
            headers=SUPABASE_HEADERS,
            params=params,
            json={"index_status": status},
            timeout=10.0,
        )
        resp.raise_for_status()


def _row_to_mcp_tool(row: dict) -> MCPTool:
    return MCPTool(
        server_id=row["server_id"],
        tool_name=row["tool_name"],
        tool_id=row["tool_id"],
        description=row.get("description"),
        input_schema=row.get("input_schema"),
    )


async def _async_handler(event: dict, _context: object) -> dict:
    detail = event.get("detail", {})
    if isinstance(detail, str):
        detail = json.loads(detail)

    server_id = detail.get("server_id")
    if not server_id:
        logger.error("Missing server_id in event detail")
        return {"statusCode": 400, "body": "Missing server_id"}

    logger.info(f"Indexing tools for server_id={server_id}")

    # 1. Fetch pending tools from Supabase
    try:
        rows = await _fetch_pending_tools(server_id)
    except httpx.HTTPStatusError as e:
        logger.error(f"Supabase fetch failed: {e.response.status_code}")
        return {"statusCode": 500, "body": "Failed to fetch pending tools"}

    if not rows:
        logger.info(f"No pending tools for server_id={server_id}")
        return {"statusCode": 200, "body": "No pending tools"}

    tools = [_row_to_mcp_tool(row) for row in rows]
    tool_ids = [t.tool_id for t in tools]
    logger.info(f"Found {len(tools)} pending tools to index")

    # 2. Embed tool descriptions
    try:
        texts = [QdrantStore.build_tool_text(tool) for tool in tools]
        vectors = await embedder.embed_batch(texts)
    except Exception as e:
        logger.error(f"Embedding failed for server_id={server_id}: {e}")
        return {"statusCode": 500, "body": "Embedding failed"}

    # 3. Upsert to Qdrant (idempotent via uuid5)
    try:
        await qdrant_store.upsert_tools(tools, vectors)
    except Exception as e:
        logger.error(f"Qdrant upsert failed for server_id={server_id}: {e}")
        return {"statusCode": 500, "body": "Qdrant upsert failed"}

    # 4. Update status to 'indexed' in Supabase
    try:
        await _update_tool_status(tool_ids, "indexed")
    except httpx.HTTPStatusError as e:
        logger.warning(
            f"Supabase status update failed: {e.response.status_code}. "
            "Tools in Qdrant but status='pending' (safe: next retry is idempotent)."
        )

    logger.info(f"Indexed {len(tools)} tools for server_id={server_id}")
    return {"statusCode": 200, "body": f"Indexed {len(tools)} tools"}


def lambda_handler(event: dict, context: object) -> dict:
    """AWS Lambda entry point."""
    return asyncio.get_event_loop().run_until_complete(_async_handler(event, context))
