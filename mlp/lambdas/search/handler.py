"""Search Lambda — find_best_tool via 2-stage retrieval pipeline."""

import asyncio
import json
import os
import time
from typing import Any

import httpx
from loguru import logger
from qdrant_client import AsyncQdrantClient

from config import Settings
from embedding.openai_embedder import OpenAIEmbedder
from models import FindBestToolRequest, FindBestToolResponse, MCPTool, SearchResult
from pipeline.confidence import compute_confidence
from pipeline.sequential import SequentialStrategy
from reranking.cohere_reranker import CohereReranker
from retrieval.qdrant_store import QdrantStore

settings = Settings()
embedder = OpenAIEmbedder(
    api_key=settings.openai_api_key or "",
    model=settings.embedding_model,
    dimension=settings.embedding_dimension,
)
_qclient = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
tool_store = QdrantStore(client=_qclient, collection_name="mcp_tools")
server_store = QdrantStore(client=_qclient, collection_name="mcp_servers")
reranker: CohereReranker | None = (
    CohereReranker(api_key=settings.cohere_api_key, model=settings.cohere_rerank_model)
    if settings.cohere_api_key
    else None
)
strategy = SequentialStrategy(
    embedder=embedder, tool_store=tool_store, server_store=server_store, reranker=reranker
)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
_SB_HEADERS: dict[str, str] = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

_cache: dict[str, tuple[float, FindBestToolResponse]] = {}
CACHE_TTL = 300


def _get_cached(query: str) -> FindBestToolResponse | None:
    if query in _cache:
        ts, result = _cache[query]
        if time.time() - ts < CACHE_TTL:
            return result
        del _cache[query]
    return None


async def _supabase_fallback(query: str, limit: int = 5) -> list[SearchResult]:
    """Full-text search against Supabase for degraded / pending-tool mode."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            resp = await c.post(
                f"{SUPABASE_URL}/rest/v1/rpc/search_tools_fts",
                headers={**_SB_HEADERS, "Content-Type": "application/json"},
                json={"search_query": query, "result_limit": limit},
            )
            resp.raise_for_status()
            rows = resp.json()
    except Exception as e:
        logger.warning(f"Supabase fallback failed: {e}")
        return []
    return [
        SearchResult(
            tool=MCPTool(
                server_id=r["server_id"],
                tool_name=r["tool_name"],
                tool_id=r["tool_id"],
                description=r.get("description"),
                input_schema=r.get("input_schema"),
            ),
            score=0.0,
            rank=i + 1,
        )
        for i, r in enumerate(rows)
    ]


def _deduplicate(results: list[SearchResult], top_k: int) -> list[SearchResult]:
    seen: dict[str, SearchResult] = {}
    for r in results:
        if r.tool.tool_id not in seen or r.score > seen[r.tool.tool_id].score:
            seen[r.tool.tool_id] = r
    ranked = sorted(seen.values(), key=lambda x: x.score, reverse=True)[:top_k]
    return [r.model_copy(update={"rank": i + 1}) for i, r in enumerate(ranked)]


async def _warming_handler() -> dict[str, Any]:
    """Warm Qdrant cluster and Supabase connection."""
    try:
        vec = await embedder.embed_one("test")
        await _qclient.search(collection_name="mcp_tools", query_vector=vec.tolist(), limit=1)
    except Exception as e:
        logger.warning(f"Warming Qdrant failed: {e}")
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                await c.get(
                    f"{SUPABASE_URL}/rest/v1/mcp_tools?select=tool_id&limit=1", headers=_SB_HEADERS
                )
        except Exception as e:
            logger.warning(f"Warming Supabase failed: {e}")
    return {"statusCode": 200, "body": json.dumps({"status": "warm"})}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point."""
    return asyncio.get_event_loop().run_until_complete(_async_handler(event, context))


async def _async_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_id = getattr(context, "aws_request_id", "local")
    if event.get("source") == "warming":
        return await _warming_handler()
    t_start = time.time()

    try:
        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event
        qp = event.get("queryStringParameters") or {}
        query = body.get("query") or qp.get("query", "")
        req = FindBestToolRequest(query=query, top_k=int(body.get("top_k", qp.get("top_k", 3))))
    except Exception as e:
        logger.error(f"[{request_id}] Bad request: {e}")
        return _respond(400, {"error": str(e)})

    cached = _get_cached(req.query)
    if cached is not None:
        logger.info(f"[{request_id}] Cache hit query='{req.query[:40]}'")
        return _respond(200, cached.model_dump())

    t_search, results, degraded = time.time(), [], False
    try:
        results = await strategy.search(req.query, req.top_k)
    except Exception as e:
        logger.warning(f"[{request_id}] Qdrant failed, fallback: {e}")
        degraded = True
    search_ms = (time.time() - t_search) * 1000

    t_fb = time.time()
    fb = await _supabase_fallback(req.query, limit=req.top_k)
    fb_ms = (time.time() - t_fb) * 1000
    if fb:
        results = _deduplicate(results + fb, req.top_k)

    confidence, disambiguation_needed = compute_confidence(
        results, gap_threshold=settings.confidence_gap_threshold
    )
    total_ms = (time.time() - t_start) * 1000

    response = FindBestToolResponse(
        query=req.query,
        results=results,
        confidence=confidence,
        disambiguation_needed=disambiguation_needed,
        strategy_used="sequential",
        latency_ms=round(total_ms, 1),
    )
    _cache[req.query] = (time.time(), response)

    logger.info(
        json.dumps(
            {
                "event": "search",
                "request_id": request_id,
                "query": req.query[:60],
                "num_results": len(results),
                "confidence": round(confidence, 3),
                "degraded": degraded,
                "search_ms": round(search_ms, 1),
                "fallback_ms": round(fb_ms, 1),
                "total_ms": round(total_ms, 1),
            }
        )
    )
    return _respond(200, response.model_dump())


def _respond(status: int, body: Any) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
