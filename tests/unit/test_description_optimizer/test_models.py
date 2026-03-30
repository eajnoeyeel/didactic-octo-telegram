"""Tests for Description Optimizer data models."""

import pytest

from description_optimizer.models import (
    AnalysisReport,
    DimensionScore,
    OptimizationStatus,
    OptimizedDescription,
)


class TestDimensionScore:
    def test_valid_score(self) -> None:
        score = DimensionScore(dimension="clarity", score=0.8, explanation="Clear purpose")
        assert score.dimension == "clarity"
        assert score.score == 0.8
        assert score.explanation == "Clear purpose"

    def test_score_bounds_low(self) -> None:
        with pytest.raises(ValueError):
            DimensionScore(dimension="clarity", score=-0.1, explanation="test")

    def test_score_bounds_high(self) -> None:
        with pytest.raises(ValueError):
            DimensionScore(dimension="clarity", score=1.1, explanation="test")

    def test_valid_dimensions(self) -> None:
        valid = [
            "clarity",
            "disambiguation",
            "parameter_coverage",
            "fluency",
            "stats",
            "precision",
        ]
        for dim in valid:
            score = DimensionScore(dimension=dim, score=0.5, explanation="test")
            assert score.dimension == dim

    def test_invalid_dimension(self) -> None:
        with pytest.raises(ValueError):
            DimensionScore(dimension="invalid_dim", score=0.5, explanation="test")


class TestAnalysisReport:
    def test_geo_score_computation(self) -> None:
        scores = [
            DimensionScore(dimension="clarity", score=0.6, explanation="ok"),
            DimensionScore(dimension="disambiguation", score=0.8, explanation="good"),
            DimensionScore(dimension="parameter_coverage", score=0.4, explanation="weak"),
            DimensionScore(dimension="fluency", score=0.2, explanation="missing"),
            DimensionScore(dimension="stats", score=0.0, explanation="none"),
            DimensionScore(dimension="precision", score=0.5, explanation="partial"),
        ]
        report = AnalysisReport(
            tool_id="server::tool",
            original_description="A tool that does stuff",
            dimension_scores=scores,
        )
        expected_geo = (0.6 + 0.8 + 0.4 + 0.2 + 0.0 + 0.5) / 6
        assert abs(report.geo_score - expected_geo) < 1e-6

    def test_weak_dimensions(self) -> None:
        scores = [
            DimensionScore(dimension="clarity", score=0.8, explanation="good"),
            DimensionScore(dimension="disambiguation", score=0.3, explanation="weak"),
            DimensionScore(dimension="parameter_coverage", score=0.7, explanation="ok"),
            DimensionScore(dimension="fluency", score=0.1, explanation="bad"),
            DimensionScore(dimension="stats", score=0.6, explanation="ok"),
            DimensionScore(dimension="precision", score=0.5, explanation="ok"),
        ]
        report = AnalysisReport(
            tool_id="server::tool",
            original_description="test",
            dimension_scores=scores,
        )
        weak = report.weak_dimensions(threshold=0.5)
        assert set(weak) == {"disambiguation", "fluency"}

    def test_requires_six_dimensions(self) -> None:
        scores = [DimensionScore(dimension="clarity", score=0.5, explanation="test")]
        with pytest.raises(ValueError):
            AnalysisReport(
                tool_id="server::tool",
                original_description="test",
                dimension_scores=scores,
            )


class TestOptimizedDescription:
    def test_fields(self) -> None:
        opt = OptimizedDescription(
            tool_id="server::tool",
            original_description="basic tool",
            optimized_description="An advanced tool that performs X when Y",
            retrieval_description="tool X Y Z purpose disambiguation",
            geo_score_before=0.3,
            geo_score_after=0.7,
            status=OptimizationStatus.SUCCESS,
        )
        assert opt.improvement == pytest.approx(0.4)
        assert opt.status == OptimizationStatus.SUCCESS
        assert opt.retrieval_description == "tool X Y Z purpose disambiguation"

    def test_improvement_calculation(self) -> None:
        opt = OptimizedDescription(
            tool_id="server::tool",
            original_description="test",
            optimized_description="test improved",
            retrieval_description="test search",
            geo_score_before=0.5,
            geo_score_after=0.8,
            status=OptimizationStatus.SUCCESS,
        )
        assert opt.improvement == pytest.approx(0.3)

    def test_legacy_search_description_input_is_accepted(self) -> None:
        opt = OptimizedDescription(
            tool_id="server::tool",
            original_description="already great tool description",
            optimized_description="already great tool description",
            search_description="legacy search text",
            geo_score_before=0.9,
            geo_score_after=0.9,
            status=OptimizationStatus.SUCCESS,
        )
        assert opt.retrieval_description == "legacy search text"
