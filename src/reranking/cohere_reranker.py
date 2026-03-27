"""Cohere Rerank 3 implementation."""

import cohere
from loguru import logger

from models import SearchResult
from reranking.base import Reranker


class CohereReranker(Reranker):
    """Reranker using Cohere Rerank 3 API."""

    def __init__(self, api_key: str, model: str = "rerank-v3.5") -> None:
        self._client = cohere.AsyncClientV2(api_key=api_key)
        self._model = model
        logger.info(f"CohereReranker initialized with model={model!r}")

    @property
    def model(self) -> str:
        return self._model

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 3,
    ) -> list[SearchResult]:
        """Rerank search results using Cohere Rerank API.

        Args:
            query: Original search query
            results: Initial search results from embedding search
            top_k: Number of results to return after reranking

        Returns:
            Reranked and truncated list of SearchResult
        """
        if not results:
            return []

        documents = [f"{r.tool.tool_name}: {r.tool.description or ''}" for r in results]

        try:
            response = await self._client.rerank(
                model=self._model,
                query=query,
                documents=documents,
                top_n=top_k,
            )
        except Exception as e:
            logger.warning(f"Cohere rerank failed, returning original results: {e}")
            return _fallback_truncate(results, top_k)

        reranked: list[SearchResult] = []
        for rank, item in enumerate(response.results, start=1):
            original = results[item.index]
            reranked.append(
                SearchResult(
                    tool=original.tool,
                    score=item.relevance_score,
                    rank=rank,
                    reason=original.reason,
                )
            )

        return reranked


def _fallback_truncate(results: list[SearchResult], top_k: int) -> list[SearchResult]:
    """Return original results truncated to top_k with ranks preserved."""
    truncated = results[:top_k]
    return [
        SearchResult(
            tool=r.tool,
            score=r.score,
            rank=i + 1,
            reason=r.reason,
        )
        for i, r in enumerate(truncated)
    ]
