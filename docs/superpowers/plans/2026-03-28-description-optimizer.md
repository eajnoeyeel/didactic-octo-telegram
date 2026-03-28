# Description Optimizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provider가 MCP 서버/도구를 등록할 때 description을 자동 진단 + 최적화하여 검색 선택률(Precision@1)을 향상시키는 파이프라인 구축

**Architecture:** GEO Score 기반 6차원 진단 → LLM(GPT-4o-mini) 기반 차원별 맞춤 재작성 → Quality Gate(의미 보존 + 품질 비하락) → 원본/최적화/검색용 3종 description 저장. 기존 `MCPTool` 모델은 변경하지 않고 새로운 `OptimizedDescription` 모델로 확장.

**Tech Stack:** Python 3.12, AsyncOpenAI (GPT-4o-mini), Pydantic v2, pytest + pytest-asyncio, loguru, 기존 Embedder ABC 재사용

---

## File Structure

```
src/
├── description_optimizer/
│   ├── __init__.py
│   ├── models.py              # OptimizedDescription, AnalysisReport, DimensionScore
│   ├── analyzer/
│   │   ├── __init__.py
│   │   ├── base.py            # DescriptionAnalyzer ABC
│   │   ├── heuristic.py       # HeuristicAnalyzer (regex/rule-based GEO scoring)
│   │   └── llm_analyzer.py    # LLMAnalyzer (GPT-4o-mini, 3-judge ensemble)
│   ├── optimizer/
│   │   ├── __init__.py
│   │   ├── base.py            # DescriptionOptimizer ABC
│   │   ├── llm_optimizer.py   # LLMDescriptionOptimizer (dimension-aware rewriting)
│   │   └── prompts.py         # Prompt templates for optimization
│   ├── quality_gate.py        # QualityGate (pre/post comparison, semantic preservation)
│   └── pipeline.py            # OptimizationPipeline (orchestrator: analyze → optimize → gate)
tests/
├── unit/
│   ├── test_description_optimizer/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   ├── test_heuristic_analyzer.py
│   │   ├── test_llm_analyzer.py
│   │   ├── test_llm_optimizer.py
│   │   ├── test_quality_gate.py
│   │   └── test_pipeline.py
│   └── ... (existing tests)
├── integration/
│   └── test_description_optimizer_integration.py
└── evaluation/
    └── test_optimizer_evaluation.py    # A/B test: original vs optimized Precision@1
description_optimizer/
├── CLAUDE.md
└── docs/
    ├── research-analysis.md
    └── evaluation-design.md
scripts/
└── optimize_descriptions.py           # CLI script to run optimization
```

---

## Task 1: Data Models

**Files:**
- Create: `src/description_optimizer/__init__.py`
- Create: `src/description_optimizer/models.py`
- Test: `tests/unit/test_description_optimizer/__init__.py`
- Test: `tests/unit/test_description_optimizer/test_models.py`

- [ ] **Step 1: Write the failing tests for models**

```python
# tests/unit/test_description_optimizer/__init__.py
# (empty)

# tests/unit/test_description_optimizer/test_models.py
"""Tests for Description Optimizer data models."""

import pytest

from description_optimizer.models import (
    AnalysisReport,
    DimensionScore,
    OptimizedDescription,
    OptimizationStatus,
)


class TestDimensionScore:
    def test_valid_score(self) -> None:
        score = DimensionScore(dimension="clarity", score=0.8, explanation="Clear purpose")
        assert score.dimension == "clarity"
        assert score.score == 0.8
        assert score.explanation == "Clear purpose"

    def test_score_bounds_low(self) -> None:
        with pytest.raises(ValueError):
            DimensionScore(dimension="clarity", score=-0.1, explanation="test")

    def test_score_bounds_high(self) -> None:
        with pytest.raises(ValueError):
            DimensionScore(dimension="clarity", score=1.1, explanation="test")

    def test_valid_dimensions(self) -> None:
        valid = ["clarity", "disambiguation", "parameter_coverage", "boundary", "stats", "precision"]
        for dim in valid:
            score = DimensionScore(dimension=dim, score=0.5, explanation="test")
            assert score.dimension == dim

    def test_invalid_dimension(self) -> None:
        with pytest.raises(ValueError):
            DimensionScore(dimension="invalid_dim", score=0.5, explanation="test")


class TestAnalysisReport:
    def test_geo_score_computation(self) -> None:
        scores = [
            DimensionScore(dimension="clarity", score=0.6, explanation="ok"),
            DimensionScore(dimension="disambiguation", score=0.8, explanation="good"),
            DimensionScore(dimension="parameter_coverage", score=0.4, explanation="weak"),
            DimensionScore(dimension="boundary", score=0.2, explanation="missing"),
            DimensionScore(dimension="stats", score=0.0, explanation="none"),
            DimensionScore(dimension="precision", score=0.5, explanation="partial"),
        ]
        report = AnalysisReport(
            tool_id="server::tool",
            original_description="A tool that does stuff",
            dimension_scores=scores,
        )
        expected_geo = (0.6 + 0.8 + 0.4 + 0.2 + 0.0 + 0.5) / 6
        assert abs(report.geo_score - expected_geo) < 1e-6

    def test_weak_dimensions(self) -> None:
        scores = [
            DimensionScore(dimension="clarity", score=0.8, explanation="good"),
            DimensionScore(dimension="disambiguation", score=0.3, explanation="weak"),
            DimensionScore(dimension="parameter_coverage", score=0.7, explanation="ok"),
            DimensionScore(dimension="boundary", score=0.1, explanation="bad"),
            DimensionScore(dimension="stats", score=0.6, explanation="ok"),
            DimensionScore(dimension="precision", score=0.5, explanation="ok"),
        ]
        report = AnalysisReport(
            tool_id="server::tool",
            original_description="test",
            dimension_scores=scores,
        )
        weak = report.weak_dimensions(threshold=0.5)
        assert set(weak) == {"disambiguation", "boundary"}

    def test_requires_six_dimensions(self) -> None:
        scores = [DimensionScore(dimension="clarity", score=0.5, explanation="test")]
        with pytest.raises(ValueError):
            AnalysisReport(
                tool_id="server::tool",
                original_description="test",
                dimension_scores=scores,
            )


class TestOptimizedDescription:
    def test_fields(self) -> None:
        opt = OptimizedDescription(
            tool_id="server::tool",
            original_description="basic tool",
            optimized_description="An advanced tool that performs X when Y",
            search_description="tool X Y Z purpose disambiguation",
            geo_score_before=0.3,
            geo_score_after=0.7,
            status=OptimizationStatus.SUCCESS,
        )
        assert opt.improvement == pytest.approx(0.4)
        assert opt.status == OptimizationStatus.SUCCESS

    def test_improvement_calculation(self) -> None:
        opt = OptimizedDescription(
            tool_id="server::tool",
            original_description="test",
            optimized_description="test improved",
            search_description="test search",
            geo_score_before=0.5,
            geo_score_after=0.8,
            status=OptimizationStatus.SUCCESS,
        )
        assert opt.improvement == pytest.approx(0.3)

    def test_skipped_status(self) -> None:
        opt = OptimizedDescription(
            tool_id="server::tool",
            original_description="already great tool description",
            optimized_description="already great tool description",
            search_description="already great tool description",
            geo_score_before=0.9,
            geo_score_after=0.9,
            status=OptimizationStatus.SKIPPED,
            skip_reason="GEO score already above threshold",
        )
        assert opt.improvement == pytest.approx(0.0)
        assert opt.skip_reason is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_description_optimizer/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'description_optimizer'`

