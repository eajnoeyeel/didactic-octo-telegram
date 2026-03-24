"""SequentialStrategy — true 2-Layer server→tool pipeline (OQ-4)."""

import numpy as np
from loguru import logger

from embedding.base import Embedder
from models import SearchResult
from pipeline.strategy import PipelineStrategy, StrategyRegistry
from retrieval.qdrant_store import QdrantStore


@StrategyRegistry.register("sequential")
class SequentialStrategy(PipelineStrategy):
    """2-Layer pipeline: server index → filtered tool search.

    Layer 1: Embed query, search mcp_servers collection → top server IDs.
    Layer 2: For each server ID, search mcp_tools filtered by server_id.
    Merge all tool results, sort by score, re-rank, return top_k.

    This is the reference implementation for OQ-4 fix (true 2-Layer).
    Compare against FlatStrategy in E0 to validate 2-Layer benefit.
    """

    def __init__(
        self,
        embedder: Embedder,
        tool_store: QdrantStore,
        server_store: QdrantStore,
        top_k_servers: int = 5,
    ) -> None:
        self.embedder = embedder
        self.tool_store = tool_store
        self.server_store = server_store
        self.top_k_servers = top_k_servers

    async def search(self, query: str, top_k: int) -> list[SearchResult]:
        """Execute 2-Layer retrieval for a query.

        Args:
            query: Natural language query.
            top_k: Number of final results to return.

        Returns:
            Top-k SearchResults merged from all candidate servers.
        """
        logger.info(f"SequentialStrategy.search: query='{query[:60]}', top_k={top_k}")

        query_vector: np.ndarray = await self.embedder.embed_one(query)

        server_ids = await self.server_store.search_server_ids(
            query_vector, top_k=self.top_k_servers
        )
        logger.debug(f"Layer 1: {len(server_ids)} candidate servers: {server_ids}")

        if not server_ids:
            logger.warning("SequentialStrategy: no servers found in Layer 1")
            return []

        all_results: list[SearchResult] = []
        for server_id in server_ids:
            results = await self.tool_store.search(
                query_vector=query_vector,
                top_k=top_k,
                server_id_filter=server_id,
            )
            all_results.extend(results)
        logger.debug(f"Layer 2: {len(all_results)} total tool candidates")

        all_results.sort(key=lambda r: r.score, reverse=True)
        return [
            SearchResult(tool=r.tool, score=r.score, rank=i + 1)
            for i, r in enumerate(all_results[:top_k])
        ]
