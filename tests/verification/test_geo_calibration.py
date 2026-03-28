"""GEO score calibration tests using real-world MCP tool descriptions.

Verifies that HeuristicAnalyzer GEO scores align with expected quality tiers:
  - Poor descriptions: vague, single-phrase, no context
  - Medium descriptions: functional but missing dimension depth
  - Good descriptions: rich with constraints, params, precision, stats

Actual scores (measured 2026-03-28):
  Poor:
    "Search stuff"  => geo=0.0250
    "Read a file"   => geo=0.0250
    "Run command"   => geo=0.0250
  Medium:
    GitHub repos desc => geo=0.1083
    Slack message desc => geo=0.1250
  Good:
    PostgreSQL SQL desc => geo=0.5833
    GitHub Issues desc  => geo=0.4667
"""

from __future__ import annotations

import pytest

from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import AnalysisReport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _geo(report: AnalysisReport) -> float:
    return report.geo_score


def _dim(report: AnalysisReport, dimension: str) -> float:
    return next(s.score for s in report.dimension_scores if s.dimension == dimension)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

POOR_DESCRIPTIONS: list[tuple[str, float]] = [
    # (description, expected_max_geo)
    # Actual: 0.0250 — only a single action verb fires (clarity +0.15), rest zero
    ("Search stuff", 0.25),
    ("Read a file", 0.25),
    ("Run command", 0.25),
]

MEDIUM_DESCRIPTIONS: list[tuple[str, float, float]] = [
    # (description, expected_min_geo, expected_max_geo)
    # Actual: 0.1083 — clarity fires (length+verbs), GitHub triggers precision
    (
        "Search for GitHub repositories matching a query. "
        "Returns repository name, URL, description, star count, and language.",
        0.05,
        0.55,
    ),
    # Actual: 0.1250 — clarity fires (length+verb+when_to_use), Slack triggers precision
    (
        "Send a message to a Slack channel or user. "
        "Requires a channel ID and message text. "
        "Use when you need to notify a team about events.",
        0.05,
        0.55,
    ),
]

GOOD_DESCRIPTIONS: list[tuple[str, float]] = [
    # (description, expected_min_geo)
    # Actual: 0.5833 — all 6 dimensions active; SQL/PostgreSQL/JSON in precision
    (
        "Executes read-only SQL queries against a PostgreSQL database via the wire protocol. "
        "Use when you need to retrieve structured data from tables. "
        "Supports JSON, JSONB, and ARRAY column types. "
        "Accepts a required `query` string parameter. "
        "Cannot execute DDL (CREATE/DROP) or DML (INSERT/UPDATE/DELETE) statements. "
        "Not suitable for bulk data export. "
        "Query timeout: 30 seconds. Maximum result size: 10,000 rows.",
        0.45,
    ),
    # Actual: 0.4667 — clarity + disambiguation very high; parameter_coverage zero
    (
        "Searches GitHub Issues matching a text query via the GitHub REST API v3. "
        "Use when you need to find bug reports, feature requests, or discussions "
        "in a specific repository. "
        "Unlike the PR search tool, this only searches Issues, not Pull Requests. "
        "Cannot search across multiple repositories in a single call. "
        "Returns up to 100 results per page.",
        0.45,
    ),
]

# Shortcuts for dimension-breakdown tests
_POSTGRES_DESC = (
    "Executes read-only SQL queries against a PostgreSQL database via the wire protocol. "
    "Use when you need to retrieve structured data from tables. "
    "Supports JSON, JSONB, and ARRAY column types. "
    "Accepts a required `query` string parameter. "
    "Cannot execute DDL (CREATE/DROP) or DML (INSERT/UPDATE/DELETE) statements. "
    "Not suitable for bulk data export. "
    "Query timeout: 30 seconds. Maximum result size: 10,000 rows."
)
_POOR_SEARCH_DESC = "Search stuff"


# ---------------------------------------------------------------------------
# Poor-description calibration
# ---------------------------------------------------------------------------


class TestPoorDescriptionCalibration:
    """Each poor description must score at or below the expected GEO ceiling."""

    @pytest.mark.parametrize("description,expected_max", POOR_DESCRIPTIONS)
    async def test_poor_geo_at_or_below_max(
        self,
        analyzer: HeuristicAnalyzer,
        description: str,
        expected_max: float,
    ) -> None:
        # Actual scores are ~0.025; ceiling is set at 0.25 (~10× margin)
        report = await analyzer.analyze("poor::tool", description)
        assert _geo(report) <= expected_max, (
            f"Expected GEO <= {expected_max} for {description!r}, got {_geo(report):.4f}"
        )


# ---------------------------------------------------------------------------
# Medium-description calibration
# ---------------------------------------------------------------------------