- [ ] **Step 3: Implement the models**

```python
# src/description_optimizer/__init__.py
"""Description Optimizer — auto-optimize MCP tool descriptions for better retrieval."""

# src/description_optimizer/models.py
"""Data models for the Description Optimizer pipeline."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

GEO_DIMENSIONS = frozenset(
    {"clarity", "disambiguation", "parameter_coverage", "boundary", "stats", "precision"}
)


class OptimizationStatus(StrEnum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    GATE_REJECTED = "gate_rejected"


class DimensionScore(BaseModel):
    """Score for a single GEO dimension (0.0 to 1.0)."""

    dimension: Literal[
        "clarity", "disambiguation", "parameter_coverage", "boundary", "stats", "precision"
    ]
    score: float = Field(ge=0.0, le=1.0)
    explanation: str

    @field_validator("dimension")
    @classmethod
    def validate_dimension(cls, v: str) -> str:
        if v not in GEO_DIMENSIONS:
            raise ValueError(f"Invalid dimension '{v}'. Must be one of {GEO_DIMENSIONS}")
        return v


class AnalysisReport(BaseModel):
    """GEO Score analysis report for a single tool description."""

    tool_id: str
    original_description: str
    dimension_scores: list[DimensionScore]

    @model_validator(mode="after")
    def validate_all_dimensions(self) -> "AnalysisReport":
        dims = {s.dimension for s in self.dimension_scores}
        if dims != GEO_DIMENSIONS:
            missing = GEO_DIMENSIONS - dims
            raise ValueError(f"Missing dimensions: {missing}. All 6 dimensions required.")
        return self

    @computed_field
    @property
    def geo_score(self) -> float:
        """Compute GEO score as equal-weight average of all dimensions."""
        return sum(s.score for s in self.dimension_scores) / len(self.dimension_scores)

    def weak_dimensions(self, threshold: float = 0.5) -> list[str]:
        """Return dimension names that score below the threshold."""
        return [s.dimension for s in self.dimension_scores if s.score < threshold]


class OptimizedDescription(BaseModel):
    """Result of the description optimization pipeline."""

    tool_id: str
    original_description: str
    optimized_description: str
    search_description: str = Field(description="Embedding-optimized description for vector search")
    geo_score_before: float = Field(ge=0.0, le=1.0)
    geo_score_after: float = Field(ge=0.0, le=1.0)
    status: OptimizationStatus
    skip_reason: str | None = None

    @computed_field
    @property
    def improvement(self) -> float:
        """GEO score improvement (after - before)."""
        return self.geo_score_after - self.geo_score_before
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_description_optimizer/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/description_optimizer/__init__.py src/description_optimizer/models.py tests/unit/test_description_optimizer/__init__.py tests/unit/test_description_optimizer/test_models.py
git commit -m "feat(desc-optimizer): add data models — DimensionScore, AnalysisReport, OptimizedDescription"
```

---

## Task 2: DescriptionAnalyzer ABC + HeuristicAnalyzer

**Files:**
- Create: `src/description_optimizer/analyzer/__init__.py`
- Create: `src/description_optimizer/analyzer/base.py`
- Create: `src/description_optimizer/analyzer/heuristic.py`
- Test: `tests/unit/test_description_optimizer/test_heuristic_analyzer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_description_optimizer/test_heuristic_analyzer.py
"""Tests for HeuristicAnalyzer — rule-based GEO scoring."""

import pytest

from description_optimizer.analyzer.base import DescriptionAnalyzer
from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import AnalysisReport, GEO_DIMENSIONS


@pytest.fixture
def analyzer() -> HeuristicAnalyzer:
    return HeuristicAnalyzer()


class TestHeuristicAnalyzerIsABC:
    def test_implements_abc(self, analyzer: HeuristicAnalyzer) -> None:
        assert isinstance(analyzer, DescriptionAnalyzer)


class TestClarityScoring:
    """Clarity: action verbs, what+when-to-use, specific scope."""

    async def test_high_clarity(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Searches the PostgreSQL database for records matching a query. Use when you need to retrieve structured data from the users table."
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
    """Disambiguation: contrast phrases, domain qualifiers, 'only'."""

    async def test_high_disambiguation(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Searches only in the GitHub Issues API, unlike the PR search tool. Does not search code repositories."
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "disambiguation")
        assert score.score >= 0.6

    async def test_no_disambiguation(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Search tool for finding things."
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "disambiguation")
        assert score.score <= 0.3


class TestBoundaryScoring:
    """Boundary: negative instructions, 'NOT for', 'cannot'."""

    async def test_has_boundaries(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Reads files from the local filesystem. Cannot access remote URLs. NOT for binary file parsing."
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "boundary")
        assert score.score >= 0.6

    async def test_no_boundaries(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "A file reading tool."
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "boundary")
        assert score.score <= 0.2


class TestStatsScoring:
    """Stats: numbers, coverage, performance information."""

    async def test_has_stats(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Searches across 50,000+ packages with 99.9% uptime. Returns up to 100 results per query in under 200ms."
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "stats")
        assert score.score >= 0.6

    async def test_no_stats(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "A search tool for packages."
        report = await analyzer.analyze("s::tool", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "stats")
        assert score.score <= 0.2


class TestPrecisionScoring:
    """Precision: technical terms, standards, protocols."""

    async def test_has_precision(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Executes SQL queries via the PostgreSQL wire protocol. Supports JSON, JSONB, and ARRAY column types. Compatible with pg_trgm extension."
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_description_optimizer/test_heuristic_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement DescriptionAnalyzer ABC**

```python
# src/description_optimizer/analyzer/__init__.py
"""Description analysis module."""

# src/description_optimizer/analyzer/base.py
"""Abstract base class for description analyzers."""

from abc import ABC, abstractmethod

from description_optimizer.models import AnalysisReport


class DescriptionAnalyzer(ABC):
    """ABC for analyzing MCP tool descriptions against GEO dimensions.

    Implementations compute a GEO Score (6-dimension analysis) for a given
    tool description.
    """

    @abstractmethod
    async def analyze(self, tool_id: str, description: str | None) -> AnalysisReport:
        """Analyze a tool description and return a GEO Score report.

        Args:
            tool_id: The tool's unique ID (server_id::tool_name).
            description: The tool description text (may be None or empty).

        Returns:
            AnalysisReport with scores for all 6 GEO dimensions.
        """
        ...
```

- [ ] **Step 4: Implement HeuristicAnalyzer**

```python
# src/description_optimizer/analyzer/heuristic.py
"""Heuristic (rule-based) GEO Score analyzer.

Scores each of the 6 GEO dimensions using regex patterns, word lists,
and text structure heuristics. Deterministic, free, instant.

Dimension definitions from docs/design/metrics-rubric.md:
- clarity: action verbs, what + when-to-use, specific scope
- disambiguation: contrast phrases ('unlike', 'only'), domain qualifiers
- parameter_coverage: parameter names, types, inputSchema completeness
- boundary: negative instructions ('NOT for', 'cannot', 'does not')
- stats: numbers, coverage, performance figures
- precision: technical terms, standards, protocols
"""

import re

from description_optimizer.analyzer.base import DescriptionAnalyzer
from description_optimizer.models import AnalysisReport, DimensionScore


# --- Patterns ---

ACTION_VERBS = re.compile(
    r"\b(search|find|retrieve|create|update|delete|read|write|list|fetch|"
    r"execute|run|send|get|post|query|parse|convert|generate|analyze|"
    r"monitor|check|validate|deploy|build|connect|upload|download)\b",
    re.IGNORECASE,
)

