"""Heuristic Analyzer sensitivity tests — verify the analyzer rewards
known-good patterns and penalizes known-bad patterns consistently."""

import pytest

from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import AnalysisReport


@pytest.fixture
def analyzer() -> HeuristicAnalyzer:
    return HeuristicAnalyzer()


def _dim(report: AnalysisReport, dimension: str) -> float:
    return next(s.score for s in report.dimension_scores if s.dimension == dimension)


class TestClarityDimension:
    """Verify clarity scoring responds to specific signal additions."""

    async def test_adding_action_verb_increases_clarity(self, analyzer: HeuristicAnalyzer) -> None:
        """Adding an action verb to a vague description increases clarity."""
        vague = "A tool for files"
        with_verb = "Searches and retrieves files from the filesystem"
        r_vague = await analyzer.analyze("t::a", vague)
        r_verb = await analyzer.analyze("t::b", with_verb)
        assert _dim(r_verb, "clarity") > _dim(r_vague, "clarity")

    async def test_adding_when_to_use_increases_clarity(self, analyzer: HeuristicAnalyzer) -> None:
        """Adding 'Use when...' phrase increases clarity."""
        base = "Searches files in a directory"
        with_when = (
            "Searches files in a directory. Use when you need to find specific files by pattern."
        )
        r_base = await analyzer.analyze("t::a", base)
        r_when = await analyzer.analyze("t::b", with_when)
        assert _dim(r_when, "clarity") > _dim(r_base, "clarity")

    async def test_adding_scope_increases_clarity(self, analyzer: HeuristicAnalyzer) -> None:
        """Adding scope markers ('from the', 'in the') increases clarity."""
        base = "Searches files"
        with_scope = "Searches files from the local filesystem via the OS API"
        r_base = await analyzer.analyze("t::a", base)
        r_scope = await analyzer.analyze("t::b", with_scope)
        assert _dim(r_scope, "clarity") > _dim(r_base, "clarity")


class TestDisambiguationDimension:
    """Verify disambiguation scoring responds to contrast language."""

    async def test_adding_contrast_increases_disambiguation(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding 'unlike X' phrase increases disambiguation."""
        base = "Searches files"
        with_contrast = (
            "Searches files. Unlike grep, this tool only searches filenames, not content."
        )
        r_base = await analyzer.analyze("t::a", base)
        r_contrast = await analyzer.analyze("t::b", with_contrast)
        assert _dim(r_contrast, "disambiguation") > _dim(r_base, "disambiguation")

    async def test_adding_only_for_increases_disambiguation(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding 'only for' qualifier increases disambiguation."""
        base = "Manages database connections"
        with_qual = (
            "Manages database connections. Only for PostgreSQL databases, not MySQL or SQLite."
        )
        r_base = await analyzer.analyze("t::a", base)
        r_qual = await analyzer.analyze("t::b", with_qual)
        assert _dim(r_qual, "disambiguation") > _dim(r_base, "disambiguation")


class TestFluencyDimension:
    """Verify fluency scoring responds to sentence structure improvements."""

    async def test_adding_complete_sentence_increases_fluency(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding complete sentences increases fluency score."""
        base = "Search data"
        enhanced = (
            "Search the database for matching records. Use this when you need filtered results."
        )
        base_report = await analyzer.analyze("t", base)
        enh_report = await analyzer.analyze("t", enhanced)
        base_score = next(s.score for s in base_report.dimension_scores if s.dimension == "fluency")
        enh_score = next(s.score for s in enh_report.dimension_scores if s.dimension == "fluency")
        assert enh_score > base_score

    async def test_adding_connectors_increases_fluency(self, analyzer: HeuristicAnalyzer) -> None:
        """Adding connector words increases fluency score."""
        base = "Search data from tables. Filter records by columns."
        enhanced = (
            "Search data from tables and filter records by columns. "
            "Also supports sorting because it uses indexed queries."
        )
        base_report = await analyzer.analyze("t", base)
        enh_report = await analyzer.analyze("t", enhanced)
        base_score = next(s.score for s in base_report.dimension_scores if s.dimension == "fluency")
        enh_score = next(s.score for s in enh_report.dimension_scores if s.dimension == "fluency")
        assert enh_score > base_score


class TestStatsDimension:
    """Verify stats scoring responds to quantitative information."""

    async def test_adding_numbers_with_units_increases_stats(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding '100 results per query' increases stats score."""
        base = "Returns search results"
        with_stats = "Returns up to 100 results per query in under 200ms"
        r_base = await analyzer.analyze("t::a", base)
        r_stats = await analyzer.analyze("t::b", with_stats)
        assert _dim(r_stats, "stats") > _dim(r_base, "stats")


class TestPrecisionDimension:
    """Verify precision scoring responds to technical terminology."""

    async def test_adding_tech_terms_increases_precision(self, analyzer: HeuristicAnalyzer) -> None:
        """Adding technical terms (SQL, REST, JSON) increases precision."""
        base = "Queries the database"
        with_tech = "Queries the PostgreSQL database via REST API, returning JSON responses"
        r_base = await analyzer.analyze("t::a", base)
        r_tech = await analyzer.analyze("t::b", with_tech)
        assert _dim(r_tech, "precision") > _dim(r_base, "precision")


class TestParameterCoverageDimension:
    """Verify parameter_coverage responds to parameter documentation."""

    async def test_adding_param_refs_increases_coverage(self, analyzer: HeuristicAnalyzer) -> None:
        """Adding parameter references increases parameter_coverage."""
        base = "Searches for items"
        with_params = (
            "Searches for items. Accepts a required `query` string parameter "
            "and an optional `limit` integer."
        )
        r_base = await analyzer.analyze("t::a", base)
        r_params = await analyzer.analyze("t::b", with_params)
        assert _dim(r_params, "parameter_coverage") > _dim(r_base, "parameter_coverage")


class TestOverallOrdering:
    """Verify that progressively richer descriptions get progressively higher GEO scores."""

    async def test_progressive_improvement(self, analyzer: HeuristicAnalyzer) -> None:
        """tier1 < tier2 < tier3 in GEO score."""
        tier1 = "Search"
        tier2 = "Searches files in a directory. Returns matching paths."
        tier3 = (
            "Searches files in the local filesystem via glob patterns. "
            "Use when you need to find files by name or extension. "
            "Accepts a required `pattern` string and optional `recursive` bool. "
            "Returns up to 1000 results. Cannot search file contents. "
            "Unlike grep, this only matches filenames. "
            "Supports POSIX glob syntax."
        )
        r1 = await analyzer.analyze("t::a", tier1)
        r2 = await analyzer.analyze("t::b", tier2)
        r3 = await analyzer.analyze("t::c", tier3)
        assert r1.geo_score < r2.geo_score < r3.geo_score
