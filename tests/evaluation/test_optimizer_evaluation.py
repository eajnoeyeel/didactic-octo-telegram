"""Evaluation tests for Description Optimizer.

These tests verify the optimizer's impact on retrieval performance.
They require external API keys and are guarded by skipif.

Stage 2: GEO Score improvement
Stage 3: Semantic preservation
Stage 4: Precision@1 A/B test (future, requires full pipeline setup)
"""

import pytest

from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import GEO_DIMENSIONS


@pytest.fixture
def analyzer() -> HeuristicAnalyzer:
    return HeuristicAnalyzer()


# --- Stage 2: GEO Score Improvement ---

SAMPLE_POOR_DESCRIPTIONS = [
    ("s::search", "Search tool"),
    ("s::read", "Reads files"),
    ("s::create", "Creates things"),
    ("s::query", "Database query"),
    ("s::send", "Sends messages"),
]

SAMPLE_GOOD_DESCRIPTIONS = [
    (
        "github::search_issues",
        "Searches GitHub Issues matching a text query. Use when you need to find "
        "bug reports, feature requests, or discussions in a specific repository. "
        "Unlike the PR search tool, this only searches Issues, not Pull Requests. "
        "Cannot search across multiple repositories in a single call. "
        "Returns up to 100 results per page via the GitHub REST API v3.",
    ),
    (
        "postgres::run_query",
        "Executes read-only SQL queries against a PostgreSQL database via the "
        "wire protocol. Use when you need to retrieve structured data. Supports "
        "JSON, JSONB, and ARRAY column types. Cannot execute DDL (CREATE/DROP) "
        "or DML (INSERT/UPDATE/DELETE) statements. Query timeout: 30 seconds. "
        "Maximum result size: 10,000 rows.",
    ),
]


class TestGEOScoreDifferentiation:
    """Stage 2: Verify HeuristicAnalyzer distinguishes poor vs good."""

    async def test_poor_descriptions_score_low(self, analyzer: HeuristicAnalyzer) -> None:
        for tool_id, desc in SAMPLE_POOR_DESCRIPTIONS:
            report = await analyzer.analyze(tool_id, desc)
            assert report.geo_score < 0.4, (
                f"{tool_id}: GEO={report.geo_score:.3f} too high for poor desc"
            )

    async def test_good_descriptions_score_high(self, analyzer: HeuristicAnalyzer) -> None:
        for tool_id, desc in SAMPLE_GOOD_DESCRIPTIONS:
            report = await analyzer.analyze(tool_id, desc)
            assert report.geo_score > 0.4, (
                f"{tool_id}: GEO={report.geo_score:.3f} too low for good desc"
            )

    async def test_good_beats_poor(self, analyzer: HeuristicAnalyzer) -> None:
        poor_scores = []
        for tool_id, desc in SAMPLE_POOR_DESCRIPTIONS:
            report = await analyzer.analyze(tool_id, desc)
            poor_scores.append(report.geo_score)

        good_scores = []
        for tool_id, desc in SAMPLE_GOOD_DESCRIPTIONS:
            report = await analyzer.analyze(tool_id, desc)
            good_scores.append(report.geo_score)

        avg_poor = sum(poor_scores) / len(poor_scores)
        avg_good = sum(good_scores) / len(good_scores)

        assert avg_good > avg_poor + 0.2, (
            f"Good descriptions (avg={avg_good:.3f}) should score "
            f"at least 0.2 higher than poor (avg={avg_poor:.3f})"
        )


class TestAllDimensionsCovered:
    """Verify analyzer returns scores for all 6 GEO dimensions."""

    async def test_dimensions_complete(self, analyzer: HeuristicAnalyzer) -> None:
        for _, desc in SAMPLE_GOOD_DESCRIPTIONS:
            report = await analyzer.analyze("s::t", desc)
            dims = {s.dimension for s in report.dimension_scores}
            assert dims == GEO_DIMENSIONS