WHEN_TO_USE = re.compile(
    r"\b(use when|use this|use for|useful for|designed for|intended for|"
    r"best for|ideal for|when you need|to\s+\w+\s+\w+)\b",
    re.IGNORECASE,
)

SCOPE_MARKERS = re.compile(
    r"\b(from the|in the|via the|through the|across|within|"
    r"for the|on the|of the)\b",
    re.IGNORECASE,
)

CONTRAST_PHRASES = re.compile(
    r"\b(unlike|not to be confused with|as opposed to|different from|"
    r"in contrast to|whereas|specifically for|only for|exclusively)\b",
    re.IGNORECASE,
)

ONLY_DOMAIN = re.compile(
    r"\b(only\s+\w+|specifically\s+\w+|exclusively\s+\w+)\b",
    re.IGNORECASE,
)

NEGATIVE_INSTRUCTIONS = re.compile(
    r"\b(not for|cannot|does not|will not|unable to|"
    r"do not use|should not|won't|isn't|doesn't|"
    r"not suitable|not designed|not intended|"
    r"limitations?:|caveats?:|restrictions?:)\b",
    re.IGNORECASE,
)

STAT_PATTERNS = re.compile(
    r"(\d+[,.]?\d*\s*(%|ms|seconds?|minutes?|hours?|GB|MB|KB|"
    r"requests?|queries|items?|records?|results?|entries|rows|"
    r"per\s+\w+|uptime|latency|throughput)|\d+\+|\d+k\b)",
    re.IGNORECASE,
)

TECH_TERMS = re.compile(
    r"\b(SQL|PostgreSQL|MySQL|MongoDB|Redis|REST|GraphQL|gRPC|HTTP|HTTPS|"
    r"JSON|JSONB|XML|YAML|CSV|API|SDK|OAuth|JWT|WebSocket|TCP|UDP|"
    r"S3|AWS|GCP|Azure|Docker|Kubernetes|Lambda|CDN|DNS|SMTP|IMAP|"
    r"Git|GitHub|GitLab|Jira|Slack|Notion|Trello|Linear|"
    r"MCP|SSE|stdio|protocol|schema|specification)\b",
    re.IGNORECASE,
)


def _clamp(value: float) -> float:
    """Clamp a value to [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


class HeuristicAnalyzer(DescriptionAnalyzer):
    """Rule-based GEO Score analyzer using regex patterns and heuristics."""

    async def analyze(self, tool_id: str, description: str | None) -> AnalysisReport:
        desc = description or ""
        scores = [
            self._score_clarity(desc),
            self._score_disambiguation(desc),
            self._score_parameter_coverage(desc),
            self._score_boundary(desc),
            self._score_stats(desc),
            self._score_precision(desc),
        ]
        return AnalysisReport(
            tool_id=tool_id,
            original_description=desc,
            dimension_scores=scores,
        )

    def _score_clarity(self, desc: str) -> DimensionScore:
        if not desc:
            return DimensionScore(dimension="clarity", score=0.0, explanation="Empty description")

        score = 0.0
        reasons: list[str] = []

        # Length baseline
        if len(desc) >= 50:
            score += 0.2
            reasons.append("adequate length")
        elif len(desc) >= 20:
            score += 0.1
            reasons.append("short")

        # Action verbs at start or in description
        action_matches = ACTION_VERBS.findall(desc)
        if action_matches:
            verb_score = min(len(action_matches) * 0.15, 0.3)
            score += verb_score
            reasons.append(f"{len(action_matches)} action verb(s)")

        # When-to-use guidance
        when_matches = WHEN_TO_USE.findall(desc)
        if when_matches:
            score += 0.25
            reasons.append("usage guidance")

        # Specific scope markers
        scope_matches = SCOPE_MARKERS.findall(desc)
        if scope_matches:
            scope_score = min(len(scope_matches) * 0.1, 0.25)
            score += scope_score
            reasons.append(f"{len(scope_matches)} scope marker(s)")

        return DimensionScore(
            dimension="clarity",
            score=_clamp(score),
            explanation=", ".join(reasons) if reasons else "no clarity signals",
        )

    def _score_disambiguation(self, desc: str) -> DimensionScore:
        if not desc:
            return DimensionScore(dimension="disambiguation", score=0.0, explanation="Empty")

        score = 0.0
        reasons: list[str] = []

        contrast = CONTRAST_PHRASES.findall(desc)
        if contrast:
            score += min(len(contrast) * 0.3, 0.5)
            reasons.append(f"{len(contrast)} contrast phrase(s)")

        only = ONLY_DOMAIN.findall(desc)
        if only:
            score += min(len(only) * 0.2, 0.3)
            reasons.append(f"{len(only)} domain qualifier(s)")

        neg = NEGATIVE_INSTRUCTIONS.findall(desc)
        if neg:
            score += 0.2
            reasons.append("negative boundaries aid disambiguation")

        return DimensionScore(
            dimension="disambiguation",
            score=_clamp(score),
            explanation=", ".join(reasons) if reasons else "no disambiguation signals",
        )

    def _score_parameter_coverage(self, desc: str) -> DimensionScore:
        if not desc:
            return DimensionScore(dimension="parameter_coverage", score=0.0, explanation="Empty")

        score = 0.0
        reasons: list[str] = []

        param_patterns = re.findall(
            r"\b(param(?:eter)?s?|arg(?:ument)?s?|input|field|option|flag)\b",
            desc, re.IGNORECASE,
        )
        if param_patterns:
            score += min(len(param_patterns) * 0.15, 0.3)
            reasons.append(f"{len(param_patterns)} param reference(s)")

        type_patterns = re.findall(
            r"\b(string|int(?:eger)?|float|bool(?:ean)?|list|dict|array|object|number|"
            r"required|optional|default)\b",
            desc, re.IGNORECASE,
        )
        if type_patterns:
            score += min(len(type_patterns) * 0.15, 0.4)
            reasons.append(f"{len(type_patterns)} type reference(s)")

        # Inline examples like `param_name` or "param_name"
        inline_examples = re.findall(r'`[^`]+`|"[^"]*"', desc)
        if inline_examples:
            score += min(len(inline_examples) * 0.1, 0.3)
            reasons.append(f"{len(inline_examples)} inline example(s)")

        return DimensionScore(
            dimension="parameter_coverage",
            score=_clamp(score),
            explanation=", ".join(reasons) if reasons else "no parameter signals",
        )

    def _score_boundary(self, desc: str) -> DimensionScore:
        if not desc:
            return DimensionScore(dimension="boundary", score=0.0, explanation="Empty")

        score = 0.0
        reasons: list[str] = []

        neg = NEGATIVE_INSTRUCTIONS.findall(desc)
        if neg:
            score += min(len(neg) * 0.25, 0.7)
            reasons.append(f"{len(neg)} negative instruction(s)")

        # Explicit limitation section
        if re.search(r"(limitation|caveat|restriction|constraint|warning)", desc, re.IGNORECASE):
            score += 0.3
            reasons.append("explicit limitation section")

        return DimensionScore(
            dimension="boundary",
            score=_clamp(score),
            explanation=", ".join(reasons) if reasons else "no boundary signals",
        )

    def _score_stats(self, desc: str) -> DimensionScore:
        if not desc:
            return DimensionScore(dimension="stats", score=0.0, explanation="Empty")

        score = 0.0
        reasons: list[str] = []

        stat_matches = STAT_PATTERNS.findall(desc)
        if stat_matches:
            score += min(len(stat_matches) * 0.25, 0.8)
            reasons.append(f"{len(stat_matches)} statistic(s)")

        # Standalone numbers
        numbers = re.findall(r"\b\d{2,}\b", desc)
        if numbers and not stat_matches:
            score += min(len(numbers) * 0.1, 0.2)
            reasons.append(f"{len(numbers)} number(s)")

        return DimensionScore(
            dimension="stats",
            score=_clamp(score),
            explanation=", ".join(reasons) if reasons else "no statistical signals",
        )

    def _score_precision(self, desc: str) -> DimensionScore:
        if not desc:
            return DimensionScore(dimension="precision", score=0.0, explanation="Empty")

        score = 0.0
        reasons: list[str] = []

        tech = TECH_TERMS.findall(desc)
        if tech:
            score += min(len(tech) * 0.15, 0.7)
            reasons.append(f"{len(tech)} technical term(s)")

        # Protocol/format mentions
        protocols = re.findall(
            r"\b(wire protocol|file format|encoding|specification|standard|"
            r"extension|plugin|middleware|connector)\b",
            desc, re.IGNORECASE,
        )
        if protocols:
            score += min(len(protocols) * 0.15, 0.3)
            reasons.append(f"{len(protocols)} protocol reference(s)")

        return DimensionScore(
            dimension="precision",
            score=_clamp(score),
            explanation=", ".join(reasons) if reasons else "no precision signals",
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_description_optimizer/test_heuristic_analyzer.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/description_optimizer/analyzer/ tests/unit/test_description_optimizer/test_heuristic_analyzer.py
git commit -m "feat(desc-optimizer): add DescriptionAnalyzer ABC + HeuristicAnalyzer (6-dim GEO scoring)"
```

---

## Task 3: DescriptionOptimizer ABC + LLM Optimizer

**Files:**
- Create: `src/description_optimizer/optimizer/__init__.py`
- Create: `src/description_optimizer/optimizer/base.py`
- Create: `src/description_optimizer/optimizer/prompts.py`
- Create: `src/description_optimizer/optimizer/llm_optimizer.py`
- Test: `tests/unit/test_description_optimizer/test_llm_optimizer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_description_optimizer/test_llm_optimizer.py
"""Tests for LLMDescriptionOptimizer — dimension-aware rewriting."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from description_optimizer.models import AnalysisReport, DimensionScore, OptimizedDescription
from description_optimizer.optimizer.base import DescriptionOptimizer
from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer
from description_optimizer.optimizer.prompts import build_optimization_prompt, build_search_description_prompt


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    client = AsyncMock()
    # Mock the chat.completions.create response
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = (
        '{"optimized_description": "Improved description text", '
        '"search_description": "search optimized text"}'
    )
    mock_response.choices = [mock_choice]
    client.chat.completions.create.return_value = mock_response
    return client


