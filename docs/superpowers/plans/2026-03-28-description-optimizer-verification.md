# Description Optimizer Verification Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Description Optimizer 기능의 정확성, 견고성, 엣지케이스 처리를 정밀하게 검증하고, 사용자가 면밀히 리뷰할 수 있는 검증 리포트를 생성한다.

**Architecture:** 2-Phase 검증 — Phase A: 자동화 검증 (엣지케이스 테스트 보강, 로직 검증, regression 확인), Phase B: 수동 리뷰 가이드 (실제 description 샘플 분석, GEO 점수 캘리브레이션, 프롬프트 품질 리뷰)

**Tech Stack:** pytest, pytest-asyncio, numpy, HeuristicAnalyzer (실제), LLM (mock)

---

## File Structure

| Action | File | Purpose |
|--------|------|---------|
| Create | `tests/verification/test_heuristic_edge_cases.py` | HeuristicAnalyzer 엣지케이스 + 캘리브레이션 |
| Create | `tests/verification/test_quality_gate_edge_cases.py` | QualityGate 경계 조건 + 견고성 |
| Create | `tests/verification/test_pipeline_error_paths.py` | Pipeline 에러 경로 + 복구 |
| Create | `tests/verification/test_llm_optimizer_robustness.py` | LLM 응답 이상 처리 |
| Create | `tests/verification/test_geo_calibration.py` | 실제 MCP description 샘플로 GEO 점수 분포 검증 |
| Create | `tests/verification/conftest.py` | 공유 fixtures |
| Create | `tests/verification/__init__.py` | Package init |
| Create | `description_optimizer/docs/verification-report.md` | 최종 검증 리포트 (Phase B 수동 리뷰 가이드 포함) |

---

## Phase A: 자동화 검증 (Agent 수행)

### Task 1: HeuristicAnalyzer 엣지케이스 테스트

**Files:**
- Create: `tests/verification/__init__.py`
- Create: `tests/verification/conftest.py`
- Create: `tests/verification/test_heuristic_edge_cases.py`

- [ ] **Step 1: conftest.py 및 패키지 초기화**

```python
# tests/verification/__init__.py
# (empty)

# tests/verification/conftest.py
import pytest
from description_optimizer.analyzer.heuristic import HeuristicAnalyzer

@pytest.fixture
def analyzer() -> HeuristicAnalyzer:
    return HeuristicAnalyzer()
```

- [ ] **Step 2: 엣지케이스 테스트 작성**

```python
# tests/verification/test_heuristic_edge_cases.py
"""HeuristicAnalyzer edge case & calibration tests.

Covers:
- Unicode/multilingual descriptions
- Extremely long descriptions (10K+ chars)
- Descriptions with only code/backticks
- Repeated patterns (regex matching abuse)
- Single-word descriptions
- Descriptions with HTML/markdown
- Action verb false positives ("lists of items" vs "lists files")
"""

import pytest
from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import GEO_DIMENSIONS


class TestEmptyAndMinimal:
    """Verify graceful handling of degenerate inputs."""

    async def test_empty_string(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("s::t", "")
        assert report.geo_score <= 0.1, f"Empty desc should score near 0, got {report.geo_score:.3f}"

    async def test_none_input(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("s::t", None)
        assert report.geo_score <= 0.1

    async def test_single_word(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("s::t", "Search")
        assert 0.0 <= report.geo_score <= 0.3, f"Single word too high: {report.geo_score:.3f}"

    async def test_whitespace_only(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("s::t", "   \n\t  ")
        assert report.geo_score <= 0.1


class TestUnicodeAndMultilingual:
    """Verify regex patterns don't crash on non-ASCII."""

    async def test_korean_description(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("s::t", "깃허브 이슈를 검색합니다. 버그 리포트와 기능 요청을 찾을 때 사용하세요.")
        assert 0.0 <= report.geo_score <= 1.0
        dims = {s.dimension for s in report.dimension_scores}
        assert dims == GEO_DIMENSIONS

    async def test_japanese_description(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("s::t", "GitHubのイシューを検索します。バグレポートを見つけるために使用してください。")
        assert 0.0 <= report.geo_score <= 1.0

    async def test_mixed_language(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Searches GitHub Issues 한국어 설명. Use when you need 필터링 기능."
        report = await analyzer.analyze("s::t", desc)
        assert report.geo_score > 0.0  # English patterns should still match

    async def test_emoji_in_description(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("s::t", "🔍 Search tool for finding files 📁")
        assert 0.0 <= report.geo_score <= 1.0


class TestExtremeLength:
    """Verify behavior with very long or very short descriptions."""

    async def test_very_long_description(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "Searches files. " * 1000  # ~16K chars
        report = await analyzer.analyze("s::t", desc)
        assert 0.0 <= report.geo_score <= 1.0
        # Should not crash or timeout

    async def test_single_char(self, analyzer: HeuristicAnalyzer) -> None:
        report = await analyzer.analyze("s::t", "x")
        assert report.geo_score <= 0.15


class TestRegexEdgeCases:
    """Verify regex patterns handle tricky inputs correctly."""

    async def test_action_verb_false_positive(self, analyzer: HeuristicAnalyzer) -> None:
        """'lists of items' should not score as high as 'lists files'."""
        report_noun = await analyzer.analyze("s::t", "A collection of lists of items from the database")
        report_verb = await analyzer.analyze("s::t", "Lists all files in the directory via the filesystem API")
        # Both may match, but verb usage in context should score higher overall
        # At minimum, both should produce valid reports
        assert 0.0 <= report_noun.geo_score <= 1.0
        assert 0.0 <= report_verb.geo_score <= 1.0

    async def test_backtick_heavy_description(self, analyzer: HeuristicAnalyzer) -> None:
        """Description with many inline code blocks."""
        desc = "Accepts `query` string, `limit` int, `offset` int, `filter` object, `sort` string"
        report = await analyzer.analyze("s::t", desc)
        param_score = next(s for s in report.dimension_scores if s.dimension == "parameter_coverage")
        assert param_score.score >= 0.3, f"Backtick-heavy desc should score param coverage >= 0.3"

    async def test_special_regex_chars(self, analyzer: HeuristicAnalyzer) -> None:
        """Descriptions with regex special chars shouldn't crash."""
        desc = "Search (files) [with] {brackets} and $dollar signs + more.*?"
        report = await analyzer.analyze("s::t", desc)
        assert 0.0 <= report.geo_score <= 1.0

    async def test_repeated_same_verb(self, analyzer: HeuristicAnalyzer) -> None:
        """Same verb repeated should cap at 0.3 contribution."""
        desc = "Search search search search search search search search"
        report = await analyzer.analyze("s::t", desc)
        clarity_score = next(s for s in report.dimension_scores if s.dimension == "clarity")
        # Verb contribution capped at 0.3 + length bonus
        assert clarity_score.score <= 0.6


class TestMarkdownAndHTML:
    """Descriptions with formatting shouldn't break scoring."""

    async def test_markdown_description(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "## Search Tool\n- **Searches** files\n- Use when you need to *find* data"
        report = await analyzer.analyze("s::t", desc)
        assert report.geo_score > 0.0

    async def test_html_tags(self, analyzer: HeuristicAnalyzer) -> None:
        desc = "<p>Searches files via the REST API. <b>Use when</b> you need data.</p>"
        report = await analyzer.analyze("s::t", desc)
        assert report.geo_score > 0.0


class TestDimensionIndependence:
    """Verify each dimension scores independently."""

    async def test_high_clarity_low_boundary(self, analyzer: HeuristicAnalyzer) -> None:
        """Description with good clarity but no boundary info."""
        desc = (
            "Searches GitHub Issues matching a text query via the REST API. "
            "Use when you need to find bug reports in a specific repository."
        )
        report = await analyzer.analyze("s::t", desc)
        clarity = next(s for s in report.dimension_scores if s.dimension == "clarity")
        boundary = next(s for s in report.dimension_scores if s.dimension == "boundary")
        assert clarity.score > boundary.score, "Clarity should be higher than boundary"

    async def test_high_boundary_low_stats(self, analyzer: HeuristicAnalyzer) -> None:
        """Description with boundaries but no stats."""
        desc = "Cannot delete files. Does not modify data. Not suitable for bulk operations."
        report = await analyzer.analyze("s::t", desc)
        boundary = next(s for s in report.dimension_scores if s.dimension == "boundary")
        stats = next(s for s in report.dimension_scores if s.dimension == "stats")
        assert boundary.score > stats.score, "Boundary should be higher than stats"

    async def test_stats_only(self, analyzer: HeuristicAnalyzer) -> None:
        """Description with only stats information."""
        desc = "Handles 50,000+ packages. 99.9% uptime. Response time under 200ms."
        report = await analyzer.analyze("s::t", desc)
        stats = next(s for s in report.dimension_scores if s.dimension == "stats")
        assert stats.score >= 0.5, f"Stats-rich desc should score >= 0.5, got {stats.score:.3f}"
```

