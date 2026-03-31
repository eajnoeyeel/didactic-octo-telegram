"""Automated assertions on comparison verification results.

These tests validate that the optimization pipeline produces measurable
improvements when run on real MCP tool descriptions.

Prerequisites:
    Run the comparison verification script first:
    PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase optimize
"""

import json
from pathlib import Path

import pytest

RESULTS_FILE = Path("data/verification/optimization_results.jsonl")

# Skip all tests if results file doesn't exist (Phase 2 not yet run)
pytestmark = pytest.mark.skipif(
    not RESULTS_FILE.exists(),
    reason="optimization_results.jsonl not found — run Phase 2 first",
)


def _load_results() -> list[dict]:
    results = []
    with open(RESULTS_FILE) as f:
        for line in f:
            results.append(json.loads(line.strip()))
    return results


class TestOverallQuality:
    """Validate overall optimization quality metrics."""

    def test_at_least_one_success(self) -> None:
        """Pipeline must successfully optimize at least 1 tool."""
        results = _load_results()
        success_count = sum(1 for r in results if r["status"] == "success")
        assert success_count > 0, "No successful optimizations"

    def test_success_rate_above_50_percent(self) -> None:
        """At least 50% of tools should be successfully optimized."""
        results = _load_results()
        success_count = sum(1 for r in results if r["status"] == "success")
        rate = success_count / len(results)
        assert rate >= 0.50, f"Success rate {rate:.0%} below 50%"

    def test_no_status_is_null(self) -> None:
        """Every result must have a valid status."""
        results = _load_results()
        for r in results:
            assert r["status"] in {"success", "skipped", "failed", "gate_rejected"}


class TestGEOImprovement:
    """Validate GEO score improvements on successful optimizations."""

    def test_average_geo_improvement_positive(self) -> None:
        """Average GEO improvement across successes must be > 0."""
        results = _load_results()
        success = [r for r in results if r["status"] == "success"]
        if not success:
            pytest.skip("No successful optimizations")
        avg_improvement = sum(r["geo_score_after"] - r["geo_score_before"] for r in success) / len(
            success
        )
        assert avg_improvement > 0, f"Average improvement {avg_improvement:.4f} is not positive"

    def test_no_success_has_negative_improvement(self) -> None:
        """No successful optimization should have a negative GEO delta.

        Quality Gate should prevent this — if it passed, GEO must not decrease.
        """
        results = _load_results()
        for r in results:
            if r["status"] == "success":
                delta = r["geo_score_after"] - r["geo_score_before"]
                assert delta >= 0, (
                    f"{r['tool_id']}: GEO decreased {delta:+.4f} despite SUCCESS status"
                )

    def test_geo_scores_in_valid_range(self) -> None:
        """All GEO scores must be in [0.0, 1.0]."""
        results = _load_results()
        for r in results:
            assert 0.0 <= r["geo_score_before"] <= 1.0, (
                f"{r['tool_id']}: geo_score_before={r['geo_score_before']} out of range"
            )
            assert 0.0 <= r["geo_score_after"] <= 1.0, (
                f"{r['tool_id']}: geo_score_after={r['geo_score_after']} out of range"
            )


class TestDimensionImprovement:
    """Validate per-dimension improvements."""

    def test_at_least_3_dimensions_improve_on_average(self) -> None:
        """On average, at least 3 of 6 dimensions should improve."""
        results = _load_results()
        success = [r for r in results if r["status"] == "success"]
        if not success:
            pytest.skip("No successful optimizations")

        dims = ["clarity", "disambiguation", "parameter_coverage", "fluency", "stats", "precision"]
        dims_improved = 0
        for dim in dims:
            before_avg = sum(
                r.get("dimension_scores_original", {}).get(dim, 0) for r in success
            ) / len(success)
            after_avg = sum(r.get("dimension_scores_after", {}).get(dim, 0) for r in success) / len(
                success
            )
            if after_avg > before_avg:
                dims_improved += 1

        assert dims_improved >= 3, (
            f"Only {dims_improved}/6 dimensions improved on average (need >= 3)"
        )


class TestSemanticPreservation:
    """Validate that optimized descriptions preserve original meaning."""

    def test_optimized_not_empty(self) -> None:
        """Successful optimizations must have non-empty optimized_description."""
        results = _load_results()
        for r in results:
            if r["status"] == "success":
                assert len(r["optimized_description"].strip()) > 0, (
                    f"{r['tool_id']}: empty optimized_description"
                )

    def test_retrieval_description_not_empty(self) -> None:
        """Successful optimizations must have non-empty retrieval/search description."""
        results = _load_results()
        for r in results:
            if r["status"] == "success":
                retrieval_text = r.get("retrieval_description") or r.get("search_description", "")
                assert len(retrieval_text.strip()) > 0, (
                    f"{r['tool_id']}: empty retrieval description"
                )

    def test_retrieval_length_reasonable(self) -> None:
        """Retrieval descriptions should stay concise enough for embedding text."""
        results = _load_results()
        for r in results:
            if r["status"] == "success":
                retrieval_text = r.get("retrieval_description") or r.get("search_description", "")
                length = len(retrieval_text)
                assert 5 <= length <= 2000, (
                    f"{r['tool_id']}: retrieval length {length} outside [5, 2000]"
                )


class TestQualityGateEffectiveness:
    """Validate that gate rejections are legitimate."""

    def test_gate_rejected_preserves_original(self) -> None:
        """Gate-rejected results must have optimized == original."""
        results = _load_results()
        for r in results:
            if r["status"] == "gate_rejected":
                assert r["optimized_description"] == r["original_description"], (
                    f"{r['tool_id']}: gate_rejected but description changed"
                )

    def test_failed_has_skip_reason(self) -> None:
        """Failed and gate_rejected results must have a skip_reason."""
        results = _load_results()
        for r in results:
            if r["status"] in ("failed", "gate_rejected"):
                assert r.get("skip_reason"), (
                    f"{r['tool_id']}: status={r['status']} but no skip_reason"
                )