class TestMediumDescriptionCalibration:
    """Each medium description must fall within the expected GEO range."""

    @pytest.mark.parametrize("description,min_geo,max_geo", MEDIUM_DESCRIPTIONS)
    async def test_medium_geo_in_range(
        self,
        analyzer: HeuristicAnalyzer,
        description: str,
        min_geo: float,
        max_geo: float,
    ) -> None:
        # Actual scores are ~0.11–0.13; range is [0.05, 0.55] for ~10% margin
        report = await analyzer.analyze("medium::tool", description)
        geo = _geo(report)
        assert min_geo <= geo <= max_geo, (
            f"Expected GEO in [{min_geo}, {max_geo}] for {description[:50]!r}..., got {geo:.4f}"
        )


# ---------------------------------------------------------------------------
# Good-description calibration
# ---------------------------------------------------------------------------


class TestGoodDescriptionCalibration:
    """Each good description must score at or above the expected GEO floor."""

    @pytest.mark.parametrize("description,expected_min", GOOD_DESCRIPTIONS)
    async def test_good_geo_at_or_above_min(
        self,
        analyzer: HeuristicAnalyzer,
        description: str,
        expected_min: float,
    ) -> None:
        # Actual scores are 0.47–0.58; floor set at 0.45
        report = await analyzer.analyze("good::tool", description)
        assert _geo(report) >= expected_min, (
            f"Expected GEO >= {expected_min} for {description[:50]!r}..., got {_geo(report):.4f}"
        )


# ---------------------------------------------------------------------------
# Score distribution: poor < medium < good
# ---------------------------------------------------------------------------


class TestScoreDistribution:
    """Average GEO scores must strictly increase across quality tiers."""

    async def test_tier_ordering(self, analyzer: HeuristicAnalyzer) -> None:
        """avg(poor) < avg(medium) < avg(good) must hold."""
        poor_scores = [
            _geo(await analyzer.analyze("poor::tool", desc)) for desc, _ in POOR_DESCRIPTIONS
        ]
        medium_scores = [
            _geo(await analyzer.analyze("medium::tool", desc)) for desc, _, _ in MEDIUM_DESCRIPTIONS
        ]
        good_scores = [
            _geo(await analyzer.analyze("good::tool", desc)) for desc, _ in GOOD_DESCRIPTIONS
        ]

        avg_poor = sum(poor_scores) / len(poor_scores)
        avg_medium = sum(medium_scores) / len(medium_scores)
        avg_good = sum(good_scores) / len(good_scores)

        assert avg_poor < avg_medium, (
            f"Expected avg(poor)={avg_poor:.4f} < avg(medium)={avg_medium:.4f}"
        )
        assert avg_medium < avg_good, (
            f"Expected avg(medium)={avg_medium:.4f} < avg(good)={avg_good:.4f}"
        )


# ---------------------------------------------------------------------------
# Dimension breakdown
# ---------------------------------------------------------------------------


class TestDimensionBreakdown:
    """Spot-check individual dimension scores on known descriptions."""

    async def test_postgres_precision_high(self, analyzer: HeuristicAnalyzer) -> None:
        """PostgreSQL description has SQL/JSON/REST terms — precision >= 0.3.

        Actual: precision=0.75 (SQL, PostgreSQL, JSON hit _TECHNICAL_TERMS;
        'wire protocol' hits _PROTOCOL_FORMAT).
        """
        report = await analyzer.analyze("good::postgres_tool", _POSTGRES_DESC)
        assert _dim(report, "precision") >= 0.3, (
            f"Expected precision >= 0.3, got {_dim(report, 'precision'):.4f}"
        )

    async def test_postgres_boundary_high(self, analyzer: HeuristicAnalyzer) -> None:
        """PostgreSQL description has 'Cannot', 'Not suitable' — boundary >= 0.3.

        Actual: boundary=0.60 ('Cannot execute' + 'Not suitable' = 2 neg_boundary hits).
        """
        report = await analyzer.analyze("good::postgres_tool", _POSTGRES_DESC)
        assert _dim(report, "boundary") >= 0.3, (
            f"Expected boundary >= 0.3, got {_dim(report, 'boundary'):.4f}"
        )

    async def test_poor_search_all_dimensions_low(self, analyzer: HeuristicAnalyzer) -> None:
        """'Search stuff' has no context signals — all 6 dimensions <= 0.35.

        Actual: clarity=0.15 (single verb), rest=0.00.
        """
        report = await analyzer.analyze("poor::tool", _POOR_SEARCH_DESC)
        for score in report.dimension_scores:
            assert score.score <= 0.35, (
                f"Expected {score.dimension} <= 0.35 for {_POOR_SEARCH_DESC!r}, "
                f"got {score.score:.4f}"
            )
