"""Tests for QualityGate — validates optimization doesn't degrade quality."""

import numpy as np
import pytest

from description_optimizer.models import AnalysisReport, DimensionScore
from description_optimizer.quality_gate import QualityGate


@pytest.fixture
def gate() -> QualityGate:
    # Non-default strict mode: allow_geo_decrease=False for testing GEO blocking behavior
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
                "fluency": 0.1,
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
                "fluency": 0.4,
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
                "fluency": 0.4,
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
                "fluency": 0.1,
                "stats": 0.0,
                "precision": 0.2,
            },
        )
        result = gate.check_geo_score(before, after)
        assert result.passed is False
        assert "decreased" in result.reason.lower()

    def test_default_allows_geo_decrease(self) -> None:
        """Default QualityGate allows GEO decrease (diagnostic only)."""
        default_gate = QualityGate(min_similarity=0.85)
        before = _make_report(
            "s::t",
            "old",
            {
                "clarity": 0.7,
                "disambiguation": 0.6,
                "parameter_coverage": 0.5,
                "fluency": 0.4,
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
                "fluency": 0.1,
                "stats": 0.0,
                "precision": 0.2,
            },
        )
        result = default_gate.check_geo_score(before, after)
        assert result.passed is True
        assert "diagnostic" in result.reason.lower()

    def test_pass_when_equal(self, gate: QualityGate) -> None:
        scores = {
            "clarity": 0.5,
            "disambiguation": 0.5,
            "parameter_coverage": 0.5,
            "fluency": 0.5,
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
                "fluency": 0.1,
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
                "fluency": 0.4,
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
                "fluency": 0.4,
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
                "fluency": 0.1,
                "stats": 0.0,
                "precision": 0.1,
            },
        )
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.95, 0.1, 0.05])
        result = gate.evaluate(before, after, vec_a, vec_b)
        assert result.passed is False


class TestFullEvaluateGEODiagnostic:
    """Test that evaluate() passes with default settings even when GEO decreases."""

    def test_evaluate_passes_with_geo_decrease_default(self) -> None:
        """Default gate treats GEO as diagnostic — evaluate passes despite GEO drop."""
        default_gate = QualityGate(min_similarity=0.85)
        before = _make_report(
            "s::t",
            "old",
            {
                "clarity": 0.7,
                "disambiguation": 0.6,
                "parameter_coverage": 0.5,
                "fluency": 0.4,
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
                "fluency": 0.1,
                "stats": 0.0,
                "precision": 0.2,
            },
        )
        # High-similarity vectors so similarity gate passes
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.95, 0.1, 0.05])
        result = default_gate.evaluate(before, after, vec_a, vec_b)
        assert result.passed is True
        assert result.geo_result.passed is True
        assert "diagnostic" in result.geo_result.reason.lower()


class TestHallucinationGate:
    def test_hallucination_gate_catches_fake_params(self, gate: QualityGate) -> None:
        schema = {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "id": {"type": "string"},
            },
        }
        # Optimized description mentions "query" and "limit" — not in schema
        optimized = (
            "Deletes a comment. Accepts a required `query` string and optional `limit` integer."
        )
        result = gate.check_hallucinated_params(optimized, schema)
        assert not result.passed
        assert "query" in result.reason or "limit" in result.reason

    def test_hallucination_gate_passes_with_real_params(self, gate: QualityGate) -> None:
        schema = {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File ID"},
                "id": {"type": "string", "description": "Comment ID"},
            },
        }
        optimized = "Deletes a comment. Requires `file` (File ID) and `id` (Comment ID) parameters."
        result = gate.check_hallucinated_params(optimized, schema)
        assert result.passed

    def test_hallucination_gate_skips_when_no_schema(self, gate: QualityGate) -> None:
        result = gate.check_hallucinated_params("Any description", None)
        assert result.passed
        assert "no schema" in result.reason.lower()

    def test_hallucination_gate_no_backtick_params(self, gate: QualityGate) -> None:
        """If optimized has no backtick params, gate passes (nothing to verify)."""
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        result = gate.check_hallucinated_params("A simple tool that does things.", schema)
        assert result.passed


class TestInfoPreservationGate:
    def test_info_preservation_catches_lost_numbers(self) -> None:
        gate = QualityGate()
        original = "Searches across 50,000+ packages with 99.9% uptime."
        optimized = "Searches for packages in the registry."
        result = gate.check_info_preservation(original, optimized)
        assert not result.passed
        assert "50,000" in result.reason or "99.9" in result.reason

    def test_info_preservation_passes_when_numbers_kept(self) -> None:
        gate = QualityGate()
        original = "Returns up to 100 results per query."
        optimized = "Returns up to 100 results per query. Use for data retrieval."
        result = gate.check_info_preservation(original, optimized)
        assert result.passed

    def test_info_preservation_no_numbers_passes(self) -> None:
        gate = QualityGate()
        original = "Deletes a comment from a file."
        optimized = "Deletes a comment from a file in Slack."
        result = gate.check_info_preservation(original, optimized)
        assert result.passed

    def test_info_preservation_catches_lost_tech_terms(self) -> None:
        gate = QualityGate()
        original = "Queries the PostgreSQL database via the wire protocol."
        optimized = "Queries the database for records."
        result = gate.check_info_preservation(original, optimized)
        assert not result.passed
        assert "PostgreSQL" in result.reason or "wire protocol" in result.reason


class TestRAGASFaithfulnessGate:
    """Tests for RAGAS-style faithfulness verification."""

    def test_faithful_description_passes(self) -> None:
        """Description that only contains verifiable claims passes."""
        gate = QualityGate()
        result = gate.check_faithfulness(
            original="Search the database for records",
            optimized=(
                "Search the PostgreSQL database for matching records. Accepts a `query` parameter."
            ),
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            claims=[
                {"claim": "Searches the PostgreSQL database", "supported": True},
                {"claim": "Accepts a query parameter", "supported": True},
            ],
        )
        assert result.passed

    def test_hallucinated_claim_fails(self) -> None:
        """Description with unsupported claims fails."""
        gate = QualityGate()
        result = gate.check_faithfulness(
            original="Search the database",
            optimized="Search the database. Does not handle complex queries or batch operations.",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            claims=[
                {"claim": "Searches the database", "supported": True},
                {"claim": "Does not handle complex queries", "supported": False},
                {"claim": "Does not handle batch operations", "supported": False},
            ],
        )
        assert not result.passed
        assert "unsupported" in result.reason.lower() or "hallucin" in result.reason.lower()

    def test_no_claims_passes(self) -> None:
        """Empty claims list passes (no verification possible)."""
        gate = QualityGate()
        result = gate.check_faithfulness(
            original="Search data",
            optimized="Search data",
            input_schema=None,
            claims=[],
        )
        assert result.passed

    def test_all_unsupported_fails(self) -> None:
        """All claims unsupported results in failure."""
        gate = QualityGate()
        result = gate.check_faithfulness(
            original="Get data",
            optimized="Retrieves data with millisecond latency across 50 shards.",
            input_schema=None,
            claims=[
                {"claim": "millisecond latency", "supported": False},
                {"claim": "50 shards", "supported": False},
            ],
        )
        assert not result.passed
