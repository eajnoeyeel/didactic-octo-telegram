"""Unit tests for evaluation metric functions."""

from __future__ import annotations

import math

import pytest

from evaluation.metrics import (
    EvalResult,
    PerQueryResult,
    compute_confusion_rate,
    compute_ece,
    compute_latency_stats,
    compute_mrr,
    compute_ndcg_at_5,
    compute_precision_at_1,
    compute_recall_at_k,
)
from models import GroundTruthEntry, MCPTool, SearchResult


class TestDataclasses:
    def test_per_query_result_fields(self):
        r = PerQueryResult(
            query_id="gt-001",
            top_1_correct=True,
            in_top_k=True,
            rank_of_correct=1,
            confidence=0.9,
            latency_ms=42.5,
            retrieved_tool_ids=["srv::a", "srv::b"],
        )
        assert r.query_id == "gt-001"
        assert r.top_1_correct is True
        assert r.rank_of_correct == 1
        assert r.confidence == 0.9
        assert r.latency_ms == 42.5
        assert r.retrieved_tool_ids == ["srv::a", "srv::b"]

    def test_eval_result_defaults(self):
        r = EvalResult(
            strategy_name="FlatStrategy",
            n_queries=10,
            k_used=10,
            precision_at_1=0.6,
            recall_at_k=0.8,
            mrr=0.7,
            ndcg_at_5=0.75,
            confusion_rate=0.3,
            ece=0.1,
            latency_p50=50.0,
            latency_p95=120.0,
            latency_p99=200.0,
            latency_mean=60.0,
        )
        assert r.strategy_name == "FlatStrategy"
        assert r.precision_at_1 == 0.6
        assert r.per_query == []  # default empty list


# ── Shared helpers ──────────────────────────────────────────────────────────


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


def make_gt(
    correct_tool_id: str,
    alternative_tools: list[str] | None = None,
) -> GroundTruthEntry:
    server_id = correct_tool_id.split("::")[0]
    return GroundTruthEntry(
        query_id="gt-test-001",
        query="test query",
        correct_server_id=server_id,
        correct_tool_id=correct_tool_id,
        difficulty="easy",
        category="general",
        ambiguity="low",
        source="manual_seed",
        manually_verified=True,
        author="test",
        created_at="2026-03-26",
        alternative_tools=alternative_tools,
    )


def make_pq(
    query_id: str = "q1",
    top_1_correct: bool = True,
    in_top_k: bool = True,
    rank_of_correct: int | None = 1,
    confidence: float = 0.9,
    retrieved_tool_ids: list[str] | None = None,
) -> PerQueryResult:
    return PerQueryResult(
        query_id=query_id,
        top_1_correct=top_1_correct,
        in_top_k=in_top_k,
        rank_of_correct=rank_of_correct,
        confidence=confidence,
        latency_ms=10.0,
        retrieved_tool_ids=retrieved_tool_ids or ["srv::a"],
    )


# ── Rank-based metrics ───────────────────────────────────────────────────────


class TestPrecisionAt1:
    def test_all_correct(self):
        assert compute_precision_at_1([make_pq(top_1_correct=True)]) == 1.0

    def test_all_wrong(self):
        assert compute_precision_at_1([make_pq(top_1_correct=False, rank_of_correct=2)]) == 0.0

    def test_mixed(self):
        pqs = [make_pq(top_1_correct=True), make_pq(top_1_correct=False, rank_of_correct=None)]
        assert compute_precision_at_1(pqs) == pytest.approx(0.5)

    def test_empty(self):
        assert compute_precision_at_1([]) == 0.0


class TestRecallAtK:
    def test_correct_in_top_k(self):
        pq = make_pq(top_1_correct=False, in_top_k=True, rank_of_correct=3)
        assert compute_recall_at_k([pq]) == 1.0

    def test_correct_not_in_top_k(self):
        pq = make_pq(top_1_correct=False, in_top_k=False, rank_of_correct=None)
        assert compute_recall_at_k([pq]) == 0.0

    def test_empty(self):
        assert compute_recall_at_k([]) == 0.0


class TestMRR:
    def test_correct_at_rank_1(self):
        assert compute_mrr([make_pq(rank_of_correct=1)]) == pytest.approx(1.0)

    def test_correct_at_rank_2(self):
        assert compute_mrr([make_pq(top_1_correct=False, rank_of_correct=2)]) == pytest.approx(0.5)

    def test_not_found(self):
        pq = make_pq(top_1_correct=False, in_top_k=False, rank_of_correct=None)
        assert compute_mrr([pq]) == pytest.approx(0.0)

    def test_mixed(self):
        # (1/1 + 1/4) / 2 = 0.625
        pqs = [make_pq(rank_of_correct=1), make_pq(top_1_correct=False, rank_of_correct=4)]
        assert compute_mrr(pqs) == pytest.approx(0.625)

    def test_empty(self):
        assert compute_mrr([]) == 0.0