@pytest.fixture
def optimizer(mock_openai_client: AsyncMock) -> LLMDescriptionOptimizer:
    return LLMDescriptionOptimizer(client=mock_openai_client)


@pytest.fixture
def sample_report() -> AnalysisReport:
    return AnalysisReport(
        tool_id="github::search_issues",
        original_description="Search GitHub issues.",
        dimension_scores=[
            DimensionScore(dimension="clarity", score=0.4, explanation="weak"),
            DimensionScore(dimension="disambiguation", score=0.2, explanation="missing"),
            DimensionScore(dimension="parameter_coverage", score=0.3, explanation="weak"),
            DimensionScore(dimension="boundary", score=0.1, explanation="missing"),
            DimensionScore(dimension="stats", score=0.0, explanation="none"),
            DimensionScore(dimension="precision", score=0.3, explanation="weak"),
        ],
    )


class TestLLMOptimizerIsABC:
    def test_implements_abc(self, optimizer: LLMDescriptionOptimizer) -> None:
        assert isinstance(optimizer, DescriptionOptimizer)


class TestOptimize:
    async def test_calls_openai(
        self,
        optimizer: LLMDescriptionOptimizer,
        sample_report: AnalysisReport,
        mock_openai_client: AsyncMock,
    ) -> None:
        result = await optimizer.optimize(sample_report)
        mock_openai_client.chat.completions.create.assert_called_once()

    async def test_returns_optimized_and_search(
        self,
        optimizer: LLMDescriptionOptimizer,
        sample_report: AnalysisReport,
    ) -> None:
        result = await optimizer.optimize(sample_report)
        assert result["optimized_description"] == "Improved description text"
        assert result["search_description"] == "search optimized text"

    async def test_includes_weak_dimensions_in_prompt(
        self,
        optimizer: LLMDescriptionOptimizer,
        sample_report: AnalysisReport,
        mock_openai_client: AsyncMock,
    ) -> None:
        await optimizer.optimize(sample_report)
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages", call_args[1].get("messages", []))
        user_msg = next(m for m in messages if m["role"] == "user")
        # All dimensions are weak (<0.5), so all should be mentioned
        assert "clarity" in user_msg["content"]
        assert "disambiguation" in user_msg["content"]


class TestPromptBuilding:
    def test_optimization_prompt_contains_weak_dims(self) -> None:
        weak = ["clarity", "boundary"]
        prompt = build_optimization_prompt(
            original="Search tool",
            tool_id="s::t",
            weak_dimensions=weak,
            dimension_scores={"clarity": 0.3, "boundary": 0.1},
        )
        assert "clarity" in prompt
        assert "boundary" in prompt
        assert "Search tool" in prompt

    def test_optimization_prompt_preserves_original(self) -> None:
        prompt = build_optimization_prompt(
            original="My special tool for X",
            tool_id="s::t",
            weak_dimensions=["clarity"],
            dimension_scores={"clarity": 0.3},
        )
        assert "My special tool for X" in prompt

    def test_search_description_prompt(self) -> None:
        prompt = build_search_description_prompt(
            optimized="An improved tool description.",
            tool_id="s::t",
        )
        assert "An improved tool description" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_description_optimizer/test_llm_optimizer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the ABC**

```python
# src/description_optimizer/optimizer/__init__.py
"""Description optimization module."""

# src/description_optimizer/optimizer/base.py
"""Abstract base class for description optimizers."""

from abc import ABC, abstractmethod

from description_optimizer.models import AnalysisReport


class DescriptionOptimizer(ABC):
    """ABC for optimizing MCP tool descriptions.

    Takes an AnalysisReport (with weak dimension info) and produces
    an optimized description + search description.
    """

    @abstractmethod
    async def optimize(self, report: AnalysisReport) -> dict[str, str]:
        """Optimize a tool description based on its analysis report.

        Args:
            report: AnalysisReport with GEO scores and weak dimensions.

        Returns:
            Dict with keys: 'optimized_description', 'search_description'.
        """
        ...
```

- [ ] **Step 4: Implement prompts module**

