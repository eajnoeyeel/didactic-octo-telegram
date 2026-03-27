"""ParallelStrategy — dual-index RRF fusion (Strategy B)."""

from __future__ import annotations

import asyncio

import numpy as np
from loguru import logger

from embedding.base import Embedder
from models import SearchResult
from pipeline.strategy import PipelineStrategy, StrategyRegistry
from reranking.base import Reranker
from retrieval.hybrid import merge_results
from retrieval.qdrant_store import QdrantStore


@StrategyRegistry.register("parallel")
class ParallelStrategy(PipelineStrategy):
    """Strategy B: parallel server + tool search with RRF fusion.

    1. Embed query once.
    2. asyncio.gather: server_store.search_server_ids + tool_store.search (direct).
    3. Per matched server: tool_store.search(server_id_filter=sid).
    4. RRF merge server-derived + direct tool results.
    5. Optional reranker.
    """

    def __init__(
        self,
        embedder: Embedder,
        tool_store: QdrantStore,
        server_store: QdrantStore,
        top_k_servers: int = 5,
        rrf_k: int = 60,
        reranker: Reranker | None = None,
    ) -> None:
        self.embedder = embedder
        self.tool_store = tool_store
        self.server_store = server_store
        self.top_k_servers = top_k_servers
        self.rrf_k = rrf_k
        self.reranker = reranker

    async def search(self, query: str, top_k: int) -> list[SearchResult]:
        """Execute dual-index parallel search with RRF fusion."""
        if top_k <= 0:
            raise ValueError(f"top_k must be positive, got {top_k}")
        logger.info(f"ParallelStrategy.search: query='{query[:60]}', top_k={top_k}")

        query_vector: np.ndarray = await self.embedder.embed_one(query)

        # Step 1: parallel server-id search + direct tool search
        server_ids, direct_results = await asyncio.gather(
            self.server_store.search_server_ids(query_vector, top_k=self.top_k_servers),
            self.tool_store.search(query_vector=query_vector, top_k=top_k, server_id_filter=None),
        )
        logger.debug(f"Parallel: {len(server_ids)} servers, {len(direct_results)} direct tools")

        # Step 2: per-server filtered tool searches
        server_derived: list[SearchResult] = []
        if server_ids:
            per_server = await asyncio.gather(
                *[
                    self.tool_store.search(
                        query_vector=query_vector,
                        top_k=top_k,
                        server_id_filter=sid,
                    )
                    for sid in server_ids
                ]
            )
            for results in per_server:
                server_derived.extend(results)

        # Step 3: RRF fusion
        merged = merge_results(server_derived, direct_results, k=self.rrf_k, top_n=top_k)

        # Step 4: optional rerank
        if self.reranker is not None:
            merged = await self.reranker.rerank(query, merged, top_k)

        logger.info(f"ParallelStrategy: {len(merged)} results returned")
        return merged