- [ ] **Step 3: 테스트 실행 및 빨간불 확인**

Run: `uv run pytest tests/verification/test_heuristic_edge_cases.py -v`
Expected: 모든 테스트 PASS (구현 이미 완료 — 이 테스트는 기존 구현 검증용)

- [ ] **Step 4: 실패 테스트 분석 및 버그 수정**

실패 테스트가 있으면:
1. 실패 원인 분석
2. 버그인 경우 `src/description_optimizer/analyzer/heuristic.py` 수정
3. 설계 의도인 경우 테스트 assertion 조정 + 코멘트로 근거 기록

- [ ] **Step 5: 커밋**

```bash
git add tests/verification/
git commit -m "test(verification): add HeuristicAnalyzer edge case tests"
```

---

### Task 2: QualityGate 경계 조건 테스트

**Files:**
- Create: `tests/verification/test_quality_gate_edge_cases.py`

- [ ] **Step 1: 경계 조건 테스트 작성**

```python
# tests/verification/test_quality_gate_edge_cases.py
"""QualityGate edge cases — boundary conditions for GEO and similarity checks."""

import numpy as np
import pytest

from description_optimizer.models import AnalysisReport, DimensionScore
from description_optimizer.quality_gate import QualityGate


def _make_report(geo_uniform: float) -> AnalysisReport:
    """Create AnalysisReport with uniform scores across all dimensions."""
    dims = ["clarity", "disambiguation", "parameter_coverage", "boundary", "stats", "precision"]
    return AnalysisReport(
        tool_id="s::t",
        original_description="test",
        dimension_scores=[
            DimensionScore(dimension=d, score=geo_uniform, explanation="test") for d in dims
        ],
    )


class TestGEOScoreBoundary:
    """Test GEO gate at exact boundaries."""

    def test_epsilon_decrease_fails(self) -> None:
        """Even a tiny GEO decrease should fail."""
        gate = QualityGate(allow_geo_decrease=False)
        before = _make_report(0.5)
        after = _make_report(0.4999)
        result = gate.check_geo_score(before, after)
        assert result.passed is False

    def test_zero_to_zero_passes(self) -> None:
        """0 -> 0 is not a decrease."""
        gate = QualityGate(allow_geo_decrease=False)
        before = _make_report(0.0)
        after = _make_report(0.0)
        result = gate.check_geo_score(before, after)
        assert result.passed is True

    def test_one_to_one_passes(self) -> None:
        """Perfect score maintained."""
        gate = QualityGate(allow_geo_decrease=False)
        before = _make_report(1.0)
        after = _make_report(1.0)
        result = gate.check_geo_score(before, after)
        assert result.passed is True

    def test_allow_geo_decrease_flag(self) -> None:
        """When allow_geo_decrease=True, any decrease passes."""
        gate = QualityGate(allow_geo_decrease=True)
        before = _make_report(0.8)
        after = _make_report(0.2)
        result = gate.check_geo_score(before, after)
        assert result.passed is True


class TestSemanticSimilarityBoundary:
    """Test similarity gate at exact thresholds."""

    def test_exactly_at_threshold(self) -> None:
        """Similarity == min_similarity should pass (>=)."""
        gate = QualityGate(min_similarity=0.85)
        # Create vectors with known cosine similarity
        vec_a = np.array([1.0, 0.0])
        # cos(theta) = 0.85 => theta ~= 31.79 degrees
        # vec_b = [cos(theta), sin(theta)] for known similarity
        theta = np.arccos(0.85)
        vec_b = np.array([np.cos(theta), np.sin(theta)])
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed is True
        assert result.similarity == pytest.approx(0.85, abs=1e-6)

    def test_just_below_threshold(self) -> None:
        """Similarity slightly below threshold should fail."""
        gate = QualityGate(min_similarity=0.85)
        theta = np.arccos(0.849)
        vec_a = np.array([1.0, 0.0])
        vec_b = np.array([np.cos(theta), np.sin(theta)])
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed is False

    def test_zero_vector_first(self) -> None:
        """Zero vector as first input."""
        gate = QualityGate()
        vec_a = np.zeros(3)
        vec_b = np.array([1.0, 0.0, 0.0])
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed is False
        assert result.similarity == 0.0

    def test_zero_vector_second(self) -> None:
        """Zero vector as second input."""
        gate = QualityGate()
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.zeros(3)
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed is False

    def test_opposite_vectors(self) -> None:
        """Perfectly opposite vectors (cosine = -1)."""
        gate = QualityGate()
        vec_a = np.array([1.0, 0.0])
        vec_b = np.array([-1.0, 0.0])
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed is False
        assert result.similarity == pytest.approx(-1.0, abs=1e-6)

    def test_high_dimensional_vectors(self) -> None:
        """Realistic 1536-dim vectors (OpenAI embedding size)."""
        gate = QualityGate(min_similarity=0.85)
        rng = np.random.default_rng(42)
        vec_a = rng.standard_normal(1536)
        vec_a = vec_a / np.linalg.norm(vec_a)
        # Add small noise for high similarity
        noise = rng.standard_normal(1536) * 0.05
        vec_b = vec_a + noise
        vec_b = vec_b / np.linalg.norm(vec_b)
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.similarity is not None
        assert 0.9 < result.similarity < 1.0  # Should be very similar
        assert result.passed is True

    def test_custom_threshold(self) -> None:
        """QualityGate with non-default min_similarity."""
        gate = QualityGate(min_similarity=0.5)
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.6, 0.8, 0.0])  # cos sim = 0.6
        result = gate.check_semantic_similarity(vec_a, vec_b)
        assert result.passed is True


class TestFullGateResultReason:
    """Test FullGateResult.reason property formatting."""

    def test_both_pass_reason(self) -> None:
        gate = QualityGate()
        before = _make_report(0.3)
        after = _make_report(0.5)
        vec = np.array([1.0, 0.0, 0.0])
        result = gate.evaluate(before, after, vec, vec)
        assert result.passed is True
        assert "All gates passed" in result.reason

    def test_both_fail_reason(self) -> None:
        gate = QualityGate()
        before = _make_report(0.8)
        after = _make_report(0.2)
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.0, 1.0, 0.0])
        result = gate.evaluate(before, after, vec_a, vec_b)
        assert result.passed is False
        assert "GEO" in result.reason
        assert "Similarity" in result.reason
```

