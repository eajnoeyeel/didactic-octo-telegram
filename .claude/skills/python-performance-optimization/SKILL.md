---
name: python-performance-optimization
description: Profile and optimize the MCP Discovery retrieval pipeline — batch embedding throughput, Qdrant search latency, Cohere reranker cost, and memory usage for large tool pools. Use when diagnosing slow pipeline performance or optimizing batch operations.
---

# Python Performance Optimization — MCP Discovery

Project-specific profiling and optimization for the retrieval pipeline. For generic Python optimization tips, Claude already knows them.

## 1. Pipeline Profiling

### py-spy (Production-safe sampling profiler)

```bash
# Profile the current baseline experiment
uv run py-spy record -o experiment.svg -- python scripts/run_e0.py

# Planned, after FastAPI app lands:
# uv run py-spy record -o profile.svg -- uvicorn src.api.main:app
```

### cProfile for specific functions

```python
import cProfile
import pstats

async def profile_pipeline():
    profiler = cProfile.Profile()
    profiler.enable()

    strategy = SequentialStrategy(qdrant=qdrant, embedder=embedder, reranker=reranker)
    results = await strategy.search("find a weather tool", top_k=3)

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    stats.print_stats(20)
```

### Latency breakdown

```python
import time

class InstrumentedStrategy(PipelineStrategy):
    async def search(self, query: str, top_k: int) -> list[SearchResult]:
        t0 = time.perf_counter()
        vector = await self.embedder.embed_one(query)
        t_embed = time.perf_counter() - t0

        t0 = time.perf_counter()
        candidates = await self.qdrant.search(vector, top_k=self.config.top_k_retrieval)
        t_search = time.perf_counter() - t0

        t0 = time.perf_counter()
        reranked = await self.reranker.rerank(query, candidates, top_k)
        t_rerank = time.perf_counter() - t0

        logger.info(f"embed={t_embed:.3f}s search={t_search:.3f}s rerank={t_rerank:.3f}s")
        return reranked
```

Typical latency targets: embed <100ms, Qdrant search <50ms, Cohere rerank <500ms.

## 2. Batch Size Tuning

### Embedding batch size

```python
# Too small → too many API calls → high latency
# Too large → OOM (BGE-M3) or API limit (OpenAI 2048)
OPTIMAL_BATCH_SIZES = {
    "openai": 500,      # API limit 2048, but 500 balances latency/throughput
    "bge-m3": 32,       # Local GPU memory dependent
}
```

### Qdrant upsert batch size

```python
# Qdrant Cloud free tier: don't send >100 points per upsert
async def upsert_batched(client, collection, points, batch_size=100):
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        await client.upsert(collection_name=collection, points=batch)
```

## 3. Embedding Cache

Avoid re-embedding the same query across experiment runs.

```python
from functools import lru_cache
import hashlib
import numpy as np

class CachedEmbedder:
    def __init__(self, embedder: Embedder, cache_dir: Path = Path("data/.embed_cache")):
        self._embedder = embedder
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    async def embed_one(self, text: str) -> np.ndarray:
        key = hashlib.sha256(text.encode()).hexdigest()[:16]
        cache_path = self._cache_dir / f"{key}.npy"
        if cache_path.exists():
            return np.load(cache_path)
        vector = await self._embedder.embed_one(text)
        np.save(cache_path, vector)
        return vector
```

## 4. Memory Optimization for Large Pools

```python
# When indexing 100+ servers × tools:
# - Use generators instead of lists for large data
# - Process in streaming batches, don't load all into memory

async def index_tools_streaming(tools_path: Path, embedder, qdrant, batch_size=50):
    batch = []
    async for tool in stream_tools_from_jsonl(tools_path):
        batch.append(tool)
        if len(batch) >= batch_size:
            texts = [build_tool_text(t) for t in batch]
            vectors = await embedder.embed_batch(texts)
            await qdrant.upsert_tools(batch, vectors)
            batch = []
    if batch:  # Final partial batch
        texts = [build_tool_text(t) for t in batch]
        vectors = await embedder.embed_batch(texts)
        await qdrant.upsert_tools(batch, vectors)
```

## 5. Experiment Run Optimization

```python
# E1-E3 share the same Ground Truth and index — don't rebuild between runs
# When `run_experiments.py` lands, prefer a `--reuse-index` style flow

# Profile experiment overhead vs actual pipeline time
# Most time should be in pipeline, not in metric calculation
```

## Key Metrics to Watch

| Metric | Target | Alert |
|--------|--------|-------|
| embed latency (single) | < 100ms | > 500ms |
| Qdrant search (top-10) | < 50ms | > 200ms |
| Cohere rerank (10 docs) | < 500ms | > 2s |
| Full pipeline (end-to-end) | < 1s | > 3s |
| Index build (50 servers) | < 5min | > 15min |
| Memory (during index build) | < 2GB | > 4GB |
