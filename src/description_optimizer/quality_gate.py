"""Quality Gate for description optimization.

Validates that optimization:
1. Preserves semantic similarity with the original (cosine >= threshold)
2. Does not hallucinate parameters absent from the input schema
3. Preserves key information (numbers, technical terms) from the original
4. GEO Score change is recorded as diagnostic (not blocking by default)

All blocking checks must pass for the optimization to be accepted.
"""

import re
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
    hallucination_result: GateResult | None = None
    info_preservation_result: GateResult | None = None
    faithfulness_result: GateResult | None = None

    @property
    def reason(self) -> str:
        if self.passed:
            return "All gates passed"
        reasons = []
        if not self.geo_result.passed:
            reasons.append(f"GEO: {self.geo_result.reason}")
        if not self.similarity_result.passed:
            reasons.append(f"Similarity: {self.similarity_result.reason}")
        if self.hallucination_result and not self.hallucination_result.passed:
            reasons.append(f"Hallucination: {self.hallucination_result.reason}")
        if self.info_preservation_result and not self.info_preservation_result.passed:
            reasons.append(f"InfoPreservation: {self.info_preservation_result.reason}")
        if self.faithfulness_result and not self.faithfulness_result.passed:
            reasons.append(f"Faithfulness: {self.faithfulness_result.reason}")
        return "; ".join(reasons)


