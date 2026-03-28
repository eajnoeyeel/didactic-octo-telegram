"""Edge case tests for QualityGate — boundary condition verification."""

import math

import numpy as np

from description_optimizer.models import AnalysisReport, DimensionScore
from description_optimizer.quality_gate import QualityGate

_DIMS = [
    "clarity",
    "disambiguation",
    "parameter_coverage",
    "boundary",
    "stats",
    "precision",
]


def _make_report(geo_uniform: float) -> AnalysisReport:
    return AnalysisReport(
        tool_id="s::t",
        original_description="test",
        dimension_scores=[
            DimensionScore(dimension=d, score=geo_uniform, explanation="test") for d in _DIMS
        ],
    )


class TestGEOScoreBoundary:
    """Verify check_geo_score behaves correctly at numeric boundaries."""

    def test_epsilon_decrease_fails(self) -> None:
        """A tiny GEO score decrease (0.5 -> 0.4999) must fail."""
        gate = QualityGate()
        before = _make_report(0.5)
        after = _make_report(0.4999)
        result = gate.check_geo_score(before, after)
        assert not result.passed

    def test_zero_to_zero_passes(self) -> None:
        """Both scores at 0.0: no decrease, must pass."""
        gate = QualityGate()
        before = _make_report(0.0)
        after = _make_report(0.0)
        result = gate.check_geo_score(before, after)
        assert result.passed

    def test_one_to_one_passes(self) -> None:
        """Both scores at 1.0 (perfect): maintained, must pass."""
        gate = QualityGate()
        before = _make_report(1.0)
        after = _make_report(1.0)
        result = gate.check_geo_score(before, after)
        assert result.passed

    def test_allow_geo_decrease_flag(self) -> None:
        """With allow_geo_decrease=True, a large GEO decrease (0.8 -> 0.2) passes."""
        gate = QualityGate(allow_geo_decrease=True)
        before = _make_report(0.8)
        after = _make_report(0.2)
        result = gate.check_geo_score(before, after)
        assert result.passed


class TestSemanticSimilarityBoundary:
    """Verify check_semantic_similarity behaves correctly at boundary conditions."""

    def test_exactly_at_threshold(self) -> None:
        """Cosine similarity exactly equal to 0.85 must pass."""
        gate = QualityGate(min_similarity=0.85)
        # Construct two unit vectors with cosine similarity exactly 0.85.
        # vec_b is rotated from vec_a by angle = arccos(0.85).
        angle = math.acos(0.85)
        vec_a = np.array([1.0, 0.0])
        vec_b = np.array([math.cos(angle), math.sin(angle)])
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed
        assert result.similarity is not None
        assert abs(result.similarity - 0.85) < 1e-9

    def test_just_below_threshold(self) -> None:
        """Cosine similarity just below 0.85 (~0.849) must fail."""
        gate = QualityGate(min_similarity=0.85)
        angle = math.acos(0.849)
        vec_a = np.array([1.0, 0.0])
        vec_b = np.array([math.cos(angle), math.sin(angle)])
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert not result.passed
        assert result.similarity is not None
        assert result.similarity < 0.85

    def test_zero_vector_first(self) -> None:
        """Zero-norm first vector must fail with similarity=0.0."""
        gate = QualityGate()
        vec_zero = np.zeros(3)
        vec_b = np.array([1.0, 0.0, 0.0])
        result = gate.check_semantic_similarity(vec_zero, vec_b)
        assert not result.passed
        assert result.similarity == 0.0

    def test_zero_vector_second(self) -> None:
        """Zero-norm second vector must fail with similarity=0.0."""
        gate = QualityGate()
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_zero = np.zeros(3)
        result = gate.check_semantic_similarity(vec_a, vec_zero)
        assert not result.passed
        assert result.similarity == 0.0

    def test_opposite_vectors(self) -> None:
        """Opposite vectors ([1,0] vs [-1,0]) must fail with similarity ~= -1.0."""
        gate = QualityGate()
        vec_a = np.array([1.0, 0.0])
        vec_b = np.array([-1.0, 0.0])
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert not result.passed
        assert result.similarity is not None
        assert abs(result.similarity - (-1.0)) < 1e-9

    def test_high_dimensional_vectors(self) -> None:
        """1536-dim similar vectors must pass with similarity in [0.9, 1.0]."""
        gate = QualityGate()
        rng = np.random.default_rng(42)
        vec_a = rng.standard_normal(1536)
        # Introduce a small perturbation to keep similarity high but < 1.0
        noise = rng.standard_normal(1536) * 0.1
        vec_b = vec_a + noise
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed
        assert result.similarity is not None
        assert 0.9 <= result.similarity <= 1.0

    def test_custom_threshold(self) -> None:
        """With min_similarity=0.5, a cosine similarity of 0.6 must pass."""
        gate = QualityGate(min_similarity=0.5)
        angle = math.acos(0.6)
        vec_a = np.array([1.0, 0.0])
        vec_b = np.array([math.cos(angle), math.sin(angle)])
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed
        assert result.similarity is not None
        assert result.similarity >= 0.5


class TestFullGateResultReason:
    """Verify the reason property on FullGateResult."""

    def test_both_pass_reason(self) -> None:
        """When all gates pass, reason must contain 'All gates passed'."""
        gate = QualityGate()
        before = _make_report(0.5)
        after = _make_report(0.6)
        vec_a = np.array([1.0, 0.0])
        vec_b = np.array([1.0, 0.0])
        full_result = gate.evaluate(before, after, vec_a, vec_b)
        assert full_result.passed
        assert "All gates passed" in full_result.reason

    def test_both_fail_reason(self) -> None:
        """When both gates fail, reason must mention 'GEO' and 'Similarity'."""
        gate = QualityGate()
        before = _make_report(0.8)
        after = _make_report(0.2)  # GEO decrease
        vec_a = np.array([1.0, 0.0])
        vec_b = np.array([-1.0, 0.0])  # opposite → similarity -1.0, below 0.85
        full_result = gate.evaluate(before, after, vec_a, vec_b)
        assert not full_result.passed
        assert "GEO" in full_result.reason
        assert "Similarity" in full_result.reason
