"""Search Lambda — find_best_tool via 2-stage retrieval pipeline."""

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
from qdrant_client import AsyncQdrantClient  # noqa: E402

from config import Settings  # noqa: E402
from embedding.openai_embedder import OpenAIEmbedder  # noqa: E402
from models import FindBestToolRequest, FindBestToolResponse, MCPTool, SearchResult  # noqa: E402
from pipeline.confidence import compute_confidence  # noqa: E402
from pipeline.sequential import SequentialStrategy  # noqa: E402
from reranking.cohere_reranker import CohereReranker  # noqa: E402
from retrieval.qdrant_store import QdrantStore  # noqa: E402

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
MAX_CACHE_SIZE = 200


def _get_cached(query: str) -> FindBestToolResponse | None:
    if query in _cache:
        ts, result = _cache[query]
        if time.time() - ts < CACHE_TTL:
            return result
        del _cache[query]
    return None


async def _supabase_fallback(query: str, limit: int = 5) -> list[SearchResult]:
    """Full-text search against Supabase for degraded mode (pending tools only)."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            resp = await c.post(
                f"{SUPABASE_URL}/rest/v1/rpc/search_tools_fts",
                headers={**_SB_HEADERS, "Content-Type": "application/json"},
                json={"search_query": query, "result_limit": limit, "status_filter": "pending"},
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
    return asyncio.run(_async_handler(event, context))


async def _async_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_id = getattr(context, "aws_request_id", "local")
    if event.get("source") == "warming":
        return await _warming_handler()
    t_start = time.time()

    # Dynamic timeout budget from Lambda remaining time
    remaining_ms = getattr(context, "get_remaining_time_in_millis", lambda: 30_000)()
    remaining_s = remaining_ms / 1000
    qdrant_timeout = max(1.0, min(5.0, remaining_s - 7.0))
    cohere_timeout = max(1.0, min(5.0, remaining_s - 2.0))
    logger.debug(
        f"[{request_id}] timeout budget: remaining={remaining_s:.1f}s "
        f"qdrant={qdrant_timeout:.1f}s cohere={cohere_timeout:.1f}s"
    )

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
        results = await asyncio.wait_for(
            strategy.search(req.query, req.top_k), timeout=qdrant_timeout + cohere_timeout
        )
    except asyncio.TimeoutError:
        total_budget = qdrant_timeout + cohere_timeout
        logger.warning(f"[{request_id}] Pipeline timed out after {total_budget:.1f}s")
        degraded = True
    except Exception as e:
        logger.warning(f"[{request_id}] Qdrant failed, fallback: {e}")
        degraded = True
    search_ms = (time.time() - t_search) * 1000

    # Only invoke lexical fallback when in degraded mode (Qdrant failed)
    # In normal mode, Qdrant already has all indexed tools
    fb_ms = 0.0
    if degraded:
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
    if len(_cache) > MAX_CACHE_SIZE:
        oldest_key = min(_cache, key=lambda k: _cache[k][0])
        del _cache[oldest_key]

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
