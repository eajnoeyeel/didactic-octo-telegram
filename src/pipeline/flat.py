"""FlatStrategy — 1-Layer direct tool search (E0 baseline)."""

import numpy as np
from loguru import logger

from embedding.base import Embedder
from models import SearchResult
from pipeline.strategy import PipelineStrategy, StrategyRegistry
from retrieval.qdrant_store import QdrantStore


@StrategyRegistry.register("flat")
class FlatStrategy(PipelineStrategy):
    """1-Layer pipeline: embed query → search tool index directly.

    Used as the E0 baseline to compare against 2-Layer strategies.
    No server-level filtering — searches all tools in the collection.
    """

    def __init__(self, embedder: Embedder, tool_store: QdrantStore) -> None:
        self.embedder = embedder
        self.tool_store = tool_store

    async def search(self, query: str, top_k: int) -> list[SearchResult]:
        """Search all tools directly without server-level filtering.

        Args:
            query: Natural language query.
            top_k: Number of results to return.

        Returns:
            Top-k SearchResults ranked by vector similarity.
        """
        if top_k <= 0:
            raise ValueError(f"top_k must be positive, got {top_k}")
        logger.info(f"FlatStrategy.search: query='{query[:60]}', top_k={top_k}")
        query_vector: np.ndarray = await self.embedder.embed_one(query)
        results = await self.tool_store.search(
            query_vector=query_vector,
            top_k=top_k,
            server_id_filter=None,
        )
        logger.info(f"FlatStrategy: {len(results)} results returned")
        return results