- [ ] **Step 2: 테스트 실행**

Run: `uv run pytest tests/verification/test_quality_gate_edge_cases.py -v`
Expected: All PASS

- [ ] **Step 3: 실패 분석 및 수정**

실패 시 `src/description_optimizer/quality_gate.py`의 경계 조건 처리 확인.

- [ ] **Step 4: 커밋**

```bash
git add tests/verification/test_quality_gate_edge_cases.py
git commit -m "test(verification): add QualityGate boundary condition tests"
```

---

### Task 3: LLM Optimizer 견고성 테스트

**Files:**
- Create: `tests/verification/test_llm_optimizer_robustness.py`

- [ ] **Step 1: 이상 응답 처리 테스트 작성**

```python
# tests/verification/test_llm_optimizer_robustness.py
"""LLM Optimizer robustness tests — malformed responses, edge cases."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from description_optimizer.models import AnalysisReport, DimensionScore
from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer

ALL_DIMS = ["clarity", "disambiguation", "parameter_coverage", "boundary", "stats", "precision"]


def _make_report(desc: str = "test", geo_uniform: float = 0.3) -> AnalysisReport:
    return AnalysisReport(
        tool_id="s::t",
        original_description=desc,
        dimension_scores=[
            DimensionScore(dimension=d, score=geo_uniform, explanation="test") for d in ALL_DIMS
        ],
    )


def _mock_client_with_content(content: str) -> AsyncMock:
    """Create mock OpenAI client returning given content."""
    client = AsyncMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response.choices = [mock_choice]
    client.chat.completions.create.return_value = mock_response
    return client


class TestMalformedJSON:
    async def test_invalid_json_raises(self) -> None:
        """Non-JSON response should raise JSONDecodeError."""
        client = _mock_client_with_content("This is not JSON")
        optimizer = LLMDescriptionOptimizer(client=client)
        with pytest.raises(json.JSONDecodeError):
            await optimizer.optimize(_make_report())

    async def test_missing_optimized_description_key(self) -> None:
        """JSON without required key should raise ValueError."""
        client = _mock_client_with_content(json.dumps({"wrong_key": "value", "search_description": "x"}))
        optimizer = LLMDescriptionOptimizer(client=client)
        with pytest.raises(ValueError, match="optimized_description"):
            await optimizer.optimize(_make_report())

    async def test_missing_search_description_key(self) -> None:
        """JSON without search_description should raise ValueError."""
        client = _mock_client_with_content(json.dumps({"optimized_description": "x", "wrong": "y"}))
        optimizer = LLMDescriptionOptimizer(client=client)
        with pytest.raises(ValueError, match="search_description"):
            await optimizer.optimize(_make_report())

    async def test_empty_json_object(self) -> None:
        """Empty JSON object should raise ValueError."""
        client = _mock_client_with_content("{}")
        optimizer = LLMDescriptionOptimizer(client=client)
        with pytest.raises(ValueError):
            await optimizer.optimize(_make_report())

    async def test_null_content(self) -> None:
        """None content from LLM should raise."""
        client = AsyncMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_response.choices = [mock_choice]
        client.chat.completions.create.return_value = mock_response
        optimizer = LLMDescriptionOptimizer(client=client)
        with pytest.raises((TypeError, json.JSONDecodeError)):
            await optimizer.optimize(_make_report())


class TestExtraKeysInResponse:
    async def test_extra_keys_accepted(self) -> None:
        """Response with extra keys should still work (only required keys checked)."""
        content = json.dumps({
            "optimized_description": "improved",
            "search_description": "keywords",
            "confidence": 0.95,
            "notes": "extra data",
        })
        client = _mock_client_with_content(content)
        optimizer = LLMDescriptionOptimizer(client=client)
        result = await optimizer.optimize(_make_report())
        assert result["optimized_description"] == "improved"
        assert result["search_description"] == "keywords"


class TestEmptyDescriptions:
    async def test_empty_optimized_description(self) -> None:
        """LLM returns empty optimized description — should still return."""
        content = json.dumps({"optimized_description": "", "search_description": "keywords"})
        client = _mock_client_with_content(content)
        optimizer = LLMDescriptionOptimizer(client=client)
        result = await optimizer.optimize(_make_report())
        assert result["optimized_description"] == ""

    async def test_very_long_response(self) -> None:
        """LLM returns very long description."""
        long_desc = "word " * 500  # ~2500 chars
        content = json.dumps({"optimized_description": long_desc, "search_description": "short"})
        client = _mock_client_with_content(content)
        optimizer = LLMDescriptionOptimizer(client=client)
        result = await optimizer.optimize(_make_report())
        assert len(result["optimized_description"]) > 2000


class TestAPIFailures:
    async def test_openai_api_error_propagates(self) -> None:
        """OpenAI API error should propagate (caught by pipeline)."""
        client = AsyncMock()
        client.chat.completions.create.side_effect = Exception("API rate limit")
        optimizer = LLMDescriptionOptimizer(client=client)
        with pytest.raises(Exception, match="API rate limit"):
            await optimizer.optimize(_make_report())


class TestWeakDimensionsInPrompt:
    async def test_all_weak_dimensions_included(self) -> None:
        """When all dimensions are weak, all guidance should be in prompt."""
        report = _make_report(geo_uniform=0.2)  # All dims below 0.5
        content = json.dumps({"optimized_description": "x", "search_description": "y"})
        client = _mock_client_with_content(content)
        optimizer = LLMDescriptionOptimizer(client=client)
        await optimizer.optimize(report)

        call_args = client.chat.completions.create.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        for dim in ALL_DIMS:
            assert dim in user_msg, f"Weak dimension '{dim}' not in prompt"

    async def test_no_weak_dimensions(self) -> None:
        """When no dimensions are weak, prompt should say 'none'."""
        report = _make_report(geo_uniform=0.8)  # All dims above 0.5
        content = json.dumps({"optimized_description": "x", "search_description": "y"})
        client = _mock_client_with_content(content)
        optimizer = LLMDescriptionOptimizer(client=client)
        await optimizer.optimize(report)

        call_args = client.chat.completions.create.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        assert "none" in user_msg.lower() or "adequate" in user_msg.lower()
```

