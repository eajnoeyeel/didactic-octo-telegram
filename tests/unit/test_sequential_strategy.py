"""Tests for SequentialStrategy — true 2-Layer server→tool pipeline."""

from unittest.mock import AsyncMock

import numpy as np
import pytest

from models import MCPTool, SearchResult
from pipeline.sequential import SequentialStrategy
from pipeline.strategy import StrategyRegistry
from reranking.base import Reranker


def make_tool(server_id: str, name: str = "tool") -> MCPTool:
    return MCPTool(
        server_id=server_id,
        tool_name=name,
        tool_id=f"{server_id}::{name}",
    )


def make_result(server_id: str, name: str = "tool", score: float = 0.9) -> SearchResult:
    return SearchResult(tool=make_tool(server_id, name), score=score, rank=1)


@pytest.fixture
def mock_embedder():
    embedder = AsyncMock()
    embedder.embed_one = AsyncMock(return_value=np.zeros(1536))
    return embedder


@pytest.fixture
def mock_server_store():
    store = AsyncMock()
    store.search_server_ids = AsyncMock(return_value=["srv1", "srv2"])
    return store


@pytest.fixture
def mock_tool_store():
    store = AsyncMock()
    store.search = AsyncMock(
        side_effect=[
            [make_result("srv1", "tool_a", score=0.9)],
            [make_result("srv2", "tool_b", score=0.7)],
        ]
    )
    return store


class TestSequentialStrategy:
    async def test_embeds_query_once(self, mock_embedder, mock_server_store, mock_tool_store):
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        await strategy.search("find github tool", top_k=3)
        mock_embedder.embed_one.assert_called_once_with("find github tool")

    async def test_searches_server_index_first(
        self, mock_embedder, mock_server_store, mock_tool_store
    ):
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        await strategy.search("test", top_k=3)
        mock_server_store.search_server_ids.assert_called_once()

    async def test_filters_tool_search_by_server_id(
        self, mock_embedder, mock_server_store, mock_tool_store
    ):
        """Layer 2 must filter by each server_id returned from Layer 1."""
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        await strategy.search("test", top_k=3)
        assert mock_tool_store.search.call_count == 2
        calls = mock_tool_store.search.call_args_list
        server_filters = [c.kwargs["server_id_filter"] for c in calls]
        assert "srv1" in server_filters
        assert "srv2" in server_filters

    async def test_results_sorted_by_score_descending(
        self, mock_embedder, mock_server_store, mock_tool_store
    ):
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        results = await strategy.search("test", top_k=3)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    async def test_ranks_are_reassigned_after_merge(
        self, mock_embedder, mock_server_store, mock_tool_store
    ):
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        results = await strategy.search("test", top_k=3)
        for i, r in enumerate(results):
            assert r.rank == i + 1

    async def test_top_k_limits_returned_results(
        self, mock_embedder, mock_server_store, mock_tool_store
    ):
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        results = await strategy.search("test", top_k=1)
        assert len(results) == 1

    async def test_empty_server_results_returns_empty(self, mock_embedder, mock_tool_store):
        server_store = AsyncMock()
        server_store.search_server_ids = AsyncMock(return_value=[])
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=server_store,
        )
        results = await strategy.search("test", top_k=3)
        assert results == []
        mock_tool_store.search.assert_not_called()

    async def test_invalid_top_k_raises(self, mock_embedder, mock_server_store, mock_tool_store):
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        with pytest.raises(ValueError, match="top_k must be positive"):
            await strategy.search("test", top_k=0)

    def test_registered_as_sequential(self):
        assert "sequential" in StrategyRegistry.list_strategies()
        assert StrategyRegistry.get("sequential") is SequentialStrategy


async def test_reranker_none_by_default(mock_embedder):
    strategy = SequentialStrategy(
        embedder=mock_embedder, tool_store=AsyncMock(), server_store=AsyncMock()
    )
    assert strategy.reranker is None


async def test_search_with_reranker(mock_embedder):
    server_store = AsyncMock()
    server_store.search_server_ids = AsyncMock(return_value=["@srv0"])
    tool_store = AsyncMock()
    tool_store.search = AsyncMock(
        return_value=[make_result("@srv0", "a", 0.9), make_result("@srv0", "b", 0.8)]
    )
    reranker = AsyncMock(spec=Reranker)
    reranked = [make_result("@srv0", "b", 0.95), make_result("@srv0", "a", 0.85)]
    reranker.rerank = AsyncMock(return_value=reranked)
    strategy = SequentialStrategy(
        embedder=mock_embedder,
        tool_store=tool_store,
        server_store=server_store,
        reranker=reranker,
    )
    results = await strategy.search("test query", top_k=3)
    reranker.rerank.assert_called_once()
    assert results == reranked
