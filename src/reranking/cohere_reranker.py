"""Cohere Rerank 3 implementation."""

import asyncio
import time

import cohere
from loguru import logger

from models import SearchResult
from reranking.base import Reranker


class CohereReranker(Reranker):
    """Reranker using Cohere Rerank 3 API.

    Includes a token-bucket rate limiter to stay within API rate limits.
    Default: 10 requests/minute (Cohere Trial key limit).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "rerank-v3.5",
        max_rpm: int = 10,
    ) -> None:
        self._client = cohere.AsyncClientV2(api_key=api_key)
        self._model = model
        self._max_rpm = max_rpm
        self._min_interval = 60.0 / max_rpm if max_rpm > 0 else 0.0
        self._last_call_time = 0.0
        logger.info(f"CohereReranker initialized with model={model!r}, max_rpm={max_rpm}")

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

        # Rate limiting: wait if we're calling too fast
        if self._min_interval > 0:
            now = time.monotonic()
            elapsed = now - self._last_call_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_call_time = time.monotonic()

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