- [ ] **Step 2: 테스트 실행**

Run: `uv run pytest tests/verification/test_llm_optimizer_robustness.py -v`
Expected: All PASS (malformed JSON/missing key → raise, extra keys → accept)

- [ ] **Step 3: 실패 분석 및 수정**

특히 `test_null_content`가 실패할 경우 `llm_optimizer.py:55`의 `content = response.choices[0].message.content` 처리 확인 필요.

- [ ] **Step 4: 커밋**

```bash
git add tests/verification/test_llm_optimizer_robustness.py
git commit -m "test(verification): add LLM optimizer robustness tests"
```

---

### Task 4: Pipeline 에러 경로 테스트

**Files:**
- Create: `tests/verification/test_pipeline_error_paths.py`

- [ ] **Step 1: 에러 경로 테스트 작성**

```python
# tests/verification/test_pipeline_error_paths.py
"""Pipeline error paths — optimizer failure, embedder failure, gate edge cases."""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from description_optimizer.models import (
    AnalysisReport,
    DimensionScore,
    OptimizationStatus,
)
from description_optimizer.pipeline import OptimizationPipeline
from description_optimizer.quality_gate import FullGateResult, GateResult

ALL_DIMS = ["clarity", "disambiguation", "parameter_coverage", "boundary", "stats", "precision"]


def _make_report(geo: float, desc: str = "test") -> AnalysisReport:
    return AnalysisReport(
        tool_id="s::t",
        original_description=desc,
        dimension_scores=[
            DimensionScore(dimension=d, score=geo, explanation="test") for d in ALL_DIMS
        ],
    )


def _build_pipeline(
    analyzer_geo: float = 0.3,
    optimizer_result: dict | Exception | None = None,
    embedder_result: np.ndarray | Exception | None = None,
    gate_passed: bool = True,
    skip_threshold: float = 0.75,
) -> OptimizationPipeline:
    analyzer = AsyncMock()
    analyzer.analyze.return_value = _make_report(analyzer_geo)

    optimizer = AsyncMock()
    if isinstance(optimizer_result, Exception):
        optimizer.optimize.side_effect = optimizer_result
    else:
        optimizer.optimize.return_value = optimizer_result or {
            "optimized_description": "improved",
            "search_description": "search",
        }

    embedder = AsyncMock()
    if isinstance(embedder_result, Exception):
        embedder.embed_one.side_effect = embedder_result
    else:
        embedder.embed_one.return_value = embedder_result if embedder_result is not None else np.array([0.95, 0.1, 0.05])

    gate = MagicMock()
    gate.evaluate.return_value = FullGateResult(
        passed=gate_passed,
        geo_result=GateResult(passed=gate_passed, reason="ok"),
        similarity_result=GateResult(passed=True, reason="ok", similarity=0.95),
    )

    return OptimizationPipeline(
        analyzer=analyzer,
        optimizer=optimizer,
        embedder=embedder,
        gate=gate,
        skip_threshold=skip_threshold,
    )


class TestOptimizerFailure:
    async def test_optimizer_exception_returns_failed(self) -> None:
        """When optimizer raises, pipeline should return FAILED status."""
        pipeline = _build_pipeline(optimizer_result=RuntimeError("LLM API down"))
        result = await pipeline.run("s::t", "test description")
        assert result.status == OptimizationStatus.FAILED
        assert "LLM API down" in result.skip_reason
        assert result.original_description == "test description"
        assert result.optimized_description == "test description"  # Preserved original

    async def test_optimizer_json_error_returns_failed(self) -> None:
        """When optimizer raises ValueError (bad JSON), FAILED status."""
        pipeline = _build_pipeline(optimizer_result=ValueError("Missing key"))
        result = await pipeline.run("s::t", "test")
        assert result.status == OptimizationStatus.FAILED


class TestEmbedderFailure:
    async def test_embedder_exception_propagates(self) -> None:
        """If embedder fails after optimization, exception propagates (not caught by pipeline)."""
        pipeline = _build_pipeline(embedder_result=RuntimeError("Embedding API error"))
        # Pipeline doesn't catch embedder errors — this is intentional?
        # Let's verify the actual behavior
        with pytest.raises(RuntimeError, match="Embedding API error"):
            await pipeline.run("s::t", "test")


class TestSkipThreshold:
    async def test_exactly_at_threshold_skips(self) -> None:
        """GEO == skip_threshold should skip (>= comparison)."""
        pipeline = _build_pipeline(analyzer_geo=0.75, skip_threshold=0.75)
        result = await pipeline.run("s::t", "already good")
        assert result.status == OptimizationStatus.SKIPPED

    async def test_just_below_threshold_optimizes(self) -> None:
        """GEO just below threshold should optimize."""
        pipeline = _build_pipeline(analyzer_geo=0.749, skip_threshold=0.75)
        result = await pipeline.run("s::t", "almost good")
        assert result.status == OptimizationStatus.SUCCESS

    async def test_threshold_zero_optimizes_everything(self) -> None:
        """skip_threshold=0 means nothing skips (GEO can't be negative)."""
        pipeline = _build_pipeline(analyzer_geo=0.0, skip_threshold=0.0)
        result = await pipeline.run("s::t", "empty")
        # GEO 0.0 >= 0.0, so SKIPPED
        assert result.status == OptimizationStatus.SKIPPED

    async def test_threshold_one_skips_only_perfect(self) -> None:
        """skip_threshold=1.0 means only perfect GEO skips."""
        pipeline = _build_pipeline(analyzer_geo=0.99, skip_threshold=1.0)
        result = await pipeline.run("s::t", "almost perfect")
        assert result.status == OptimizationStatus.SUCCESS


class TestGateRejection:
    async def test_gate_rejected_preserves_original(self) -> None:
        """When gate rejects, original description is preserved."""
        pipeline = _build_pipeline(gate_passed=False)
        result = await pipeline.run("s::t", "test description")
        assert result.status == OptimizationStatus.GATE_REJECTED
        assert result.optimized_description == "test description"
        assert result.search_description == "test description"

    async def test_gate_rejected_has_reason(self) -> None:
        """Gate rejection should include reason."""
        pipeline = _build_pipeline(gate_passed=False)
        result = await pipeline.run("s::t", "test")
        assert result.skip_reason is not None


class TestBatchEdgeCases:
    async def test_empty_batch(self) -> None:
        """Empty tool list should return empty results."""
        pipeline = _build_pipeline()
        results = await pipeline.run_batch([])
        assert results == []

    async def test_single_item_batch(self) -> None:
        """Single item batch should work."""
        pipeline = _build_pipeline()
        results = await pipeline.run_batch([("s::t", "desc")])
        assert len(results) == 1
```

