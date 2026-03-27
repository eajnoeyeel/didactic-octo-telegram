"""Tests for RRF score fusion."""

import pytest

from models import MCPTool, SearchResult
from retrieval.hybrid import merge_results, rrf_score


def make_tool(n: int) -> MCPTool:
    return MCPTool(server_id=f"@srv{n}", tool_name=f"tool{n}", tool_id=f"@srv{n}::tool{n}")


def make_result(n: int, score: float = 0.9, rank: int = 1) -> SearchResult:
    return SearchResult(tool=make_tool(n), score=score, rank=rank)


def test_rrf_score_rank_1_k_60():
    assert rrf_score(1, k=60) == pytest.approx(1 / 61)


def test_rrf_score_higher_rank_is_lower():
    assert rrf_score(1, k=60) > rrf_score(10, k=60)


def test_merge_duplicate_tool_sums_scores():
    list_a = [make_result(0, rank=1)]
    list_b = [make_result(0, rank=1)]
    merged = merge_results(list_a, list_b, k=60, top_n=10)
    assert len(merged) == 1
    assert merged[0].score == pytest.approx(rrf_score(1, 60) * 2)


def test_merge_disjoint_lists():
    merged = merge_results([make_result(0, rank=1)], [make_result(1, rank=1)], k=60, top_n=10)
    assert len(merged) == 2


def test_merge_top_n_truncation():
    merged = merge_results([make_result(i, rank=i + 1) for i in range(5)], k=60, top_n=3)
    assert len(merged) == 3


def test_merge_ranks_reassigned():
    merged = merge_results([make_result(0, rank=1), make_result(1, rank=2)], k=60, top_n=10)
    assert [r.rank for r in merged] == [1, 2]


def test_merge_empty():
    assert merge_results([], [], k=60, top_n=10) == []


def test_merge_preserves_tool_data():
    merged = merge_results([make_result(42, rank=1)], k=60, top_n=10)
    assert merged[0].tool.tool_id == "@srv42::tool42"