```python
# src/description_optimizer/optimizer/prompts.py
"""Prompt templates for LLM-based description optimization.

GEO dimension definitions (from docs/design/metrics-rubric.md):
- clarity: Purpose + when-to-use + specific scope
- disambiguation: Contrast with similar tools
- parameter_coverage: Input parameter docs
- boundary: What the tool does NOT do
- stats: Quantitative info (counts, latency, coverage)
- precision: Technical terms, protocols, standards
"""

SYSTEM_PROMPT = """You are a technical writer specializing in MCP (Model Context Protocol) tool descriptions.
Your goal is to rewrite tool descriptions so they are optimally discoverable by both LLM-based search systems and human readers.

Rules:
1. PRESERVE all factual information from the original — never add capabilities the tool doesn't have.
2. IMPROVE weak dimensions identified in the analysis without degrading strong ones.
3. Keep descriptions concise (50-200 words for optimized, 30-80 words for search).
4. Use active voice and action verbs.
5. Return valid JSON with exactly two keys: "optimized_description" and "search_description".
"""


def build_optimization_prompt(
    original: str,
    tool_id: str,
    weak_dimensions: list[str],
    dimension_scores: dict[str, float],
) -> str:
    """Build the user prompt for description optimization.

    Args:
        original: The original tool description.
        tool_id: The tool's ID (server_id::tool_name).
        weak_dimensions: List of dimension names scoring below threshold.
        dimension_scores: All dimension name→score pairs.

    Returns:
        User prompt string.
    """
    scores_text = "\n".join(f"  - {dim}: {score:.2f}" for dim, score in dimension_scores.items())
    weak_text = ", ".join(weak_dimensions) if weak_dimensions else "none"

    dimension_guidance = {
        "clarity": "Add clear action verb at the start. Specify WHAT the tool does and WHEN to use it. Include specific data sources or scope.",
        "disambiguation": "Add contrast phrases: 'unlike X', 'specifically for Y', 'only handles Z'. Differentiate from similar tools.",
        "parameter_coverage": "Mention key input parameters with types or constraints. E.g., 'Accepts a `query` string and optional `limit` integer.'",
        "boundary": "Add explicit limitations: 'Does NOT handle X', 'Cannot Y', 'Not suitable for Z'.",
        "stats": "Add quantitative information if known: coverage numbers, response times, limits. E.g., 'Searches across 10K+ repositories.'",
        "precision": "Use precise technical terms: protocol names, data formats, standards. E.g., 'via the PostgreSQL wire protocol'.",
    }

    guidance_lines = []
    for dim in weak_dimensions:
        if dim in dimension_guidance:
            guidance_lines.append(f"  - **{dim}** ({dimension_scores.get(dim, 0):.2f}): {dimension_guidance[dim]}")

    guidance_text = "\n".join(guidance_lines) if guidance_lines else "  All dimensions are adequate."

    return f"""Optimize this MCP tool description.

**Tool ID**: {tool_id}

**Original Description**:
{original}

**Current GEO Scores** (0.0-1.0):
{scores_text}

**Weak Dimensions** (need improvement): {weak_text}

**Improvement Guidance**:
{guidance_text}

Rewrite the description to improve the weak dimensions while preserving all original meaning. Return JSON:
{{"optimized_description": "...", "search_description": "..."}}

The `optimized_description` should be readable by both humans and machines (50-200 words).
The `search_description` should be a dense, keyword-rich version optimized for embedding-based vector search (30-80 words). Include likely search queries a user would type to find this tool."""


def build_search_description_prompt(optimized: str, tool_id: str) -> str:
    """Build prompt for generating a search-optimized description.

    Args:
        optimized: The optimized description.
        tool_id: The tool's ID.

    Returns:
        User prompt string.
    """
    return f"""Create a search-optimized description for embedding-based retrieval.

**Tool ID**: {tool_id}
**Optimized Description**: {optimized}

Generate a dense, keyword-rich version (30-80 words) that includes:
- Core functionality keywords
- Likely search queries users would type
- Technical terms and domain vocabulary
- Action verbs describing what the tool does

Return just the search description text, no JSON."""
```

- [ ] **Step 5: Implement LLMDescriptionOptimizer**

```python
# src/description_optimizer/optimizer/llm_optimizer.py
"""LLM-based description optimizer using GPT-4o-mini."""

import json

from loguru import logger
from openai import AsyncOpenAI

from description_optimizer.models import AnalysisReport
from description_optimizer.optimizer.base import DescriptionOptimizer
from description_optimizer.optimizer.prompts import SYSTEM_PROMPT, build_optimization_prompt


class LLMDescriptionOptimizer(DescriptionOptimizer):
    """Optimizes tool descriptions using GPT-4o-mini with dimension-aware prompting."""

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature

    async def optimize(self, report: AnalysisReport) -> dict[str, str]:
        """Optimize a description based on its GEO analysis report.

        Args:
            report: AnalysisReport with dimension scores.

        Returns:
            Dict with 'optimized_description' and 'search_description'.
        """
        weak_dims = report.weak_dimensions(threshold=0.5)
        dim_scores = {s.dimension: s.score for s in report.dimension_scores}

        prompt = build_optimization_prompt(
            original=report.original_description,
            tool_id=report.tool_id,
            weak_dimensions=weak_dims,
            dimension_scores=dim_scores,
        )

        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response as JSON: {content[:200]}")
            raise

        if "optimized_description" not in result or "search_description" not in result:
            logger.error(f"LLM response missing required keys: {list(result.keys())}")
            raise ValueError("LLM response must contain 'optimized_description' and 'search_description'")

        logger.info(
            f"Optimized {report.tool_id}: "
            f"weak_dims={weak_dims}, "
            f"original_len={len(report.original_description)}, "
            f"optimized_len={len(result['optimized_description'])}"
        )

        return {
            "optimized_description": result["optimized_description"],
            "search_description": result["search_description"],
        }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_description_optimizer/test_llm_optimizer.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/description_optimizer/optimizer/ tests/unit/test_description_optimizer/test_llm_optimizer.py
git commit -m "feat(desc-optimizer): add DescriptionOptimizer ABC + LLM optimizer with dimension-aware prompts"
```

---

## Task 4: Quality Gate

