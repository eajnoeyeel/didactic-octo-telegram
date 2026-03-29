"""Verification tests for OptimizationPipeline error paths and boundary conditions."""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from description_optimizer.analyzer.base import DescriptionAnalyzer
from description_optimizer.models import (
    AnalysisReport,
    DimensionScore,
    OptimizationStatus,
)
from description_optimizer.optimizer.base import DescriptionOptimizer
from description_optimizer.pipeline import OptimizationPipeline
from description_optimizer.quality_gate import FullGateResult, GateResult, QualityGate
from embedding.base import Embedder

_DIMS = [
    "clarity",
    "disambiguation",
    "parameter_coverage",
    "fluency",
    "stats",
    "precision",
]


def _make_report(tool_id: str, geo_uniform: float) -> AnalysisReport:
    """Build an AnalysisReport with all 6 dimensions set to the same score."""
    return AnalysisReport(
        tool_id=tool_id,
        original_description="test description",
        dimension_scores=[
            DimensionScore(dimension=d, score=geo_uniform, explanation="test") for d in _DIMS
        ],
    )


def _build_pipeline(
    geo_before: float = 0.4,
    geo_after: float = 0.6,
    optimizer_side_effect: Exception | None = None,
    embedder_side_effect: Exception | None = None,
    gate_passed: bool = True,
    skip_threshold: float = 0.75,
) -> OptimizationPipeline:
    """Factory that creates an OptimizationPipeline with configurable mock behavior.

    Args:
        geo_before: GEO score returned by the first analyze() call.
        geo_after: GEO score returned by the second analyze() call.
        optimizer_side_effect: If set, optimizer.optimize() raises this exception.
        embedder_side_effect: If set, embedder.embed_one() raises this exception.
        gate_passed: Controls whether the quality gate passes or fails.
        skip_threshold: Pipeline skip threshold.

    Returns:
        Configured OptimizationPipeline with mock dependencies.
    """
    tool_id = "server::tool"

    # Analyzer mock: returns geo_before on first call, geo_after on second
    analyzer = MagicMock(spec=DescriptionAnalyzer)
    analyzer.analyze = AsyncMock(
        side_effect=[
            _make_report(tool_id, geo_before),
            _make_report(tool_id, geo_after),
        ]
    )

    # Optimizer mock
    optimizer = MagicMock(spec=DescriptionOptimizer)
    if optimizer_side_effect is not None:
        optimizer.optimize = AsyncMock(side_effect=optimizer_side_effect)
    else:
        optimizer.optimize = AsyncMock(
            return_value={
                "optimized_description": "optimized text",
                "search_description": "search text",
            }
        )

    # Embedder mock
    embedder = MagicMock(spec=Embedder)
    if embedder_side_effect is not None:
        embedder.embed_one = AsyncMock(side_effect=embedder_side_effect)
    else:
        embedder.embed_one = AsyncMock(return_value=np.array([1.0, 0.0]))

    # Gate mock
    gate = MagicMock(spec=QualityGate)
    if gate_passed:
        gate.evaluate = MagicMock(
            return_value=FullGateResult(
                passed=True,
                geo_result=GateResult(passed=True, reason="GEO ok"),
                similarity_result=GateResult(passed=True, reason="Similarity ok"),
            )
        )
    else:
        gate.evaluate = MagicMock(
            return_value=FullGateResult(
                passed=False,
                geo_result=GateResult(passed=False, reason="GEO decreased"),
                similarity_result=GateResult(passed=False, reason="Similarity too low"),
            )
        )

    return OptimizationPipeline(
        analyzer=analyzer,
        optimizer=optimizer,
        embedder=embedder,
        gate=gate,
        skip_threshold=skip_threshold,
    )