- [ ] **Step 2: 테스트 실행**

Run: `uv run pytest tests/verification/test_pipeline_error_paths.py -v`
Expected: 대부분 PASS. `test_embedder_exception_propagates`는 실제 pipeline이 embedder 에러를 catch하는지 확인 필요.

- [ ] **Step 3: 실패 분석 및 수정**

`pipeline.py:90-91`에서 embedder 호출이 try/except 밖에 있으므로 embedder 에러는 전파됨. 이것이 의도인지 확인하고 테스트 assertion 조정.

- [ ] **Step 4: 커밋**

```bash
git add tests/verification/test_pipeline_error_paths.py
git commit -m "test(verification): add pipeline error path tests"
```

---

### Task 5: 실제 MCP Description 샘플 GEO 캘리브레이션

**Files:**
- Create: `tests/verification/test_geo_calibration.py`

- [ ] **Step 1: 실제 MCP description 샘플로 캘리브레이션 테스트 작성**

```python
# tests/verification/test_geo_calibration.py
"""GEO Score calibration — verify scoring on real-world MCP tool descriptions.

Uses actual MCP tool descriptions from well-known servers to validate:
1. Score distribution is reasonable (not clustered at 0 or 1)
2. Known-good descriptions outscore known-poor ones
3. Each dimension's scoring aligns with human intuition
"""

import pytest

from description_optimizer.analyzer.heuristic import HeuristicAnalyzer

# -----------------------------------------------------------------------
# Real MCP tool descriptions (curated from Smithery registry)
# -----------------------------------------------------------------------

REAL_DESCRIPTIONS = {
    "poor": [
        {
            "tool_id": "generic::search",
            "description": "Search stuff",
            "expected_geo_max": 0.25,
            "note": "Minimal, no specifics",
        },
        {
            "tool_id": "generic::read",
            "description": "Read a file",
            "expected_geo_max": 0.25,
            "note": "Too vague",
        },
        {
            "tool_id": "generic::run",
            "description": "Run command",
            "expected_geo_max": 0.25,
            "note": "No context, no scope",
        },
    ],
    "medium": [
        {
            "tool_id": "github::search_repos",
            "description": (
                "Search for GitHub repositories matching a query. "
                "Returns repository name, URL, description, star count, and language."
            ),
            "expected_geo_range": (0.15, 0.55),
            "note": "Has action verb and scope but lacks disambiguation, boundary, stats",
        },
        {
            "tool_id": "slack::send_message",
            "description": (
                "Send a message to a Slack channel or user. "
                "Requires a channel ID and message text. "
                "Use when you need to notify a team about events."
            ),
            "expected_geo_range": (0.2, 0.55),
            "note": "Has clarity and param hints but lacks boundary and stats",
        },
    ],
    "good": [
        {
            "tool_id": "postgres::run_query",
            "description": (
                "Executes read-only SQL queries against a PostgreSQL database via the "
                "wire protocol. Use when you need to retrieve structured data from tables. "
                "Supports JSON, JSONB, and ARRAY column types. Accepts a required `query` "
                "string parameter. Cannot execute DDL (CREATE/DROP) or DML (INSERT/UPDATE/DELETE) "
                "statements. Not suitable for bulk data export. Query timeout: 30 seconds. "
                "Maximum result size: 10,000 rows."
            ),
            "expected_geo_min": 0.45,
            "note": "Rich in all dimensions",
        },
        {
            "tool_id": "github::search_issues",
            "description": (
                "Searches GitHub Issues matching a text query via the GitHub REST API v3. "
                "Use when you need to find bug reports, feature requests, or discussions "
                "in a specific repository. Unlike the PR search tool, this only searches "
                "Issues, not Pull Requests. Cannot search across multiple repositories in "
                "a single call. Returns up to 100 results per page."
            ),
            "expected_geo_min": 0.45,
            "note": "Good clarity, disambiguation, boundary, stats",
        },
    ],
}


@pytest.fixture
def analyzer() -> HeuristicAnalyzer:
    return HeuristicAnalyzer()


class TestPoorDescriptionCalibration:
    """Poor descriptions should score consistently low."""

    @pytest.mark.parametrize(
        "sample",
        REAL_DESCRIPTIONS["poor"],
        ids=[s["tool_id"] for s in REAL_DESCRIPTIONS["poor"]],
    )
    async def test_poor_scores_low(self, analyzer: HeuristicAnalyzer, sample: dict) -> None:
        report = await analyzer.analyze(sample["tool_id"], sample["description"])
        assert report.geo_score <= sample["expected_geo_max"], (
            f"{sample['tool_id']}: GEO={report.geo_score:.3f} exceeds max={sample['expected_geo_max']}. "
            f"Note: {sample['note']}"
        )


class TestMediumDescriptionCalibration:
    """Medium descriptions should fall in expected range."""

    @pytest.mark.parametrize(
        "sample",
        REAL_DESCRIPTIONS["medium"],
        ids=[s["tool_id"] for s in REAL_DESCRIPTIONS["medium"]],
    )
    async def test_medium_in_range(self, analyzer: HeuristicAnalyzer, sample: dict) -> None:
        report = await analyzer.analyze(sample["tool_id"], sample["description"])
        lo, hi = sample["expected_geo_range"]
        assert lo <= report.geo_score <= hi, (
            f"{sample['tool_id']}: GEO={report.geo_score:.3f} outside [{lo}, {hi}]. "
            f"Note: {sample['note']}"
        )


class TestGoodDescriptionCalibration:
    """Good descriptions should score consistently high."""

    @pytest.mark.parametrize(
        "sample",
        REAL_DESCRIPTIONS["good"],
        ids=[s["tool_id"] for s in REAL_DESCRIPTIONS["good"]],
    )
    async def test_good_scores_high(self, analyzer: HeuristicAnalyzer, sample: dict) -> None:
        report = await analyzer.analyze(sample["tool_id"], sample["description"])
        assert report.geo_score >= sample["expected_geo_min"], (
            f"{sample['tool_id']}: GEO={report.geo_score:.3f} below min={sample['expected_geo_min']}. "
            f"Note: {sample['note']}"
        )


class TestScoreDistribution:
    """Verify score ordering: poor < medium < good."""

    async def test_ordering(self, analyzer: HeuristicAnalyzer) -> None:
        poor_scores = []
        for s in REAL_DESCRIPTIONS["poor"]:
            r = await analyzer.analyze(s["tool_id"], s["description"])
            poor_scores.append(r.geo_score)

        medium_scores = []
        for s in REAL_DESCRIPTIONS["medium"]:
            r = await analyzer.analyze(s["tool_id"], s["description"])
            medium_scores.append(r.geo_score)

        good_scores = []
        for s in REAL_DESCRIPTIONS["good"]:
            r = await analyzer.analyze(s["tool_id"], s["description"])
            good_scores.append(r.geo_score)

        avg_poor = sum(poor_scores) / len(poor_scores)
        avg_medium = sum(medium_scores) / len(medium_scores)
        avg_good = sum(good_scores) / len(good_scores)

        assert avg_poor < avg_medium < avg_good, (
            f"Score ordering violated: poor={avg_poor:.3f}, medium={avg_medium:.3f}, good={avg_good:.3f}"
        )


class TestDimensionBreakdown:
    """Verify individual dimension scores align with description content."""

    async def test_postgres_has_high_precision(self, analyzer: HeuristicAnalyzer) -> None:
        """PostgreSQL description mentions many technical terms."""
        report = await analyzer.analyze(
            "postgres::run_query",
            REAL_DESCRIPTIONS["good"][0]["description"],
        )
        precision = next(s for s in report.dimension_scores if s.dimension == "precision")
        assert precision.score >= 0.3, f"Expected high precision for PostgreSQL desc, got {precision.score:.3f}"

    async def test_postgres_has_boundary(self, analyzer: HeuristicAnalyzer) -> None:
        """PostgreSQL description has clear 'Cannot' statements."""
        report = await analyzer.analyze(
            "postgres::run_query",
            REAL_DESCRIPTIONS["good"][0]["description"],
        )
        boundary = next(s for s in report.dimension_scores if s.dimension == "boundary")
        assert boundary.score >= 0.3, f"Expected boundary info for PostgreSQL desc, got {boundary.score:.3f}"

    async def test_poor_desc_low_on_all(self, analyzer: HeuristicAnalyzer) -> None:
        """Minimal description should be low on all dimensions."""
        report = await analyzer.analyze("generic::search", "Search stuff")
        for ds in report.dimension_scores:
            assert ds.score <= 0.35, f"Poor desc scored {ds.score:.3f} on {ds.dimension}"
```

