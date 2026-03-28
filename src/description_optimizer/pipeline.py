"""Orchestrates the description optimization pipeline.

Flow: analyze -> (skip if high GEO) -> optimize -> re-analyze -> gate -> result
"""

from loguru import logger

from description_optimizer.analyzer.base import DescriptionAnalyzer
from description_optimizer.models import OptimizationStatus, OptimizedDescription
from description_optimizer.optimizer.base import DescriptionOptimizer
from description_optimizer.quality_gate import QualityGate
from embedding.base import Embedder


class OptimizationPipeline:
    """End-to-end description optimization: analyze -> optimize -> validate."""

    def __init__(
        self,
        analyzer: DescriptionAnalyzer,
        optimizer: DescriptionOptimizer,
        embedder: Embedder,
        gate: QualityGate,
        skip_threshold: float = 0.75,
    ) -> None:
        self._analyzer = analyzer
        self._optimizer = optimizer
        self._embedder = embedder
        self._gate = gate
        self._skip_threshold = skip_threshold

    async def run(self, tool_id: str, description: str | None) -> OptimizedDescription:
        """Run the full optimization pipeline for a single tool.

        Args:
            tool_id: Tool ID (server_id::tool_name).
            description: Original description (may be None/empty).

        Returns:
            OptimizedDescription with status indicating outcome.
        """
        desc = description or ""

        # Phase 1: Analyze original
        report_before = await self._analyzer.analyze(tool_id, desc)
        logger.info(f"Analyzed {tool_id}: GEO={report_before.geo_score:.3f}")

        # Skip if already high quality
        if report_before.geo_score >= self._skip_threshold:
            logger.info(
                f"Skipping {tool_id}: GEO={report_before.geo_score:.3f} >= {self._skip_threshold}"
            )
            return OptimizedDescription(
                tool_id=tool_id,
                original_description=desc,
                optimized_description=desc,
                search_description=desc,
                geo_score_before=report_before.geo_score,
                geo_score_after=report_before.geo_score,
                status=OptimizationStatus.SKIPPED,
                skip_reason=(
                    f"GEO score {report_before.geo_score:.3f} "
                    f"already above threshold {self._skip_threshold}"
                ),
            )

        # Phase 2: Optimize
        try:
            optimized = await self._optimizer.optimize(report_before)
        except Exception as e:
            logger.error(f"Optimization failed for {tool_id}: {e}")
            return OptimizedDescription(
                tool_id=tool_id,
                original_description=desc,
                optimized_description=desc,
                search_description=desc,
                geo_score_before=report_before.geo_score,
                geo_score_after=report_before.geo_score,
                status=OptimizationStatus.FAILED,
                skip_reason=f"Optimization error: {e}",
            )

        optimized_desc = optimized["optimized_description"]
        search_desc = optimized["search_description"]

        # Phase 3: Re-analyze optimized description
        report_after = await self._analyzer.analyze(tool_id, optimized_desc)

        # Phase 4: Compute embeddings for semantic similarity
        vec_before = await self._embedder.embed_one(desc)
        vec_after = await self._embedder.embed_one(optimized_desc)

        # Phase 5: Quality Gate
        gate_result = self._gate.evaluate(report_before, report_after, vec_before, vec_after)

        if not gate_result.passed:
            logger.warning(f"Gate rejected for {tool_id}: {gate_result.reason}")
            return OptimizedDescription(
                tool_id=tool_id,
                original_description=desc,
                optimized_description=desc,
                search_description=desc,
                geo_score_before=report_before.geo_score,
                geo_score_after=report_after.geo_score,
                status=OptimizationStatus.GATE_REJECTED,
                skip_reason=gate_result.reason,
            )

        logger.info(
            f"Optimization accepted for {tool_id}: "
            f"GEO {report_before.geo_score:.3f} -> {report_after.geo_score:.3f}"
        )

        return OptimizedDescription(
            tool_id=tool_id,
            original_description=desc,
            optimized_description=optimized_desc,
            search_description=search_desc,
            geo_score_before=report_before.geo_score,
            geo_score_after=report_after.geo_score,
            status=OptimizationStatus.SUCCESS,
        )

    async def run_batch(self, tools: list[tuple[str, str | None]]) -> list[OptimizedDescription]:
        """Run optimization for a batch of tools.

        Args:
            tools: List of (tool_id, description) tuples.

        Returns:
            List of OptimizedDescription results.
        """
        results: list[OptimizedDescription] = []
        for tool_id, desc in tools:
            result = await self.run(tool_id, desc)
            results.append(result)
        return results
