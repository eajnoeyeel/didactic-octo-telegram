"""Tests for FlatStrategy — 1-Layer direct tool search."""

from unittest.mock import AsyncMock

import numpy as np
import pytest

from models import MCPTool, SearchResult
from pipeline.flat import FlatStrategy
from pipeline.strategy import StrategyRegistry


def make_tool(n: int = 0) -> MCPTool:
    return MCPTool(
        server_id=f"@srv{n}",
        tool_name=f"tool{n}",
        tool_id=f"@srv{n}::tool{n}",
    )


def make_search_result(n: int = 0, score: float = 0.9) -> SearchResult:
    return SearchResult(tool=make_tool(n), score=score, rank=n + 1)


@pytest.fixture
def mock_embedder():
    embedder = AsyncMock()
    embedder.embed_one = AsyncMock(return_value=np.zeros(1536))
    return embedder


@pytest.fixture
def mock_tool_store():
    store = AsyncMock()
    store.search = AsyncMock(return_value=[make_search_result(0), make_search_result(1, 0.8)])
    return store


class TestFlatStrategy:
    async def test_search_embeds_query(self, mock_embedder, mock_tool_store):
        strategy = FlatStrategy(embedder=mock_embedder, tool_store=mock_tool_store)
        await strategy.search("find a github tool", top_k=3)
        mock_embedder.embed_one.assert_called_once_with("find a github tool")

    async def test_search_calls_tool_store_with_query_vector(self, mock_embedder, mock_tool_store):
        strategy = FlatStrategy(embedder=mock_embedder, tool_store=mock_tool_store)
        await strategy.search("test query", top_k=5)
        mock_tool_store.search.assert_called_once()
        call_kwargs = mock_tool_store.search.call_args
        assert call_kwargs.kwargs["top_k"] == 5

    async def test_search_returns_results_from_store(self, mock_embedder, mock_tool_store):
        strategy = FlatStrategy(embedder=mock_embedder, tool_store=mock_tool_store)
        results = await strategy.search("test", top_k=3)
        assert len(results) == 2
        assert results[0].score == 0.9

    async def test_search_no_server_filter(self, mock_embedder, mock_tool_store):
        """FlatStrategy must NOT apply any server_id filter."""
        strategy = FlatStrategy(embedder=mock_embedder, tool_store=mock_tool_store)
        await strategy.search("test", top_k=3)
        call_kwargs = mock_tool_store.search.call_args.kwargs
        assert call_kwargs.get("server_id_filter") is None

    def test_registered_as_flat(self):
        assert "flat" in StrategyRegistry.list_strategies()
        assert StrategyRegistry.get("flat") is FlatStrategy