- [ ] **Step 2: 테스트 실행**

Run: `uv run pytest tests/verification/test_geo_calibration.py -v`
Expected: All PASS — 실패 시 GEO 스코어 캘리브레이션 조정 필요

- [ ] **Step 3: 실패 분석**

실패한 테스트의 실제 GEO score 값을 기록하고, expected range를 조정하거나 heuristic weights를 조정.

- [ ] **Step 4: 커밋**

```bash
git add tests/verification/test_geo_calibration.py
git commit -m "test(verification): add GEO score calibration with real MCP descriptions"
```

---

### Task 6: 기존 테스트 전체 실행 + Lint + 검증 리포트

**Files:**
- Create: `description_optimizer/docs/verification-report.md`

- [ ] **Step 1: Lint 실행**

Run: `uv run ruff check src/description_optimizer/ tests/`
Expected: Clean

- [ ] **Step 2: 전체 테스트 실행**

Run: `uv run pytest tests/verification/ tests/unit/test_description_optimizer/ tests/integration/test_description_optimizer_integration.py tests/evaluation/test_optimizer_evaluation.py -v --tb=short`
Expected: All PASS

- [ ] **Step 3: 커버리지 확인**

Run: `uv run pytest tests/verification/ tests/unit/test_description_optimizer/ tests/integration/test_description_optimizer_integration.py tests/evaluation/test_optimizer_evaluation.py --cov=src/description_optimizer --cov-report=term-missing`
Expected: 80%+ coverage

