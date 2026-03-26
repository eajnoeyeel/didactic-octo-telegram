"""Tests for the evaluate() orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from evaluation.harness import DefaultEvaluator, evaluate
from evaluation.metrics import EvalResult

from .conftest import _make_entry, _make_result


class TestEvaluate:
    async def test_returns_eval_result(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(
            return_value=[
                _make_result("srv1::tool_a", 0.9, 1),
            ]
        )
        result = await evaluate(mock_strategy, [_make_entry()], top_k=10)
        assert isinstance(result, EvalResult)
        assert result.n_queries == 1
        assert result.k_used == 10

    async def test_precision_correct(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(
            return_value=[
                _make_result("srv1::tool_a", 0.9, 1),
                _make_result("srv1::tool_b", 0.5, 2),
            ]
        )
        entry = _make_entry(correct_tool_id="srv1::tool_a")
        result = await evaluate(mock_strategy, [entry], top_k=10)
        assert result.precision_at_1 == pytest.approx(1.0)
        assert result.recall_at_k == pytest.approx(1.0)
        assert result.mrr == pytest.approx(1.0)

    async def test_precision_wrong_but_in_top_k(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(
            return_value=[
                _make_result("srv1::tool_b", 0.9, 1),
                _make_result("srv1::tool_a", 0.5, 2),
            ]
        )
        entry = _make_entry(correct_tool_id="srv1::tool_a")
        result = await evaluate(mock_strategy, [entry], top_k=10)
        assert result.precision_at_1 == pytest.approx(0.0)
        assert result.recall_at_k == pytest.approx(1.0)
        assert result.mrr == pytest.approx(0.5)  # correct at rank 2

    async def test_strategy_called_once_per_query(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(return_value=[])
        entries = [_make_entry(f"gt-{i:03d}") for i in range(3)]
        await evaluate(mock_strategy, entries, top_k=10)
        assert mock_strategy.search.call_count == 3

    async def test_strategy_called_with_correct_query_and_top_k(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(return_value=[])
        entry = _make_entry(query="search github repos", correct_tool_id="srv::t")
        await evaluate(mock_strategy, [entry], top_k=5)
        mock_strategy.search.assert_called_once_with("search github repos", top_k=5)

    async def test_latency_is_non_negative(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(return_value=[])
        result = await evaluate(mock_strategy, [_make_entry()], top_k=10)
        assert result.latency_p50 >= 0.0
        assert result.latency_mean >= 0.0
        assert result.per_query[0].latency_ms >= 0.0

    async def test_empty_queries(self):
        mock_strategy = AsyncMock()
        result = await evaluate(mock_strategy, [], top_k=10)
        assert result.n_queries == 0
        assert result.n_failed == 0
        assert result.precision_at_1 == 0.0
        assert result.per_query == ()
        assert result.confusion_rate is None

    async def test_per_query_length_matches_input(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(return_value=[_make_result("srv1::tool_a", 0.9, 1)])
        entries = [_make_entry(f"gt-{i:03d}") for i in range(5)]
        result = await evaluate(mock_strategy, entries, top_k=10)
        assert len(result.per_query) == 5

    async def test_strategy_name_uses_class_name(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(return_value=[])
        result = await evaluate(mock_strategy, [_make_entry()], top_k=10)
        assert result.strategy_name == type(mock_strategy).__name__

    async def test_strategy_name_prefers_name_attribute(self):
        mock_strategy = AsyncMock()
        mock_strategy.name = "my_custom_strategy"
        mock_strategy.search = AsyncMock(return_value=[])
        result = await evaluate(mock_strategy, [_make_entry()], top_k=10)
        assert result.strategy_name == "my_custom_strategy"


class TestExceptionIsolation:
    async def test_failed_query_is_skipped(self):
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(side_effect=RuntimeError("network timeout"))
        result = await evaluate(mock_strategy, [_make_entry()], top_k=10)
        assert result.n_queries == 1
        assert result.n_failed == 1
        assert len(result.per_query) == 0
        assert result.precision_at_1 == 0.0

    async def test_partial_failure(self):
        """One query fails, one succeeds — only successful query contributes to metrics."""
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(
            side_effect=[
                RuntimeError("timeout"),
                [_make_result("srv1::tool_a", 0.9, 1)],
            ]
        )
        entries = [_make_entry("gt-001"), _make_entry("gt-002")]
        result = await evaluate(mock_strategy, entries, top_k=10)
        assert result.n_queries == 2
        assert result.n_failed == 1
        assert len(result.per_query) == 1
        assert result.precision_at_1 == pytest.approx(1.0)


class TestDefaultEvaluator:
    async def test_is_evaluator_subclass(self):
        from evaluation.evaluator import Evaluator

        assert issubclass(DefaultEvaluator, Evaluator)

    async def test_custom_gap_threshold(self):
        evaluator = DefaultEvaluator(gap_threshold=0.25)
        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(return_value=[_make_result("srv1::tool_a", 0.9, 1)])
        result = await evaluator.evaluate(mock_strategy, [_make_entry()], top_k=10)
        assert isinstance(result, EvalResult)
