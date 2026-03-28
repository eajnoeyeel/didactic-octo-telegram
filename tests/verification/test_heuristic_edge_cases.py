"""Edge case tests for HeuristicAnalyzer — robustness verification."""

from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import GEO_DIMENSIONS, AnalysisReport


def _dim(report: AnalysisReport, dimension: str) -> float:
    """Return score for a specific dimension from a report."""
    return next(s.score for s in report.dimension_scores if s.dimension == dimension)


class TestEmptyAndMinimal:
    """Verify the analyzer degrades gracefully on minimal / empty inputs."""

    async def test_empty_string(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("test::tool", "")
        assert report.geo_score <= 0.1

    async def test_none_input(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("test::tool", None)
        assert report.geo_score <= 0.1

    async def test_single_word(self, analyzer: HeuristicAnalyzer) -> None:
        """A single action verb should produce a very low but non-negative GEO score."""
        report = await analyzer.analyze("test::tool", "Search")
        assert 0.0 <= report.geo_score <= 0.3

    async def test_whitespace_only(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("test::tool", "   \n\t  ")
        assert report.geo_score <= 0.1


class TestUnicodeAndMultilingual:
    """Verify the analyzer handles non-ASCII text without crashing and returns valid reports."""

    async def test_korean_description(self, analyzer: HeuristicAnalyzer) -> None:
        """Korean text produces a valid AnalysisReport with all 6 dimensions."""
        desc = "파일 시스템에서 파일을 검색합니다. 경로와 패턴을 입력으로 받습니다."
        report = await analyzer.analyze("test::tool", desc)
        assert isinstance(report, AnalysisReport)
        dims = {s.dimension for s in report.dimension_scores}
        assert dims == GEO_DIMENSIONS
        assert 0.0 <= report.geo_score <= 1.0

    async def test_japanese_description(self, analyzer: HeuristicAnalyzer) -> None:
        """Japanese text produces a valid GEO score in [0.0, 1.0]."""
        desc = "ファイルシステムのファイルを検索します。パスとパターンを入力として受け取ります。"
        report = await analyzer.analyze("test::tool", desc)
        assert 0.0 <= report.geo_score <= 1.0

    async def test_mixed_language(self, analyzer: HeuristicAnalyzer) -> None:
        """Mixed English/Korean text: English patterns still fire, GEO > 0.0."""
        desc = "파일을 Searches the filesystem for files matching a pattern."
        report = await analyzer.analyze("test::tool", desc)
        assert report.geo_score > 0.0

    async def test_emoji_in_description(self, analyzer: HeuristicAnalyzer) -> None:
        """Descriptions containing emoji characters produce a valid GEO score."""
        desc = (
            "\U0001f50d Search files in your repository. "
            "\U0001f4c2 Returns matching paths. Cannot access remote URLs."
        )
        report = await analyzer.analyze("test::tool", desc)
        assert 0.0 <= report.geo_score <= 1.0


class TestExtremeLength:
    """Verify the analyzer handles very long and very short descriptions safely."""

    async def test_very_long_description(self, analyzer: HeuristicAnalyzer) -> None:
        """A 16 000-character description processes without error and returns valid GEO."""
        desc = "Searches files. " * 1000
        report = await analyzer.analyze("test::tool", desc)
        assert isinstance(report, AnalysisReport)
        assert 0.0 <= report.geo_score <= 1.0

    async def test_single_char(self, analyzer: HeuristicAnalyzer) -> None:
        """A single-character description scores at or near zero."""
        report = await analyzer.analyze("test::tool", "x")
        assert report.geo_score <= 0.15


class TestRegexEdgeCases:
    """Verify regex patterns behave correctly on tricky inputs."""

    async def test_action_verb_false_positive(self, analyzer: HeuristicAnalyzer) -> None:
        """Both ambiguous and unambiguous uses of action verbs produce valid reports."""
        desc1 = "A collection of lists of items"
        desc2 = "Lists all files in the directory"
        report1 = await analyzer.analyze("test::tool1", desc1)
        report2 = await analyzer.analyze("test::tool2", desc2)
        # Both must be valid reports — no crash, all dimensions present
        assert {s.dimension for s in report1.dimension_scores} == GEO_DIMENSIONS
        assert {s.dimension for s in report2.dimension_scores} == GEO_DIMENSIONS

    async def test_backtick_heavy_description(self, analyzer: HeuristicAnalyzer) -> None:
        """Multiple backtick inline examples drive parameter_coverage >= 0.3."""
        desc = (
            "Use `query` parameter with `limit` and `offset` fields. "
            "Pass `filter` as `dict` and `sort` as `string`."
        )
        report = await analyzer.analyze("test::tool", desc)
        assert _dim(report, "parameter_coverage") >= 0.3

    async def test_special_regex_chars(self, analyzer: HeuristicAnalyzer) -> None:
        """Descriptions containing regex metacharacters do not raise exceptions."""
        desc = "Search (files) [with] {brackets} and $dollar signs + more.*?"
        report = await analyzer.analyze("test::tool", desc)
        assert isinstance(report, AnalysisReport)

    async def test_repeated_same_verb(self, analyzer: HeuristicAnalyzer) -> None:
        """Repeating the same verb many times: verb contribution is capped, clarity <= 0.6."""
        desc = " ".join(["Search"] * 8)
        report = await analyzer.analyze("test::tool", desc)
        assert _dim(report, "clarity") <= 0.6


class TestMarkdownAndHTML:
    """Verify descriptions with markup produce meaningful (non-zero) GEO scores."""

    async def test_markdown_description(self, analyzer: HeuristicAnalyzer) -> None:
        """Markdown-formatted descriptions are handled and produce GEO > 0.0."""
        desc = (
            "## Search Tool\n\n"
            "Searches **files** in `directory`. Use for _pattern_ matching.\n\n"
            "- Supports `glob`\n"
            "- Returns `list`"
        )
        report = await analyzer.analyze("test::tool", desc)
        assert report.geo_score > 0.0

    async def test_html_tags(self, analyzer: HeuristicAnalyzer) -> None:
        """HTML tag-containing descriptions are handled and produce GEO > 0.0."""
        desc = (
            "<b>Search</b> files using <code>query</code>. "
            "<i>Returns</i> matching <strong>results</strong>."
        )
        report = await analyzer.analyze("test::tool", desc)
        assert report.geo_score > 0.0


class TestDimensionIndependence:
    """Verify that individual dimensions score independently and correctly."""

    async def test_high_clarity_low_boundary(self, analyzer: HeuristicAnalyzer) -> None:
        """Clarity-rich description without boundary language: clarity > boundary."""
        desc = (
            "Searches the database for records matching a query. "
            "Use when you need to retrieve data from the API."
        )
        report = await analyzer.analyze("test::tool", desc)
        clarity = _dim(report, "clarity")
        boundary = _dim(report, "boundary")
        assert clarity > boundary

    async def test_high_boundary_low_stats(self, analyzer: HeuristicAnalyzer) -> None:
        """A description with boundary language but no numeric stats: boundary > stats."""
        desc = (
            "Manages files. Cannot delete system files. "
            "Does not support binary formats. Will not modify permissions."
        )
        report = await analyzer.analyze("test::tool", desc)
        boundary = _dim(report, "boundary")
        stats = _dim(report, "stats")
        assert boundary > stats

    async def test_stats_only(self, analyzer: HeuristicAnalyzer) -> None:
        """A description with only numeric stats content: stats dimension >= 0.5."""
        desc = "Returns 100 results per query in under 200ms with 99.9% uptime guarantee."
        report = await analyzer.analyze("test::tool", desc)
        assert _dim(report, "stats") >= 0.5