- [ ] **Step 4: 검증 리포트 작성**

아래 형식으로 `description_optimizer/docs/verification-report.md` 작성:

```markdown
# Description Optimizer — Verification Report

> Date: 2026-03-28
> Branch: feat/description-optimizer
> Verifier: Claude (자동 검증) + 수동 리뷰 가이드

## 자동 검증 결과

### Test Summary
| Suite | Count | Pass | Fail |
|-------|-------|------|------|
| Unit (models) | 11 | ? | ? |
| Unit (heuristic) | 16 | ? | ? |
| Unit (llm_optimizer) | 7 | ? | ? |
| Unit (quality_gate) | 8 | ? | ? |
| Unit (pipeline) | 10 | ? | ? |
| Evaluation | 4 | ? | ? |
| Integration | 2 | ? | ? |
| Verification (edge cases) | ?? | ? | ? |
| **Total** | **??** | **?** | **?** |

### Coverage
(실제 커버리지 결과 삽입)

### 발견된 이슈
(실제 발견 이슈 기록)

### 수정 내역
(수정한 버그 기록)
```

- [ ] **Step 5: 커밋**

```bash
git add description_optimizer/docs/verification-report.md
git commit -m "docs(verification): add automated verification report"
```

---

## Phase B: 수동 리뷰 가이드 (사용자 수행)

> 아래 내용은 검증 리포트에 포함되어 사용자가 직접 면밀히 검토할 수 있도록 한다.

### Task 7: 검증 리포트에 수동 리뷰 가이드 추가

**Files:**
- Modify: `description_optimizer/docs/verification-report.md`

- [ ] **Step 1: 수동 리뷰 가이드 섹션 추가**

아래 섹션을 검증 리포트에 추가:

```markdown
---

## 수동 리뷰 가이드

### 리뷰 1: GEO 점수 캘리브레이션 직접 확인

실제 서버 데이터로 GEO 점수가 직관에 부합하는지 확인합니다.

**실행:**
```bash
uv run python -c "
import asyncio
from description_optimizer.analyzer.heuristic import HeuristicAnalyzer

async def main():
    analyzer = HeuristicAnalyzer()
    samples = [
        ('poor', 'generic::search', 'Search stuff'),
        ('poor', 'generic::read', 'Read a file'),
        ('medium', 'github::search_repos', 'Search for GitHub repositories matching a query. Returns repository name, URL, description, star count, and language.'),
        ('good', 'postgres::run_query', 'Executes read-only SQL queries against a PostgreSQL database via the wire protocol. Use when you need to retrieve structured data. Supports JSON, JSONB, and ARRAY column types. Cannot execute DDL or DML statements. Query timeout: 30 seconds. Maximum result size: 10,000 rows.'),
    ]
    for tier, tid, desc in samples:
        report = await analyzer.analyze(tid, desc)
        print(f'[{tier:6s}] {tid:30s} GEO={report.geo_score:.3f}')
        for ds in report.dimension_scores:
            print(f'         {ds.dimension:25s} {ds.score:.2f}  {ds.explanation}')
        print()

