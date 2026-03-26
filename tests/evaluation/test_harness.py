"""Tests for the evaluate() orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from evaluation.harness import evaluate
from evaluation.metrics import EvalResult
from models import GroundTruthEntry, MCPTool, SearchResult


def make_tool(tool_id: str) -> MCPTool:
    server_id, tool_name = tool_id.split("::", 1)
    return MCPTool(
        tool_id=tool_id,
        server_id=server_id,
        tool_name=tool_name,
        description=f"Description for {tool_name}",
    )


def make_result(tool_id: str, score: float, rank: int) -> SearchResult:
    return SearchResult(tool=make_tool(tool_id), score=score, rank=rank)


def make_entry(
    query_id: str = "gt-test-001",
    correct_tool_id: str = "srv1::tool_a",
    query: str = "find tool a",
) -> GroundTruthEntry:
    server_id = correct_tool_id.split("::")[0]
    return GroundTruthEntry(
        query_id=query_id,
        query=query,
        correct_server_id=server_id,
        correct_tool_id=correct_tool_id,
        difficulty="easy",
        category="general",
        ambiguity="low",
        source="manual_seed",
        manually_verified=True,
        author="test",
        created_at="2026-03-26",
        alternative_tools=None,
    )


class TestEvaluate:
    async def test_returns_eval_result(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(
            return_value=[
                make_result("srv1::tool_a", 0.9, 1),
            ]
        )
        result = await evaluate(mock_strategy, [make_entry()], top_k=10)
        assert isinstance(result, EvalResult)
        assert result.n_queries == 1
        assert result.k_used == 10

    async def test_precision_correct(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(
            return_value=[
                make_result("srv1::tool_a", 0.9, 1),
                make_result("srv1::tool_b", 0.5, 2),
            ]
        )
        entry = make_entry(correct_tool_id="srv1::tool_a")
        result = await evaluate(mock_strategy, [entry], top_k=10)
        assert result.precision_at_1 == pytest.approx(1.0)
        assert result.recall_at_k == pytest.approx(1.0)
        assert result.mrr == pytest.approx(1.0)

    async def test_precision_wrong_but_in_top_k(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(
            return_value=[
                make_result("srv1::tool_b", 0.9, 1),
                make_result("srv1::tool_a", 0.5, 2),
            ]
        )
        entry = make_entry(correct_tool_id="srv1::tool_a")
        result = await evaluate(mock_strategy, [entry], top_k=10)
        assert result.precision_at_1 == pytest.approx(0.0)
        assert result.recall_at_k == pytest.approx(1.0)
        assert result.mrr == pytest.approx(0.5)  # correct at rank 2

    async def test_strategy_called_once_per_query(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(return_value=[])
        entries = [make_entry(f"gt-{i:03d}") for i in range(3)]
        await evaluate(mock_strategy, entries, top_k=10)
        assert mock_strategy.search.call_count == 3

    async def test_strategy_called_with_correct_query_and_top_k(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(return_value=[])
        entry = make_entry(query="search github repos", correct_tool_id="srv::t")
        await evaluate(mock_strategy, [entry], top_k=5)
        mock_strategy.search.assert_called_once_with("search github repos", top_k=5)

    async def test_latency_is_non_negative(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(return_value=[])
        result = await evaluate(mock_strategy, [make_entry()], top_k=10)
        assert result.latency_p50 >= 0.0
        assert result.latency_mean >= 0.0
        assert result.per_query[0].latency_ms >= 0.0

    async def test_empty_queries(self):
        mock_strategy = AsyncMock()
        result = await evaluate(mock_strategy, [], top_k=10)
        assert result.n_queries == 0
        assert result.precision_at_1 == 0.0
        assert result.per_query == []

    async def test_per_query_length_matches_input(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(return_value=[make_result("srv1::tool_a", 0.9, 1)])
        entries = [make_entry(f"gt-{i:03d}") for i in range(5)]
        result = await evaluate(mock_strategy, entries, top_k=10)
        assert len(result.per_query) == 5

    async def test_strategy_name_is_class_name(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(return_value=[])
        result = await evaluate(mock_strategy, [make_entry()], top_k=10)
        assert result.strategy_name == type(mock_strategy).__name__
