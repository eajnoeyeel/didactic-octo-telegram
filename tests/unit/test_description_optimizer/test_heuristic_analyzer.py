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
        desc = "Searches only in the GitHub Issues API, unlike the PR search tool. Does not search code repositories."  # noqa: E501
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "disambiguation")
        assert score.score >= 0.6

    async def test_no_disambiguation(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Search tool for finding things."
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "disambiguation")
        assert score.score <= 0.3


class TestBoundaryScoring:
    async def test_has_boundaries(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Reads files from the local filesystem. Cannot access remote URLs. NOT for binary file parsing."  # noqa: E501
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "boundary")
        assert score.score >= 0.6

    async def test_no_boundaries(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "A file reading tool."
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "boundary")
        assert score.score <= 0.2


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