**Files:**
- Create: `src/description_optimizer/quality_gate.py`
- Test: `tests/unit/test_description_optimizer/test_quality_gate.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_description_optimizer/test_quality_gate.py
"""Tests for QualityGate — validates optimization doesn't degrade quality."""

import numpy as np
import pytest

from description_optimizer.models import AnalysisReport, DimensionScore
from description_optimizer.quality_gate import GateResult, QualityGate


@pytest.fixture
def gate() -> QualityGate:
    return QualityGate(
        min_similarity=0.85,
        allow_geo_decrease=False,
    )


def _make_report(tool_id: str, desc: str, scores: dict[str, float]) -> AnalysisReport:
    """Helper to create an AnalysisReport with given dimension scores."""
    return AnalysisReport(
        tool_id=tool_id,
        original_description=desc,
        dimension_scores=[
            DimensionScore(dimension=dim, score=s, explanation="test")
            for dim, s in scores.items()
        ],
    )


class TestGeoScoreGate:
    def test_pass_when_improved(self, gate: QualityGate) -> None:
        before = _make_report("s::t", "old", {
            "clarity": 0.3, "disambiguation": 0.2, "parameter_coverage": 0.3,
            "boundary": 0.1, "stats": 0.0, "precision": 0.2,
        })
        after = _make_report("s::t", "new", {
            "clarity": 0.7, "disambiguation": 0.5, "parameter_coverage": 0.6,
            "boundary": 0.4, "stats": 0.3, "precision": 0.5,
        })
        result = gate.check_geo_score(before, after)
        assert result.passed is True

    def test_fail_when_degraded(self, gate: QualityGate) -> None:
        before = _make_report("s::t", "old", {
            "clarity": 0.7, "disambiguation": 0.6, "parameter_coverage": 0.5,
            "boundary": 0.4, "stats": 0.3, "precision": 0.5,
        })
        after = _make_report("s::t", "new", {
            "clarity": 0.3, "disambiguation": 0.2, "parameter_coverage": 0.3,
            "boundary": 0.1, "stats": 0.0, "precision": 0.2,
        })
        result = gate.check_geo_score(before, after)
        assert result.passed is False
        assert "degraded" in result.reason.lower() or "decreased" in result.reason.lower()

    def test_pass_when_equal(self, gate: QualityGate) -> None:
        scores = {
            "clarity": 0.5, "disambiguation": 0.5, "parameter_coverage": 0.5,
            "boundary": 0.5, "stats": 0.5, "precision": 0.5,
        }
        before = _make_report("s::t", "old", scores)
        after = _make_report("s::t", "new", scores)
        result = gate.check_geo_score(before, after)
        assert result.passed is True


class TestSemanticSimilarityGate:
    def test_pass_high_similarity(self, gate: QualityGate) -> None:
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.95, 0.1, 0.05])
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed is True

    def test_fail_low_similarity(self, gate: QualityGate) -> None:
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.0, 1.0, 0.0])
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed is False

    def test_identical_vectors(self, gate: QualityGate) -> None:
        vec = np.array([0.5, 0.5, 0.5])
        result = gate.check_semantic_similarity(vec, vec)
        assert result.passed is True
        assert result.similarity == pytest.approx(1.0)


class TestFullGate:
    def test_all_pass(self, gate: QualityGate) -> None:
        before = _make_report("s::t", "old", {
            "clarity": 0.3, "disambiguation": 0.2, "parameter_coverage": 0.3,
            "boundary": 0.1, "stats": 0.0, "precision": 0.2,
        })
        after = _make_report("s::t", "new improved", {
            "clarity": 0.7, "disambiguation": 0.5, "parameter_coverage": 0.6,
            "boundary": 0.4, "stats": 0.3, "precision": 0.5,
        })
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.95, 0.1, 0.05])
        result = gate.evaluate(before, after, vec_a, vec_b)
        assert result.passed is True

    def test_fail_if_any_fails(self, gate: QualityGate) -> None:
        before = _make_report("s::t", "old", {
            "clarity": 0.7, "disambiguation": 0.6, "parameter_coverage": 0.5,
            "boundary": 0.4, "stats": 0.3, "precision": 0.5,
        })
        after = _make_report("s::t", "worse", {
            "clarity": 0.3, "disambiguation": 0.2, "parameter_coverage": 0.2,
            "boundary": 0.1, "stats": 0.0, "precision": 0.1,
        })
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.95, 0.1, 0.05])
        result = gate.evaluate(before, after, vec_a, vec_b)
        assert result.passed is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_description_optimizer/test_quality_gate.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement QualityGate**

```python
# src/description_optimizer/quality_gate.py
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
                reason=f"GEO score decreased from {before.geo_score:.3f} to {after.geo_score:.3f}",
            )

        logger.info(
            f"GEO gate passed for {before.tool_id}: "
            f"{before.geo_score:.3f} → {after.geo_score:.3f}"
        )
        return GateResult(
            passed=True,
            reason=f"GEO score maintained/improved: {before.geo_score:.3f} → {after.geo_score:.3f}",
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
                reason=f"Semantic similarity {similarity:.3f} below threshold {self._min_similarity}",
                similarity=similarity,
            )

        return GateResult(
            passed=True,
            reason=f"Semantic similarity {similarity:.3f} >= {self._min_similarity}",
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_description_optimizer/test_quality_gate.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/description_optimizer/quality_gate.py tests/unit/test_description_optimizer/test_quality_gate.py
git commit -m "feat(desc-optimizer): add QualityGate — GEO score + semantic similarity validation"
```

---

## Task 5: Optimization Pipeline (Orchestrator)

**Files:**
- Create: `src/description_optimizer/pipeline.py`
- Test: `tests/unit/test_description_optimizer/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_description_optimizer/test_pipeline.py
"""Tests for OptimizationPipeline — orchestrates analyze → optimize → gate."""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from description_optimizer.models import (
    AnalysisReport,
    DimensionScore,
    OptimizationStatus,
    OptimizedDescription,
)
from description_optimizer.pipeline import OptimizationPipeline
from description_optimizer.quality_gate import FullGateResult, GateResult


def _make_report(geo: float, desc: str = "test") -> AnalysisReport:
    return AnalysisReport(
        tool_id="s::t",
        original_description=desc,
        dimension_scores=[
            DimensionScore(dimension=d, score=geo, explanation="test")
            for d in ["clarity", "disambiguation", "parameter_coverage", "boundary", "stats", "precision"]
        ],
    )


@pytest.fixture
def mock_analyzer() -> AsyncMock:
    analyzer = AsyncMock()
    analyzer.analyze.return_value = _make_report(0.3, "original desc")
    return analyzer


@pytest.fixture
def mock_optimizer() -> AsyncMock:
    optimizer = AsyncMock()
    optimizer.optimize.return_value = {
        "optimized_description": "improved desc",
        "search_description": "search desc",
    }
    return optimizer


@pytest.fixture
def mock_embedder() -> AsyncMock:
    embedder = AsyncMock()
    # Return similar vectors
    embedder.embed_one.side_effect = [
        np.array([1.0, 0.0, 0.0]),  # original
        np.array([0.95, 0.1, 0.05]),  # optimized
    ]
    return embedder


@pytest.fixture
def mock_gate() -> MagicMock:
    gate = MagicMock()
    gate.evaluate.return_value = FullGateResult(
        passed=True,
        geo_result=GateResult(passed=True, reason="ok"),
        similarity_result=GateResult(passed=True, reason="ok", similarity=0.95),
    )
    return gate


@pytest.fixture
def pipeline(mock_analyzer, mock_optimizer, mock_embedder, mock_gate) -> OptimizationPipeline:
    return OptimizationPipeline(
        analyzer=mock_analyzer,
        optimizer=mock_optimizer,
        embedder=mock_embedder,
        gate=mock_gate,
    )


class TestPipelineSuccess:
    async def test_full_pipeline(self, pipeline: OptimizationPipeline) -> None:
        result = await pipeline.run("s::t", "original desc")
        assert isinstance(result, OptimizedDescription)
        assert result.status == OptimizationStatus.SUCCESS
        assert result.optimized_description == "improved desc"
        assert result.search_description == "search desc"

    async def test_calls_analyzer_first(
        self, pipeline: OptimizationPipeline, mock_analyzer: AsyncMock
    ) -> None:
        await pipeline.run("s::t", "test")
        mock_analyzer.analyze.assert_called_once_with("s::t", "test")

    async def test_calls_optimizer_with_report(
        self, pipeline: OptimizationPipeline, mock_optimizer: AsyncMock
    ) -> None:
        await pipeline.run("s::t", "test")
        mock_optimizer.optimize.assert_called_once()

    async def test_calls_gate_with_embeddings(
        self, pipeline: OptimizationPipeline, mock_gate: MagicMock
    ) -> None:
        await pipeline.run("s::t", "test")
        mock_gate.evaluate.assert_called_once()


class TestPipelineSkip:
    async def test_skip_when_high_geo_score(self, pipeline: OptimizationPipeline, mock_analyzer: AsyncMock) -> None:
        mock_analyzer.analyze.return_value = _make_report(0.85, "already great")
        result = await pipeline.run("s::t", "already great")
        assert result.status == OptimizationStatus.SKIPPED
        assert result.skip_reason is not None

    async def test_skip_preserves_original(self, pipeline: OptimizationPipeline, mock_analyzer: AsyncMock) -> None:
        mock_analyzer.analyze.return_value = _make_report(0.85, "already great")
        result = await pipeline.run("s::t", "already great")
        assert result.original_description == "already great"
        assert result.optimized_description == "already great"


class TestPipelineGateRejection:
    async def test_gate_rejected(self, pipeline: OptimizationPipeline, mock_gate: MagicMock) -> None:
        mock_gate.evaluate.return_value = FullGateResult(
            passed=False,
            geo_result=GateResult(passed=False, reason="GEO decreased"),
            similarity_result=GateResult(passed=True, reason="ok", similarity=0.9),
        )
        result = await pipeline.run("s::t", "test")
        assert result.status == OptimizationStatus.GATE_REJECTED


class TestPipelineBatch:
    async def test_batch_optimize(self, pipeline: OptimizationPipeline) -> None:
        tools = [("s::t1", "desc 1"), ("s::t2", "desc 2"), ("s::t3", "desc 3")]
        results = await pipeline.run_batch(tools)
        assert len(results) == 3
        assert all(isinstance(r, OptimizedDescription) for r in results)


class TestPipelineEmptyDescription:
    async def test_empty_description(self, pipeline: OptimizationPipeline) -> None:
        result = await pipeline.run("s::t", "")
        assert isinstance(result, OptimizedDescription)

    async def test_none_description(self, pipeline: OptimizationPipeline) -> None:
        result = await pipeline.run("s::t", None)
        assert isinstance(result, OptimizedDescription)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_description_optimizer/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement OptimizationPipeline**

```python
# src/description_optimizer/pipeline.py
"""Orchestrates the description optimization pipeline.

Flow: analyze → (skip if high GEO) → optimize → re-analyze → gate → result
"""

from loguru import logger

from description_optimizer.analyzer.base import DescriptionAnalyzer
from description_optimizer.models import OptimizationStatus, OptimizedDescription
from description_optimizer.optimizer.base import DescriptionOptimizer
from description_optimizer.quality_gate import QualityGate
from embedding.base import Embedder


class OptimizationPipeline:
    """End-to-end description optimization: analyze → optimize → validate."""

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
            logger.info(f"Skipping {tool_id}: GEO={report_before.geo_score:.3f} >= {self._skip_threshold}")
            return OptimizedDescription(
                tool_id=tool_id,
                original_description=desc,
                optimized_description=desc,
                search_description=desc,
                geo_score_before=report_before.geo_score,
                geo_score_after=report_before.geo_score,
                status=OptimizationStatus.SKIPPED,
                skip_reason=f"GEO score {report_before.geo_score:.3f} already above threshold {self._skip_threshold}",
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
            f"GEO {report_before.geo_score:.3f} → {report_after.geo_score:.3f}"
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

    async def run_batch(
        self, tools: list[tuple[str, str | None]]
    ) -> list[OptimizedDescription]:
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_description_optimizer/test_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/description_optimizer/pipeline.py tests/unit/test_description_optimizer/test_pipeline.py
git commit -m "feat(desc-optimizer): add OptimizationPipeline orchestrator — analyze → optimize → gate"
```

---

## Task 6: CLI Script

**Files:**
- Create: `scripts/optimize_descriptions.py`

- [ ] **Step 1: Implement the CLI script**

```python
# scripts/optimize_descriptions.py
"""CLI script to optimize MCP tool descriptions.

Usage:
    uv run python scripts/optimize_descriptions.py
    uv run python scripts/optimize_descriptions.py --input data/raw/servers.jsonl
    uv run python scripts/optimize_descriptions.py --dry-run
    uv run python scripts/optimize_descriptions.py --skip-threshold 0.8
"""

import argparse
import asyncio
import json
from pathlib import Path

from loguru import logger
from openai import AsyncOpenAI

from config import Settings
from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import OptimizationStatus
from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer
from description_optimizer.pipeline import OptimizationPipeline
from description_optimizer.quality_gate import QualityGate
from embedding.openai_embedder import OpenAIEmbedder


async def main(args: argparse.Namespace) -> None:
    settings = Settings()
    input_path = Path(args.input)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return

    # Load servers and extract tools
    tools: list[tuple[str, str | None]] = []
    with open(input_path) as f:
        for line in f:
            server = json.loads(line.strip())
            for tool in server.get("tools", []):
                tool_id = f"{server['server_id']}::{tool['tool_name']}"
                tools.append((tool_id, tool.get("description")))

    logger.info(f"Loaded {len(tools)} tools from {input_path}")

    if args.dry_run:
        # Dry run: only analyze, don't optimize
        analyzer = HeuristicAnalyzer()
        for tool_id, desc in tools:
            report = await analyzer.analyze(tool_id, desc)
            weak = report.weak_dimensions()
            logger.info(
                f"{tool_id}: GEO={report.geo_score:.3f}, "
                f"weak=[{', '.join(weak)}]"
            )
        return

    # Full pipeline
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    analyzer = HeuristicAnalyzer()
    optimizer = LLMDescriptionOptimizer(client=openai_client)
    embedder = OpenAIEmbedder(client=openai_client)
    gate = QualityGate(min_similarity=0.85)
    pipeline = OptimizationPipeline(
        analyzer=analyzer,
        optimizer=optimizer,
        embedder=embedder,
        gate=gate,
        skip_threshold=args.skip_threshold,
    )

    results = await pipeline.run_batch(tools)

    # Summary
    success = sum(1 for r in results if r.status == OptimizationStatus.SUCCESS)
    skipped = sum(1 for r in results if r.status == OptimizationStatus.SKIPPED)
    failed = sum(1 for r in results if r.status == OptimizationStatus.FAILED)
    rejected = sum(1 for r in results if r.status == OptimizationStatus.GATE_REJECTED)

    logger.info(
        f"Optimization complete: {success} success, {skipped} skipped, "
        f"{failed} failed, {rejected} gate-rejected"
    )

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for r in results:
            f.write(r.model_dump_json() + "\n")

    logger.info(f"Results saved to {output_path}")

    # Print improvement summary
    if success > 0:
        avg_improvement = sum(r.improvement for r in results if r.status == OptimizationStatus.SUCCESS) / success
        logger.info(f"Average GEO improvement: +{avg_improvement:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize MCP tool descriptions")
    parser.add_argument("--input", default="data/raw/servers.jsonl")
    parser.add_argument("--output", default="data/optimized/descriptions.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="Only analyze, don't optimize")
    parser.add_argument("--skip-threshold", type=float, default=0.75)
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
```

- [ ] **Step 2: Commit**

```bash
git add scripts/optimize_descriptions.py
git commit -m "feat(desc-optimizer): add CLI script for batch description optimization"
```

---

## Task 7: Evaluation — A/B Test (Original vs Optimized Precision@1)

**Files:**
- Create: `tests/evaluation/test_optimizer_evaluation.py`
- Create: `description_optimizer/docs/evaluation-design.md`

- [ ] **Step 1: Write the evaluation design document**

```markdown
# Description Optimizer — Evaluation Design

> 최종 업데이트: 2026-03-28

---

## 평가 목표

Description Optimizer가 실제로 검색 선택률(Precision@1)을 향상시키는지 검증.

## 평가 5단계

### Stage 1: Unit-level Quality (Task 1-5에서 완료)
- 모든 컴포넌트 단위 테스트 통과
- GEO Score 계산 정확성
- Quality Gate 작동 검증

### Stage 2: Description Quality Delta
- 최적화 전후 GEO Score 비교
- 목표: 평균 GEO Score +0.2 이상 향상
- 최소 80% 도구에서 GEO Score 비하락

### Stage 3: Semantic Preservation
- Cosine similarity(original, optimized) >= 0.85
- LLM-as-Judge 의미 보존 검증 (future)

### Stage 4: Offline A/B Test (Primary)
- Control: 원본 description으로 Qdrant 인덱싱 → 검색
- Treatment: 최적화 description으로 인덱싱 → 검색
- 동일 Ground Truth 사용
- Primary: Precision@1 delta
- Secondary: Recall@10, MRR delta

### Stage 5: Statistical Significance
- McNemar's test (paired, binary outcome)
- 유의수준: p < 0.05
- 최소 효과 크기: +5%p Precision@1

## 성공 기준

| 지표 | 목표 | 방법 |
|------|------|------|
| GEO Score delta | +0.2 avg | Before/after comparison |
| Semantic preservation | >= 0.85 cosine | Embedding similarity |
| Precision@1 delta | +10%p | A/B test |
| No regression | 0 tools worse | Gate verification |
```

- [ ] **Step 2: Write evaluation tests**

```python
# tests/evaluation/test_optimizer_evaluation.py
"""Evaluation tests for Description Optimizer.

These tests verify the optimizer's impact on retrieval performance.
They require external API keys and are guarded by skipif.

Stage 2: GEO Score improvement
Stage 3: Semantic preservation
Stage 4: Precision@1 A/B test (future, requires full pipeline setup)
"""

import os

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
        "Searches GitHub Issues matching a text query. Use when you need to find bug reports, "
        "feature requests, or discussions in a specific repository. Unlike the PR search tool, "
        "this only searches Issues, not Pull Requests. Cannot search across multiple repositories "
        "in a single call. Returns up to 100 results per page via the GitHub REST API v3.",
    ),
    (
        "postgres::run_query",
        "Executes read-only SQL queries against a PostgreSQL database via the wire protocol. "
        "Use when you need to retrieve structured data. Supports JSON, JSONB, and ARRAY column types. "
        "Cannot execute DDL (CREATE/DROP) or DML (INSERT/UPDATE/DELETE) statements. "
        "Query timeout: 30 seconds. Maximum result size: 10,000 rows.",
    ),
]


class TestGEOScoreDifferentiation:
    """Stage 2: Verify HeuristicAnalyzer distinguishes poor vs good descriptions."""

    async def test_poor_descriptions_score_low(self, analyzer: HeuristicAnalyzer) -> None:
        for tool_id, desc in SAMPLE_POOR_DESCRIPTIONS:
            report = await analyzer.analyze(tool_id, desc)
            assert report.geo_score < 0.4, f"{tool_id}: GEO={report.geo_score:.3f} too high for poor desc"

    async def test_good_descriptions_score_high(self, analyzer: HeuristicAnalyzer) -> None:
        for tool_id, desc in SAMPLE_GOOD_DESCRIPTIONS:
            report = await analyzer.analyze(tool_id, desc)
            assert report.geo_score > 0.4, f"{tool_id}: GEO={report.geo_score:.3f} too low for good desc"

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
```

- [ ] **Step 3: Run evaluation tests**

Run: `uv run pytest tests/evaluation/test_optimizer_evaluation.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/evaluation/test_optimizer_evaluation.py description_optimizer/docs/evaluation-design.md
git commit -m "test(desc-optimizer): add evaluation tests — GEO score differentiation + dimension coverage"
```

---

## Task 8: Integration Test (Full Pipeline with Mocked LLM)

**Files:**
- Create: `tests/integration/test_description_optimizer_integration.py`

- [ ] **Step 1: Write integration tests**

```python
# tests/integration/test_description_optimizer_integration.py
"""Integration tests for Description Optimizer pipeline.

Tests the full pipeline with mocked LLM but real analyzer and gate.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import OptimizationStatus
from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer
from description_optimizer.pipeline import OptimizationPipeline
from description_optimizer.quality_gate import QualityGate


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    """Mock OpenAI client that returns a realistic optimized description."""
    client = AsyncMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "optimized_description": (
            "Searches GitHub Issues matching a text query via the GitHub REST API v3. "
            "Use when you need to find bug reports or feature requests in a repository. "
            "Unlike the PR search tool, this only searches Issues. "
            "Cannot search across multiple repositories. Returns up to 100 results."
        ),
        "search_description": (
            "github issues search query bug report feature request "
            "repository REST API find issues text search filter"
        ),
    })
    mock_response.choices = [mock_choice]
    client.chat.completions.create.return_value = mock_response
    return client


@pytest.fixture
def mock_embedder() -> AsyncMock:
    """Mock embedder returning similar vectors."""
    embedder = AsyncMock()
    base = np.random.randn(1536)
    base = base / np.linalg.norm(base)
    noise = np.random.randn(1536) * 0.05
    similar = base + noise
    similar = similar / np.linalg.norm(similar)

    embedder.embed_one.side_effect = [base, similar, base, similar]
    return embedder


@pytest.fixture
def pipeline(mock_openai_client, mock_embedder) -> OptimizationPipeline:
    return OptimizationPipeline(
        analyzer=HeuristicAnalyzer(),
        optimizer=LLMDescriptionOptimizer(client=mock_openai_client),
        embedder=mock_embedder,
        gate=QualityGate(min_similarity=0.85),
        skip_threshold=0.75,
    )


class TestFullPipelineIntegration:
    async def test_poor_description_gets_optimized(self, pipeline: OptimizationPipeline) -> None:
        result = await pipeline.run("github::search_issues", "Search issues")
        assert result.status == OptimizationStatus.SUCCESS
        assert len(result.optimized_description) > len(result.original_description)
        assert result.geo_score_after >= result.geo_score_before

    async def test_batch_processing(self, pipeline: OptimizationPipeline, mock_embedder: AsyncMock) -> None:
        # Reset side_effect for batch
        base = np.random.randn(1536)
        base = base / np.linalg.norm(base)
        noise = np.random.randn(1536) * 0.05
        similar = base + noise
        similar = similar / np.linalg.norm(similar)
        mock_embedder.embed_one.side_effect = [base, similar] * 3

        tools = [
            ("s::t1", "A search tool"),
            ("s::t2", "File reader"),
            ("s::t3", "Database connector"),
        ]
        results = await pipeline.run_batch(tools)
        assert len(results) == 3
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/integration/test_description_optimizer_integration.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_description_optimizer_integration.py
git commit -m "test(desc-optimizer): add integration tests — full pipeline with mocked LLM"
```

---

## Task 9: Run Full Test Suite + Lint

- [ ] **Step 1: Run lint and format**

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

- [ ] **Step 2: Run full test suite with coverage**

```bash
uv run pytest tests/ --cov=src -v
```

Expected: ALL PASS, coverage >= 80%

- [ ] **Step 3: Fix any issues found**

If lint or test failures, fix them.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore(desc-optimizer): fix lint + ensure full test suite passes"
```

---

## Task 10: Documentation Update

**Files:**
- Modify: `description_optimizer/CLAUDE.md` (if needed)
- Create: `description_optimizer/docs/evaluation-design.md` (if not created in Task 7)

- [ ] **Step 1: Verify all docs are current**

Check that:
- `description_optimizer/CLAUDE.md` reflects actual implementation
- `description_optimizer/docs/research-analysis.md` is complete
- `description_optimizer/docs/evaluation-design.md` exists

- [ ] **Step 2: Update root checklist**

Note: Do NOT modify root `docs/plan/checklist.md` — this is a separate branch feature. Document the feature status in `description_optimizer/` only.

- [ ] **Step 3: Commit docs**

```bash
git add description_optimizer/
git commit -m "docs(desc-optimizer): finalize documentation — research analysis, evaluation design, CLAUDE.md"
```
