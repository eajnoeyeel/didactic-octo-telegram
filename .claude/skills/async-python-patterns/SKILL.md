---
name: async-python-patterns
description: Async patterns for MCP Discovery Platform — connection pooling (Qdrant/Cohere/OpenAI), batch embedding with rate limiting, concurrent pipeline strategy execution, and async resource lifecycle. Use when implementing or optimizing async I/O in the retrieval pipeline.
---

# Async Python Patterns — MCP Discovery

Project-specific async patterns for the retrieval pipeline. For general asyncio concepts, Claude already knows them.

## 1. Connection Pool Management

All external clients should be instantiated once and shared via DI.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from qdrant_client import AsyncQdrantClient
from openai import AsyncOpenAI
import cohere

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create clients once
    app.state.qdrant = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )
    app.state.openai = AsyncOpenAI(api_key=settings.openai_api_key)
    app.state.cohere = cohere.AsyncClientV2(api_key=settings.cohere_api_key)
    yield
    # Cleanup
    await app.state.qdrant.close()
```

Never create clients per-request. Pass via `app.state` or DI container.

## 2. Batch Embedding with Rate Limiting

```python
import asyncio

class RateLimitedEmbedder:
    def __init__(self, embedder: Embedder, max_concurrent: int = 5):
        self._embedder = embedder
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def embed_batch(self, texts: list[str], batch_size: int = 50) -> list[np.ndarray]:
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            async with self._semaphore:
                vectors = await self._embedder.embed_batch(batch)
                results.extend(vectors)
        return results
```

- OpenAI: max 2048 inputs/request, respect rate limits
- BGE-M3: local model, batch by GPU memory

## 3. Concurrent Pipeline Strategy

```python
async def parallel_search(
    server_index: QdrantStore,
    tool_index: QdrantStore,
    query_vector: np.ndarray,
    top_k: int,
) -> list[SearchResult]:
    """Strategy B: parallel server + tool search with RRF fusion."""
    server_task = asyncio.create_task(
        server_index.search(query_vector, top_k=top_k)
    )
    tool_task = asyncio.create_task(
        tool_index.search(query_vector, top_k=top_k)
    )
    server_results, tool_results = await asyncio.gather(
        server_task, tool_task, return_exceptions=True
    )
    # Handle partial failures
    if isinstance(server_results, Exception):
        logger.warning(f"Server search failed: {server_results}")
        server_results = []
    if isinstance(tool_results, Exception):
        logger.warning(f"Tool search failed: {tool_results}")
        tool_results = []
    return rrf_fusion(server_results, tool_results)
```

Use `return_exceptions=True` to avoid cancelling the other task on failure.

## 4. Retry with Exponential Backoff

```python
import asyncio
from functools import wraps

def async_retry(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (httpx.HTTPStatusError, cohere.TooManyRequestsError) as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Retry {attempt+1}/{max_retries} after {delay}s: {e}")
                    await asyncio.sleep(delay)
        return wrapper
    return decorator

@async_retry(max_retries=3)
async def rerank_with_cohere(client, query: str, docs: list[str]) -> list:
    return await client.rerank(query=query, documents=docs, model="rerank-v3.5")
```

## 5. Async Resource Cleanup

```python
class PipelineContext:
    """Manages async resources for a pipeline run."""

    async def __aenter__(self):
        self.qdrant = AsyncQdrantClient(url=settings.qdrant_url)
        return self

    async def __aexit__(self, *exc):
        await self.qdrant.close()

# Usage
async with PipelineContext() as ctx:
    results = await strategy.search(ctx.qdrant, query, top_k=10)
```

## Anti-Patterns

```python
# WRONG: Sync client in async context
from qdrant_client import QdrantClient  # Use AsyncQdrantClient

# WRONG: requests in async
import requests  # Use httpx.AsyncClient

# WRONG: New client per request
async def search(query):
    client = AsyncQdrantClient(...)  # Create once, share via DI
    ...

# WRONG: Sequential when parallel is safe
r1 = await index1.search(q)  # These are independent
r2 = await index2.search(q)  # Use asyncio.gather instead
```