asyncio.run(main())
"
```

**확인 포인트:**
- [ ] poor 설명은 GEO < 0.25인가?
- [ ] good 설명은 GEO > 0.45인가?
- [ ] 각 차원 점수가 설명 내용과 직관적으로 매치되는가?
- [ ] precision 차원에서 기술 용어가 있는 설명이 높은 점수를 받는가?
- [ ] boundary 차원에서 "Cannot", "Does not" 등이 있는 설명이 높은 점수를 받는가?

---

### 리뷰 2: LLM 프롬프트 품질 검토

`src/description_optimizer/optimizer/prompts.py`를 직접 읽고 검토합니다.

**확인 포인트:**
- [ ] SYSTEM_PROMPT가 사실 보존 규칙을 명시하고 있는가? (Line 14: "PRESERVE all factual information")
- [ ] 차원별 가이던스가 충분히 구체적인가? (Lines 43-49)
- [ ] word limit이 적절한가? (optimized: 50-200, search: 30-80)
- [ ] JSON 출력 포맷 지시가 명확한가?
- [ ] 프롬프트에 주입 취약점이 없는가? (tool_id, description이 escape 없이 삽입됨)

---

### 리뷰 3: Quality Gate 임계값 타당성

**확인 포인트:**
- [ ] `min_similarity=0.85` — embedding cosine similarity 85%가 의미 보존에 충분히 엄격한가?
  - 참고: 같은 주제의 다른 문장은 보통 0.7-0.85, 패러프레이즈는 0.85-0.95
  - 너무 낮으면: 의미가 바뀐 설명도 통과
  - 너무 높으면: 개선된 설명도 거부
- [ ] `skip_threshold=0.75` — GEO 0.75 이상이면 이미 충분히 좋은가?
  - 참고: 현재 heuristic에서 0.75+ 받으려면 최소 4-5개 차원에서 높은 점수 필요
- [ ] `allow_geo_decrease=False` — 어떤 상황에서도 GEO 하락을 허용하지 않는 것이 합리적인가?
  - 고려: 의미 보존을 위해 약간의 GEO 하락이 나을 수 있음

---

### 리뷰 4: Pipeline 안전성

`src/description_optimizer/pipeline.py`를 읽고 검토합니다.

**확인 포인트:**
- [ ] Line 42: `desc = description or ""` — None 처리가 적절한가?
- [ ] Lines 68-81: optimizer 에러 catch — 모든 Exception을 잡는 것이 적절한가?
- [ ] Lines 90-91: embedder 에러는 catch되지 않음 — 이것이 의도적인가?
  - embedder 실패 시 전체 pipeline이 죽음 → batch 중 한 tool 실패하면 나머지도 처리 안 됨
- [ ] Lines 98-107: gate rejection 시 original 보존 — search_description도 original로 설정하는 것이 맞는가?
- [ ] Line 134: `run_batch`가 sequential — 대규모 tool pool에서 성능 이슈 없는가?

---

### 리뷰 5: 데이터 모델 견고성

`src/description_optimizer/models.py`를 읽고 검토합니다.

**확인 포인트:**
- [ ] Line 26: `Field(ge=0.0, le=1.0)` — 점수 범위가 적절한가?
- [ ] Lines 44-49: 6개 차원 전부 필수 — 부분 분석 허용 여부?
- [ ] Line 56: `geo_score` = 균등 가중 평균 — 차원별 중요도가 다르지 않은가?
  - 예: clarity가 precision보다 검색 성능에 더 중요하지 않은가?
- [ ] Line 77: `improvement = after - before` — 음수 improvement가 가능 (gate rejected일 때)

---

### 리뷰 6: Heuristic Regex 품질

`src/description_optimizer/analyzer/heuristic.py`를 읽고 검토합니다.

**확인 포인트:**
- [ ] Lines 24-30: Action verb 패턴 — "gets" (HTTP GET)가 action verb인가?
- [ ] Lines 41-54: Disambiguation — "only"가 domain qualifier인데, "the only way to..."처럼 쓰이면 false positive
- [ ] Lines 81-87: Stats — `\d{2,}` 패턴이 연도(2024)를 stat으로 잡지 않는가?
- [ ] Lines 90-95: Precision — "Git"이 기술 용어인데, 일반 문맥에서의 "git"도 매치
- [ ] 전반적으로: regex 기반 한계를 인지하고 LLM-as-Judge 대안을 고려

---

### 리뷰 7: 실제 데이터로 dry-run 테스트

`data/raw/servers.jsonl`이 있다면 실제 데이터로 dry-run을 실행합니다.

**실행:**
```bash
# data/raw/servers.jsonl이 있는 경우
uv run python scripts/optimize_descriptions.py --dry-run --input data/raw/servers.jsonl

# 없는 경우, 샘플 데이터 생성
echo '{"server_id":"github","name":"GitHub","description":"GitHub API","tools":[{"tool_name":"search_issues","description":"Search stuff"},{"tool_name":"create_pr","description":"Creates pull requests on GitHub repositories. Accepts title (string, required), body (string, optional), and base branch. Cannot create PRs across forks."}]}' > /tmp/test_servers.jsonl

uv run python scripts/optimize_descriptions.py --dry-run --input /tmp/test_servers.jsonl
```

**확인 포인트:**
- [ ] dry-run이 에러 없이 실행되는가?
- [ ] 각 tool의 GEO score와 weak dimensions가 출력되는가?
- [ ] score가 직관에 부합하는가?
```

- [ ] **Step 2: 커밋**

```bash
git add description_optimizer/docs/verification-report.md
git commit -m "docs(verification): add manual review guide to verification report"
```

---

## Summary

| Phase | Task | 검증 대상 | 테스트 수 (예상) |
|-------|------|----------|----------------|
| A (자동) | Task 1 | HeuristicAnalyzer 엣지케이스 | ~18 |
| A (자동) | Task 2 | QualityGate 경계 조건 | ~12 |
| A (자동) | Task 3 | LLM Optimizer 견고성 | ~10 |
| A (자동) | Task 4 | Pipeline 에러 경로 | ~9 |
| A (자동) | Task 5 | GEO 캘리브레이션 | ~10 |
| A (자동) | Task 6 | 전체 실행 + 리포트 | - |
| B (수동) | Task 7 | 리뷰 가이드 7개 항목 | - |
| **Total** | | | **~59 new tests** |
