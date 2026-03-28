"""Tests for QualityGate — validates optimization doesn't degrade quality."""

import numpy as np
import pytest

from description_optimizer.models import AnalysisReport, DimensionScore
from description_optimizer.quality_gate import QualityGate


@pytest.fixture
def gate() -> QualityGate:
    return QualityGate(
        min_similarity=0.85,
        allow_geo_decrease=False,
    )


def _make_report(tool_id: str, desc: str, scores: dict[str, float]) -> AnalysisReport:
    """Helper to create an AnalysisReport with given dimension scores."""
    return AnalysisReport(
        tool_id=tool_id,
        original_description=desc,
        dimension_scores=[
            DimensionScore(dimension=dim, score=s, explanation="test") for dim, s in scores.items()
        ],
    )


class TestGeoScoreGate:
    def test_pass_when_improved(self, gate: QualityGate) -> None:
        before = _make_report(
            "s::t",
            "old",
            {
                "clarity": 0.3,
                "disambiguation": 0.2,
                "parameter_coverage": 0.3,
                "boundary": 0.1,
                "stats": 0.0,
                "precision": 0.2,
            },
        )
        after = _make_report(
            "s::t",
            "new",
            {
                "clarity": 0.7,
                "disambiguation": 0.5,
                "parameter_coverage": 0.6,
                "boundary": 0.4,
                "stats": 0.3,
                "precision": 0.5,
            },
        )
        result = gate.check_geo_score(before, after)
        assert result.passed is True

    def test_fail_when_degraded(self, gate: QualityGate) -> None:
        before = _make_report(
            "s::t",
            "old",
            {
                "clarity": 0.7,
                "disambiguation": 0.6,
                "parameter_coverage": 0.5,
                "boundary": 0.4,
                "stats": 0.3,
                "precision": 0.5,
            },
        )
        after = _make_report(
            "s::t",
            "new",
            {
                "clarity": 0.3,
                "disambiguation": 0.2,
                "parameter_coverage": 0.3,
                "boundary": 0.1,
                "stats": 0.0,
                "precision": 0.2,
            },
        )
        result = gate.check_geo_score(before, after)
        assert result.passed is False
        assert "decreased" in result.reason.lower()

    def test_pass_when_equal(self, gate: QualityGate) -> None:
        scores = {
            "clarity": 0.5,
            "disambiguation": 0.5,
            "parameter_coverage": 0.5,
            "boundary": 0.5,
            "stats": 0.5,
            "precision": 0.5,
        }
        before = _make_report("s::t", "old", scores)
        after = _make_report("s::t", "new", scores)
        result = gate.check_geo_score(before, after)
        assert result.passed is True


class TestSemanticSimilarityGate:
    def test_pass_high_similarity(self, gate: QualityGate) -> None:
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.95, 0.1, 0.05])
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed is True

    def test_fail_low_similarity(self, gate: QualityGate) -> None:
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.0, 1.0, 0.0])
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed is False

    def test_identical_vectors(self, gate: QualityGate) -> None:
        vec = np.array([0.5, 0.5, 0.5])
        result = gate.check_semantic_similarity(vec, vec)
        assert result.passed is True
        assert result.similarity == pytest.approx(1.0)


class TestFullGate:
    def test_all_pass(self, gate: QualityGate) -> None:
        before = _make_report(
            "s::t",
            "old",
            {
                "clarity": 0.3,
                "disambiguation": 0.2,
                "parameter_coverage": 0.3,
                "boundary": 0.1,
                "stats": 0.0,
                "precision": 0.2,
            },
        )
        after = _make_report(
            "s::t",
            "new improved",
            {
                "clarity": 0.7,
                "disambiguation": 0.5,
                "parameter_coverage": 0.6,
                "boundary": 0.4,
                "stats": 0.3,
                "precision": 0.5,
            },
        )
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.95, 0.1, 0.05])
        result = gate.evaluate(before, after, vec_a, vec_b)
        assert result.passed is True

    def test_fail_if_any_fails(self, gate: QualityGate) -> None:
        before = _make_report(
            "s::t",
            "old",
            {
                "clarity": 0.7,
                "disambiguation": 0.6,
                "parameter_coverage": 0.5,
                "boundary": 0.4,
                "stats": 0.3,
                "precision": 0.5,
            },
        )
        after = _make_report(
            "s::t",
            "worse",
            {
                "clarity": 0.3,
                "disambiguation": 0.2,
                "parameter_coverage": 0.2,
                "boundary": 0.1,
                "stats": 0.0,
                "precision": 0.1,
            },
        )
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.95, 0.1, 0.05])
        result = gate.evaluate(before, after, vec_a, vec_b)
        assert result.passed is False
