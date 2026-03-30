"""Tests for HeuristicAnalyzer — rule-based GEO scoring."""

import pytest

from description_optimizer.analyzer.base import DescriptionAnalyzer
from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import GEO_DIMENSIONS, AnalysisReport


@pytest.fixture
def analyzer() -> HeuristicAnalyzer:
    return HeuristicAnalyzer()


class TestHeuristicAnalyzerIsABC:
    def test_implements_abc(self, analyzer: HeuristicAnalyzer) -> None:
        assert isinstance(analyzer, DescriptionAnalyzer)


class TestClarityScoring:
    """Clarity: action verbs, what+when-to-use, specific scope."""

    async def test_high_clarity(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Searches the PostgreSQL database for records matching a query. Use when you need to retrieve structured data from the users table."  # noqa: E501
        report = await analyzer.analyze("s::tool", desc)
        clarity = next(s for s in report.dimension_scores if s.dimension == "clarity")
        assert clarity.score >= 0.7

    async def test_low_clarity(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "A tool."
        report = await analyzer.analyze("s::tool", desc)
        clarity = next(s for s in report.dimension_scores if s.dimension == "clarity")
        assert clarity.score <= 0.3

    async def test_medium_clarity(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Handles file operations for the project."
        report = await analyzer.analyze("s::tool", desc)
        clarity = next(s for s in report.dimension_scores if s.dimension == "clarity")
        assert 0.2 <= clarity.score <= 0.7


class TestDisambiguationScoring:
    async def test_high_disambiguation(self, analyzer: HeuristicAnalyzer) -> None:
        # New scoring: action-object pairs + scope delimiters give high score
        desc = "Searches for issues specifically within the GitHub Issues API. Limited to issue records only, not pull requests."  # noqa: E501
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "disambiguation")
        assert score.score >= 0.4

    async def test_no_disambiguation(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Search tool for finding things."
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "disambiguation")
        assert score.score <= 0.3


class TestDisambiguationRedesign:
    """Verify disambiguation no longer rewards sibling name contamination."""

    @pytest.fixture
    def analyzer(self) -> HeuristicAnalyzer:
        return HeuristicAnalyzer()

    @pytest.mark.asyncio
    async def test_contrast_phrases_do_not_boost_score(self, analyzer: HeuristicAnalyzer) -> None:
        """'Unlike X, Y, Z' should NOT increase disambiguation score."""
        clean = "Calculates the median value of a sorted numeric list."
        # Adds only a contrast phrase (unlike ...) with no additional action-object pairs
        contaminated = (
            "Calculates the median value of a sorted numeric list. "
            "Unlike addition, subtraction, and division."
        )
        report_clean = await analyzer.analyze("s::median", clean)
        report_dirty = await analyzer.analyze("s::median", contaminated)
        score_clean = next(
            s for s in report_clean.dimension_scores if s.dimension == "disambiguation"
        )
        score_dirty = next(
            s for s in report_dirty.dimension_scores if s.dimension == "disambiguation"
        )
        # Contaminated text should NOT score higher than clean text
        assert score_dirty.score <= score_clean.score

    @pytest.mark.asyncio
    async def test_target_specificity_rewards_action_object(  # noqa: E501
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Target-specific descriptions with action+object should score well."""
        specific = "Calculates the median — the middle value of a sorted numeric list."
        generic = "Does something with numbers."
        report_specific = await analyzer.analyze("s::median", specific)
        report_generic = await analyzer.analyze("s::median", generic)
        score_specific = next(
            s for s in report_specific.dimension_scores if s.dimension == "disambiguation"
        )
        score_generic = next(
            s for s in report_generic.dimension_scores if s.dimension == "disambiguation"
        )
        assert score_specific.score > score_generic.score

    @pytest.mark.asyncio
    async def test_domain_qualifier_without_sibling_names(  # noqa: E501
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Domain qualifiers like 'specifically for' boost score without sibling names."""
        desc = "Specifically handles rounding numeric values to the nearest whole integer."
        report = await analyzer.analyze("s::round", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "disambiguation")
        assert score.score > 0.0


class TestFluencyScoring:
    async def test_high_fluency(self) -> None:
        """Well-structured sentences with connectors score high."""
        desc = (
            "Searches the PostgreSQL database for records matching a query. "
            "Use this tool when you need to retrieve structured data from tables. "
            "It supports filtering by column values and returns results in JSON format."
        )
        analyzer = HeuristicAnalyzer()
        report = await analyzer.analyze("test::tool", desc)
        fluency = next(s for s in report.dimension_scores if s.dimension == "fluency")
        assert fluency.score >= 0.5

    async def test_low_fluency(self) -> None:
        """Single short fragment without connectors scores low."""
        desc = "get data"
        analyzer = HeuristicAnalyzer()
        report = await analyzer.analyze("test::tool", desc)
        fluency = next(s for s in report.dimension_scores if s.dimension == "fluency")
        assert fluency.score <= 0.3


class TestStatsScoring:
    async def test_has_stats(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Searches across 50,000+ packages with 99.9% uptime. Returns up to 100 results per query in under 200ms."  # noqa: E501
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "stats")
        assert score.score >= 0.6

    async def test_no_stats(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "A search tool for packages."
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "stats")
        assert score.score <= 0.2


class TestPrecisionScoring:
    async def test_has_precision(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Executes SQL queries via the PostgreSQL wire protocol. Supports JSON, JSONB, and ARRAY column types. Compatible with pg_trgm extension."  # noqa: E501
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "precision")
        assert score.score >= 0.6

    async def test_no_precision(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Runs queries on the database."
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "precision")
        assert score.score <= 0.3


class TestFullAnalysis:
    async def test_returns_all_six_dimensions(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "A basic tool for searching."
        report = await analyzer.analyze("s::tool", desc)
        assert isinstance(report, AnalysisReport)
        dims = {s.dimension for s in report.dimension_scores}
        assert dims == GEO_DIMENSIONS

    async def test_geo_score_is_average(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Searches the PostgreSQL database for records."
        report = await analyzer.analyze("s::tool", desc)
        expected = sum(s.score for s in report.dimension_scores) / 6
        assert abs(report.geo_score - expected) < 1e-6

    async def test_empty_description(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("s::tool", "")
        assert report.geo_score <= 0.1

    async def test_none_description(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("s::tool", None)
        assert report.geo_score <= 0.1
