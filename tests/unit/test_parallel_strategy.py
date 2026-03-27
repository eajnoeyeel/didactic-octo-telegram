"""Tests for ParallelStrategy."""

from unittest.mock import AsyncMock

import numpy as np
import pytest

from models import MCPTool, SearchResult
from pipeline.parallel import ParallelStrategy
from pipeline.strategy import StrategyRegistry
from reranking.base import Reranker


def make_tool(sid: str, name: str = "tool") -> MCPTool:
    return MCPTool(server_id=sid, tool_name=name, tool_id=f"{sid}::{name}")


def make_result(sid: str, name: str = "tool", score: float = 0.9, rank: int = 1) -> SearchResult:
    return SearchResult(tool=make_tool(sid, name), score=score, rank=rank)


@pytest.fixture
def mock_embedder():
    e = AsyncMock()
    e.embed_one = AsyncMock(return_value=np.zeros(1536))
    return e


async def test_registered_as_parallel():
    assert StrategyRegistry.get("parallel") is ParallelStrategy


async def test_embeds_query_once(mock_embedder):
    ts, ss = AsyncMock(), AsyncMock()
    ss.search_server_ids = AsyncMock(return_value=[])
    ts.search = AsyncMock(return_value=[])
    s = ParallelStrategy(embedder=mock_embedder, tool_store=ts, server_store=ss)
    await s.search("hello", top_k=3)
    mock_embedder.embed_one.assert_called_once_with("hello")


async def test_searches_both_indexes(mock_embedder):
    ts, ss = AsyncMock(), AsyncMock()
    ss.search_server_ids = AsyncMock(return_value=["@srv0"])
    ts.search = AsyncMock(return_value=[make_result("@srv0")])
    s = ParallelStrategy(embedder=mock_embedder, tool_store=ts, server_store=ss)
    await s.search("hello", top_k=3)
    ss.search_server_ids.assert_called_once()
    assert ts.search.call_count >= 2  # direct + per-server


async def test_empty_servers_still_returns_direct(mock_embedder):
    ts, ss = AsyncMock(), AsyncMock()
    ss.search_server_ids = AsyncMock(return_value=[])
    ts.search = AsyncMock(return_value=[make_result("@srv0", "a")])
    s = ParallelStrategy(embedder=mock_embedder, tool_store=ts, server_store=ss)
    results = await s.search("hello", top_k=3)
    assert len(results) >= 1


async def test_reranker_applied(mock_embedder):
    ts, ss = AsyncMock(), AsyncMock()
    ss.search_server_ids = AsyncMock(return_value=[])
    ts.search = AsyncMock(return_value=[make_result("@srv0")])
    reranker = AsyncMock(spec=Reranker)
    reranker.rerank = AsyncMock(return_value=[make_result("@srv0", score=0.99)])
    s = ParallelStrategy(embedder=mock_embedder, tool_store=ts, server_store=ss, reranker=reranker)
    await s.search("hello", top_k=3)
    reranker.rerank.assert_called_once()


async def test_invalid_top_k(mock_embedder):
    s = ParallelStrategy(embedder=mock_embedder, tool_store=AsyncMock(), server_store=AsyncMock())
    with pytest.raises(ValueError, match="top_k must be positive"):
        await s.search("hello", top_k=0)
