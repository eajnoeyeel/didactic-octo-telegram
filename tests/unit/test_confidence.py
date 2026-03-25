"""Tests for gap-based confidence branching."""

import pytest

from models import MCPTool, SearchResult
from pipeline.confidence import compute_confidence


def make_result(score: float, rank: int = 1, server_id: str = "srv") -> SearchResult:
    tool = MCPTool(
        server_id=server_id,
        tool_name=f"tool_{rank}",
        tool_id=f"{server_id}::tool_{rank}",
    )
    return SearchResult(tool=tool, score=score, rank=rank)


class TestComputeConfidence:
    def test_empty_results_returns_zero_confidence_and_needs_disambiguation(self):
        confidence, needs_disambiguation = compute_confidence([])
        assert confidence == 0.0
        assert needs_disambiguation is True

    def test_single_result_returns_its_score_no_disambiguation(self):
        result = make_result(score=0.9, rank=1)
        confidence, needs_disambiguation = compute_confidence([result])
        assert confidence == pytest.approx(0.9)
        assert needs_disambiguation is False

    def test_gap_above_threshold_no_disambiguation(self):
        # gap = 0.9 - 0.7 = 0.2 > 0.15 → clear winner, no ambiguity
        results = [make_result(0.9, 1), make_result(0.7, 2)]
        confidence, needs_disambiguation = compute_confidence(results)
        assert confidence == pytest.approx(0.9)
        assert needs_disambiguation is False

    def test_gap_below_threshold_needs_disambiguation(self):
        # gap = 0.8 - 0.72 = 0.08 < 0.15 → ambiguous
        results = [make_result(0.8, 1), make_result(0.72, 2)]
        confidence, needs_disambiguation = compute_confidence(results)
        assert confidence == pytest.approx(0.8)
        assert needs_disambiguation is True

    def test_gap_exactly_at_threshold_no_disambiguation(self):
        # gap = 0.15 == 0.15 → boundary: not ambiguous (gap >= threshold)
        results = [make_result(0.9, 1), make_result(0.75, 2)]
        confidence, needs_disambiguation = compute_confidence(results)
        assert needs_disambiguation is False

    def test_custom_gap_threshold(self):
        # With threshold=0.05, gap=0.08 is now clear enough
        results = [make_result(0.8, 1), make_result(0.72, 2)]
        _, needs_disambiguation = compute_confidence(results, gap_threshold=0.05)
        assert needs_disambiguation is False

    def test_uses_top_two_only(self):
        # Only rank1 and rank2 matter for gap calculation
        results = [make_result(0.9, 1), make_result(0.5, 2), make_result(0.1, 3)]
        confidence, needs_disambiguation = compute_confidence(results)
        assert confidence == pytest.approx(0.9)
        assert needs_disambiguation is False  # gap = 0.4 > 0.15
