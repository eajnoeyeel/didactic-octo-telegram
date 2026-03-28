"""Quality Gate for description optimization.

Validates that optimization:
1. Does not degrade GEO Score (no-regression)
2. Preserves semantic similarity with the original (cosine >= threshold)

Both checks must pass for the optimization to be accepted.
"""

from dataclasses import dataclass

import numpy as np
from loguru import logger

from description_optimizer.models import AnalysisReport


@dataclass(frozen=True)
class GateResult:
    """Result of a single quality gate check."""

    passed: bool
    reason: str
    similarity: float | None = None


@dataclass(frozen=True)
class FullGateResult:
    """Combined result of all quality gate checks."""

    passed: bool
    geo_result: GateResult
    similarity_result: GateResult

    @property
    def reason(self) -> str:
        if self.passed:
            return "All gates passed"
        reasons = []
        if not self.geo_result.passed:
            reasons.append(f"GEO: {self.geo_result.reason}")
        if not self.similarity_result.passed:
            reasons.append(f"Similarity: {self.similarity_result.reason}")
        return "; ".join(reasons)


class QualityGate:
    """Validates optimization quality before accepting results."""

    def __init__(
        self,
        min_similarity: float = 0.85,
        allow_geo_decrease: bool = False,
    ) -> None:
        self._min_similarity = min_similarity
        self._allow_geo_decrease = allow_geo_decrease

    def check_geo_score(self, before: AnalysisReport, after: AnalysisReport) -> GateResult:
        """Check that GEO score did not decrease after optimization."""
        if self._allow_geo_decrease:
            return GateResult(passed=True, reason="GEO decrease allowed by config")

        if after.geo_score < before.geo_score:
            return GateResult(
                passed=False,
                reason=(
                    f"GEO score decreased from {before.geo_score:.3f} to {after.geo_score:.3f}"
                ),
            )

        logger.info(
            f"GEO gate passed for {before.tool_id}: {before.geo_score:.3f} → {after.geo_score:.3f}"
        )
        return GateResult(
            passed=True,
            reason=(
                f"GEO score maintained/improved: {before.geo_score:.3f} → {after.geo_score:.3f}"
            ),
        )

    def check_semantic_similarity(
        self, vec_before: np.ndarray, vec_after: np.ndarray
    ) -> GateResult:
        """Check cosine similarity between original and optimized embeddings."""
        norm_a = np.linalg.norm(vec_before)
        norm_b = np.linalg.norm(vec_after)

        if norm_a == 0 or norm_b == 0:
            return GateResult(passed=False, reason="Zero-norm vector", similarity=0.0)

        similarity = float(np.dot(vec_before, vec_after) / (norm_a * norm_b))

        if similarity < self._min_similarity:
            return GateResult(
                passed=False,
                reason=(
                    f"Semantic similarity {similarity:.3f} below threshold {self._min_similarity}"
                ),
                similarity=similarity,
            )

        return GateResult(
            passed=True,
            reason=(f"Semantic similarity {similarity:.3f} >= {self._min_similarity}"),
            similarity=similarity,
        )

    def evaluate(
        self,
        before: AnalysisReport,
        after: AnalysisReport,
        vec_before: np.ndarray,
        vec_after: np.ndarray,
    ) -> FullGateResult:
        """Run all quality gate checks."""
        geo_result = self.check_geo_score(before, after)
        sim_result = self.check_semantic_similarity(vec_before, vec_after)

        passed = geo_result.passed and sim_result.passed

        if not passed:
            logger.warning(
                f"Quality gate FAILED for {before.tool_id}: "
                f"GEO={geo_result.passed}, Similarity={sim_result.passed}"
            )

        return FullGateResult(
            passed=passed,
            geo_result=geo_result,
            similarity_result=sim_result,
        )