class TestOptimizerFailure:
    """Verify optimizer exceptions are caught and return FAILED status."""

    async def test_optimizer_exception_returns_failed(self) -> None:
        """RuntimeError from optimizer returns FAILED status."""
        pipeline = _build_pipeline(
            geo_before=0.4,
            optimizer_side_effect=RuntimeError("LLM API down"),
        )
        result = await pipeline.run("server::tool", "original description")

        assert result.status == OptimizationStatus.FAILED
        assert result.skip_reason is not None
        assert "LLM API down" in result.skip_reason
        assert result.original_description == "original description"
        assert result.optimized_description == "original description"

    async def test_optimizer_json_error_returns_failed(self) -> None:
        """ValueError from optimizer → FAILED status."""
        pipeline = _build_pipeline(
            geo_before=0.4,
            optimizer_side_effect=ValueError("Missing key"),
        )
        result = await pipeline.run("server::tool", "some description")

        assert result.status == OptimizationStatus.FAILED
        assert result.skip_reason is not None
        assert "Missing key" in result.skip_reason


class TestEmbedderFailure:
    """Verify embedder exceptions propagate out of the pipeline (not caught)."""

    async def test_embedder_exception_propagates(self) -> None:
        """RuntimeError from embedder must propagate — pipeline does NOT catch it."""
        pipeline = _build_pipeline(
            geo_before=0.4,
            embedder_side_effect=RuntimeError("Embedding API error"),
        )

        with pytest.raises(RuntimeError, match="Embedding API error"):
            await pipeline.run("server::tool", "some description")


class TestSkipThreshold:
    """Verify skip logic uses >= comparison at various threshold boundaries."""

    async def test_exactly_at_threshold_skips(self) -> None:
        """GEO=0.75 with threshold=0.75 → SKIPPED (>= comparison)."""
        pipeline = _build_pipeline(geo_before=0.75, skip_threshold=0.75)
        result = await pipeline.run("server::tool", "description")

        assert result.status == OptimizationStatus.SKIPPED

    async def test_just_below_threshold_optimizes(self) -> None:
        """GEO=0.749 with threshold=0.75 → proceeds to optimization → SUCCESS."""
        pipeline = _build_pipeline(
            geo_before=0.749,
            geo_after=0.8,
            skip_threshold=0.75,
        )
        result = await pipeline.run("server::tool", "description")

        assert result.status == OptimizationStatus.SUCCESS

    async def test_threshold_zero_skips_everything(self) -> None:
        """GEO=0.0 with threshold=0.0 → SKIPPED (0.0 >= 0.0)."""
        pipeline = _build_pipeline(geo_before=0.0, skip_threshold=0.0)
        result = await pipeline.run("server::tool", "description")

        assert result.status == OptimizationStatus.SKIPPED

    async def test_threshold_one_skips_only_perfect(self) -> None:
        """GEO=0.99 with threshold=1.0 → proceeds to optimization (0.99 < 1.0) → SUCCESS."""
        pipeline = _build_pipeline(
            geo_before=0.99,
            geo_after=1.0,
            skip_threshold=1.0,
        )
        result = await pipeline.run("server::tool", "description")

        assert result.status == OptimizationStatus.SUCCESS


class TestGateRejection:
    """Verify gate rejection returns GATE_REJECTED status with original description preserved."""

    async def test_gate_rejected_preserves_original(self) -> None:
        """Gate fails → GATE_REJECTED, optimized_description and search_description == original."""
        pipeline = _build_pipeline(geo_before=0.4, geo_after=0.5, gate_passed=False)
        original = "original description text"
        result = await pipeline.run("server::tool", original)

        assert result.status == OptimizationStatus.GATE_REJECTED
        assert result.optimized_description == original
        assert result.search_description == original

    async def test_gate_rejected_has_reason(self) -> None:
        """Gate fails → skip_reason is not None."""
        pipeline = _build_pipeline(geo_before=0.4, geo_after=0.5, gate_passed=False)
        result = await pipeline.run("server::tool", "description")

        assert result.skip_reason is not None


class TestBatchEdgeCases:
    """Verify run_batch handles edge case inputs correctly."""

    async def test_empty_batch(self) -> None:
        """Empty input list → empty result list."""
        pipeline = _build_pipeline()
        results = await pipeline.run_batch([])

        assert results == []

    async def test_single_item_batch(self) -> None:
        """Single item input → result list of length 1."""
        # Need a fresh pipeline for single call (analyzer mock has 2 side effects)
        pipeline = _build_pipeline(geo_before=0.4, geo_after=0.6)
        results = await pipeline.run_batch([("server::tool", "description")])

        assert len(results) == 1