class TestNDCGAt5:
    def test_correct_at_rank_1_no_alternatives(self):
        results = [make_result("srv::a", 0.9, 1), make_result("srv::b", 0.5, 2)]
        entry = make_gt("srv::a")
        # DCG = 2/log2(2) = 2.0; IDCG = 2.0; NDCG = 1.0
        assert compute_ndcg_at_5(results, entry) == pytest.approx(1.0)

    def test_correct_at_rank_2(self):
        results = [make_result("srv::b", 0.9, 1), make_result("srv::a", 0.8, 2)]
        entry = make_gt("srv::a")
        # DCG = 0 + 2/log2(3); IDCG = 2/log2(2) = 2.0
        expected = (2.0 / math.log2(3)) / 2.0
        assert compute_ndcg_at_5(results, entry) == pytest.approx(expected)

    def test_alternative_at_rank_1(self):
        results = [make_result("srv::alt", 0.9, 1), make_result("srv::a", 0.8, 2)]
        entry = make_gt("srv::a", alternative_tools=["srv::alt"])
        # DCG = 1/log2(2) + 2/log2(3); IDCG = 2/log2(2) + 1/log2(3)
        dcg = 1.0 / math.log2(2) + 2.0 / math.log2(3)
        idcg = 2.0 / math.log2(2) + 1.0 / math.log2(3)
        assert compute_ndcg_at_5(results, entry) == pytest.approx(dcg / idcg)

    def test_not_found_returns_zero(self):
        results = [make_result("srv::b", 0.9, 1)]
        entry = make_gt("srv::a")
        assert compute_ndcg_at_5(results, entry) == pytest.approx(0.0)

    def test_empty_results_returns_zero(self):
        assert compute_ndcg_at_5([], make_gt("srv::a")) == pytest.approx(0.0)


# ── Statistical metrics ──────────────────────────────────────────────────────


class TestConfusionRate:
    def test_all_correct_returns_nan(self):
        result = compute_confusion_rate([make_pq(top_1_correct=True)])
        assert math.isnan(result)

    def test_empty_returns_nan(self):
        assert math.isnan(compute_confusion_rate([]))

    def test_wrong_but_in_top_k_is_confusion(self):
        pqs = [make_pq(top_1_correct=False, in_top_k=True, rank_of_correct=3)]
        assert compute_confusion_rate(pqs) == pytest.approx(1.0)

    def test_wrong_and_not_in_top_k_is_miss(self):
        pqs = [make_pq(top_1_correct=False, in_top_k=False, rank_of_correct=None)]
        assert compute_confusion_rate(pqs) == pytest.approx(0.0)

    def test_half_confusion_half_miss(self):
        pqs = [
            make_pq(top_1_correct=True),  # correct — excluded from errors
            make_pq(top_1_correct=False, in_top_k=True, rank_of_correct=2),  # confusion
            make_pq(top_1_correct=False, in_top_k=False, rank_of_correct=None),  # miss
        ]
        assert compute_confusion_rate(pqs) == pytest.approx(0.5)


class TestECE:
    def test_high_confidence_all_correct_low_ece(self):
        confidences = [0.9, 0.85, 0.92, 0.88, 0.91]
        correct = [True, True, True, True, True]
        assert compute_ece(confidences, correct, n_bins=5) < 0.2

    def test_high_confidence_all_wrong_high_ece(self):
        confidences = [0.95, 0.90, 0.95, 0.90, 0.95]
        correct = [False, False, False, False, False]
        assert compute_ece(confidences, correct, n_bins=5) > 0.5

    def test_empty_returns_zero(self):
        assert compute_ece([], [], n_bins=10) == 0.0

    def test_single_item(self):
        # One item in bin [0.7, 0.8): acc=1.0, conf=0.75 → ECE = |1.0 - 0.75| = 0.25
        ece = compute_ece([0.75], [True], n_bins=10)
        assert ece == pytest.approx(0.25)


class TestLatencyStats:
    def test_basic_percentiles(self):
        latencies = list(range(10, 110, 10))  # [10, 20, ..., 100]
        p50, p95, p99, mean = compute_latency_stats(latencies)
        assert p50 == pytest.approx(55.0)
        assert mean == pytest.approx(55.0)
        assert p95 > p50
        assert p99 >= p95

    def test_single_value(self):
        p50, p95, p99, mean = compute_latency_stats([42.0])
        assert p50 == pytest.approx(42.0)
        assert p95 == pytest.approx(42.0)
        assert p99 == pytest.approx(42.0)
        assert mean == pytest.approx(42.0)

    def test_empty_returns_all_zeros(self):
        assert compute_latency_stats([]) == (0.0, 0.0, 0.0, 0.0)