class QualityGate:
    """Validates optimization quality before accepting results."""

    _BACKTICK_PARAM: re.Pattern[str] = re.compile(r"`(\w+)`")
    _NUMBERS_WITH_CONTEXT: re.Pattern[str] = re.compile(r"\d[\d,]*\.?\d*\s*[%+]?")
    _TECH_TERMS: re.Pattern[str] = re.compile(
        r"\b(SQL|PostgreSQL|MySQL|MongoDB|Redis|REST|GraphQL|gRPC|HTTP|HTTPS|JSON|XML|YAML|CSV"
        r"|API|SDK|OAuth|JWT|WebSocket|TCP|UDP|S3|AWS|GCP|Azure|Docker|Kubernetes"
        r"|Git|GitHub|Slack|Notion|OWASP|wire protocol|stdio|SSE)\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        min_similarity: float = 0.85,
        allow_geo_decrease: bool = True,
    ) -> None:
        self._min_similarity = min_similarity
        self._allow_geo_decrease = allow_geo_decrease

    def check_geo_score(self, before: AnalysisReport, after: AnalysisReport) -> GateResult:
        """Check that GEO score did not decrease after optimization."""
        if self._allow_geo_decrease:
            return GateResult(passed=True, reason="GEO is diagnostic only — decrease allowed")

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

    def check_hallucinated_params(self, optimized: str, input_schema: dict | None) -> GateResult:
        """Check if optimized description mentions parameters not in the actual schema.

        Args:
            optimized: The optimized description text.
            input_schema: The tool's actual input schema (may be None).

        Returns:
            GateResult indicating pass/fail.
        """
        if not input_schema:
            return GateResult(
                passed=True, reason="No schema available — hallucination check skipped"
            )

        actual_params = set(input_schema.get("properties", {}).keys())
        if not actual_params:
            return GateResult(
                passed=True, reason="No schema properties — hallucination check skipped"
            )

        # Extract backtick-quoted words from optimized description
        mentioned_params = set(self._BACKTICK_PARAM.findall(optimized))
        if not mentioned_params:
            return GateResult(passed=True, reason="No backtick parameters in optimized description")

        # Filter: only flag words that look like parameter names (lowercase, not common words)
        common_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "to",
            "for",
            "and",
            "or",
            "not",
            "true",
            "false",
            "null",
            "none",
        }
        candidate_params = {p for p in mentioned_params if p.lower() not in common_words}

        hallucinated = candidate_params - actual_params
        if hallucinated:
            return GateResult(
                passed=False,
                reason=(
                    f"Hallucinated parameters: {sorted(hallucinated)}."
                    f" Actual: {sorted(actual_params)}"
                ),
            )

        return GateResult(
            passed=True,
            reason=f"All mentioned parameters verified against schema: {sorted(candidate_params)}",
        )

    def check_info_preservation(self, original: str, optimized: str) -> GateResult:
        """Check that key information from original is preserved in optimized.

        Checks for:
        1. Numbers/statistics (e.g., "50,000+", "99.9%")
        2. Technical terms (e.g., "PostgreSQL", "wire protocol")

        Args:
            original: Original description.
            optimized: Optimized description.

        Returns:
            GateResult indicating pass/fail.
        """
        lost_items: list[str] = []
        optimized_lower = optimized.lower()

        # Check numbers
        original_numbers = self._NUMBERS_WITH_CONTEXT.findall(original)
        significant_numbers = [n.strip() for n in original_numbers if len(n.strip()) >= 2]
        for num in significant_numbers:
            if num not in optimized:
                lost_items.append(f"number '{num}'")

        # Check technical terms
        original_terms = set(self._TECH_TERMS.findall(original))
        for term in original_terms:
            if term.lower() not in optimized_lower:
                lost_items.append(f"term '{term}'")

        if lost_items:
            return GateResult(
                passed=False,
                reason=f"Information lost from original: {', '.join(lost_items)}",
            )

        return GateResult(passed=True, reason="Key information preserved from original")

    def check_faithfulness(
        self,
        original: str,
        optimized: str,
        input_schema: dict | None,
        claims: list[dict],
    ) -> GateResult:
        """RAGAS-style faithfulness check: verify all claims against source data.

        Each claim has {"claim": str, "supported": bool}.
        Passes only if ALL claims are supported.

        The claim extraction and verification is done externally (by LLM);
        this gate makes the pass/fail decision based on the verification results.
        """
        if not claims:
            return GateResult(passed=True, reason="No claims to verify")

        unsupported = [c["claim"] for c in claims if not c["supported"]]

        if unsupported:
            return GateResult(
                passed=False,
                reason=(
                    f"Faithfulness check failed: {len(unsupported)} unsupported/hallucinated "
                    f"claim(s): {unsupported[:3]}"
                ),
            )

        return GateResult(
            passed=True,
            reason=f"All {len(claims)} claims verified as faithful",
        )

    def evaluate(
        self,
        before: AnalysisReport,
        after: AnalysisReport,
        vec_before: np.ndarray,
        vec_after: np.ndarray,
        input_schema: dict | None = None,
        optimized_text: str | None = None,
        original_text: str | None = None,
    ) -> FullGateResult:
        """Run all quality gate checks."""
        geo_result = self.check_geo_score(before, after)
        sim_result = self.check_semantic_similarity(vec_before, vec_after)

        hallucination_result = None
        info_preservation_result = None

        if optimized_text and input_schema:
            hallucination_result = self.check_hallucinated_params(optimized_text, input_schema)

        if original_text and optimized_text:
            info_preservation_result = self.check_info_preservation(original_text, optimized_text)

        passed = (
            geo_result.passed
            and sim_result.passed
            and (hallucination_result is None or hallucination_result.passed)
            and (info_preservation_result is None or info_preservation_result.passed)
        )

        if not passed:
            logger.warning(
                f"Quality gate FAILED for {before.tool_id}: "
                f"GEO={geo_result.passed}, Similarity={sim_result.passed}"
                + (f", Hallucination={hallucination_result.passed}" if hallucination_result else "")
                + (
                    f", InfoPreservation={info_preservation_result.passed}"
                    if info_preservation_result
                    else ""
                )
            )

        return FullGateResult(
            passed=passed,
            geo_result=geo_result,
            similarity_result=sim_result,
            hallucination_result=hallucination_result,
            info_preservation_result=info_preservation_result,
        )
