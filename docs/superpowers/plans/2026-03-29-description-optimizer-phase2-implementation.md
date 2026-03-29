# Description Optimizer Phase 2: 리서치 기반 개선 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GEO Scorer의 Goodhart's Law 문제를 해결하기 위해 boundary 차원을 제거하고, fluency 차원을 추가하며, RAGAS Faithfulness 게이트를 구현하고, doc2query 쿼리 인식 최적화와 P@1 A/B 검증을 구축한다.

**Architecture:** boundary 차원(GEO 미지지, 95% 환각 원인)을 제거하고 fluency(GEO +28%, LLM 선호 확인)로 교체. RAGAS faithfulness 패턴(주장 추출 → 이진 검증)으로 환각 게이트를 강화. doc2query 스타일로 예상 쿼리를 생성하여 최적화 프롬프트에 사용. P@1 A/B 스크립트로 end-to-end 검증.

**Tech Stack:** Python 3.12, OpenAI AsyncOpenAI (GPT-4o-mini 최적화, 별도 모델 평가), numpy, pytest, ruff

---

## File Structure

### Modified Files
- `src/description_optimizer/models.py` — GEO_DIMENSIONS에서 "boundary" 제거, "fluency" 추가
- `src/description_optimizer/analyzer/heuristic.py` — _score_boundary 제거, _score_fluency 추가
- `src/description_optimizer/optimizer/prompts.py` — boundary 가이드라인 제거, fluency 가이드라인 추가, build_query_aware_prompt 추가
- `src/description_optimizer/quality_gate.py` — RAGAS faithfulness 게이트 추가
- Tests: 14개 파일에서 boundary→fluency 업데이트

### New Files
- `scripts/run_retrieval_ab_eval.py` — P@1 A/B 평가 스크립트

---

### Task 1: boundary 차원 제거 및 fluency 차원 추가 — models.py

**Files:**
- Modify: `src/description_optimizer/models.py:8-10,23-24`

- [ ] **Step 1: models.py에서 GEO_DIMENSIONS 업데이트**

`src/description_optimizer/models.py`에서 boundary를 fluency로 교체:

```python
# Line 8-10: 변경 전
GEO_DIMENSIONS = frozenset(
    {"clarity", "disambiguation", "parameter_coverage", "boundary", "stats", "precision"}
)

# 변경 후
GEO_DIMENSIONS = frozenset(
    {"clarity", "disambiguation", "parameter_coverage", "fluency", "stats", "precision"}
)
```

```python
# Line 23-25: DimensionScore의 Literal 타입도 변경
# 변경 전
class DimensionScore(BaseModel):
    dimension: Literal[
        "clarity", "disambiguation", "parameter_coverage", "boundary", "stats", "precision"
    ]

# 변경 후
class DimensionScore(BaseModel):
    dimension: Literal[
        "clarity", "disambiguation", "parameter_coverage", "fluency", "stats", "precision"
    ]
```

- [ ] **Step 2: 테스트 실행하여 영향 범위 확인**

Run: `uv run pytest tests/unit/test_description_optimizer/test_models.py -v 2>&1 | head -50`
Expected: 다수의 FAIL (boundary를 참조하는 테스트들)

- [ ] **Step 3: test_models.py 업데이트**

`tests/unit/test_description_optimizer/test_models.py`에서 모든 "boundary" → "fluency" 교체:

```python
# test_valid_dimensions: "boundary" → "fluency"
# test_geo_score_computation: DimensionScore(dimension="boundary", ...) → DimensionScore(dimension="fluency", ...)
# test_weak_dimensions: 동일 변경, assert set(weak) == {"disambiguation", "fluency"} 등
```

모든 test_models.py 내 `"boundary"` 문자열을 `"fluency"`로 교체.

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_description_optimizer/test_models.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/description_optimizer/models.py tests/unit/test_description_optimizer/test_models.py
git commit -m "refactor(desc-optimizer): boundary 차원을 fluency로 교체 — models"
```

---

### Task 2: HeuristicAnalyzer — _score_boundary 제거, _score_fluency 추가

**Files:**
- Modify: `src/description_optimizer/analyzer/heuristic.py:70-78,111,228-249`
- Modify: `tests/unit/test_description_optimizer/test_heuristic_analyzer.py`

- [ ] **Step 1: test_heuristic_analyzer.py에서 TestBoundaryScoring → TestFluencyScoring 교체**

```python
# TestBoundaryScoring 클래스를 삭제하고 TestFluencyScoring으로 교체:

class TestFluencyScoring:
    async def test_high_fluency(self):
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

    async def test_low_fluency(self):
        """Fragmented, poorly structured text scores low."""
        desc = "get data. data. get. query. results."
        analyzer = HeuristicAnalyzer()
        report = await analyzer.analyze("test::tool", desc)
        fluency = next(s for s in report.dimension_scores if s.dimension == "fluency")
        assert fluency.score <= 0.3
```

또한 `TestFullAnalysis` 에서:
- `test_returns_all_six_dimensions`의 GEO_DIMENSIONS 검증은 자동으로 새 frozenset과 일치하게 됨 (fluency 포함)

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `uv run pytest tests/unit/test_description_optimizer/test_heuristic_analyzer.py -v`
Expected: FAIL — _score_fluency 메서드 없음, _score_boundary 여전히 호출

- [ ] **Step 3: heuristic.py에서 boundary 제거, fluency 추가**

`src/description_optimizer/analyzer/heuristic.py`에서:

1. boundary 관련 regex 패턴 제거 (lines 70-78: `_NEGATIVE_BOUNDARY`, `_LIMITATION_KEYWORDS`):

```python
# 삭제할 코드 (lines 69-78):
    # --- Boundary patterns ---
    _NEGATIVE_BOUNDARY: re.Pattern[str] = re.compile(...)
    _LIMITATION_KEYWORDS: re.Pattern[str] = re.compile(...)
```

2. fluency 관련 패턴 추가:

```python
    # --- Fluency patterns ---
    _SENTENCE_ENDER: re.Pattern[str] = re.compile(r"[.!?]\s+", re.UNICODE)
    _CONNECTOR_WORDS: re.Pattern[str] = re.compile(
        r"\b(and|or|but|because|since|when|while|however|therefore|also|"
        r"additionally|furthermore|moreover|then|thus|so|if|by|with|for|"
        r"in order to|such as|including)\b",
        re.IGNORECASE,
    )
```

3. analyze() 메서드에서 `_score_boundary` → `_score_fluency` 교체 (line 111):

```python
        dimension_scores = [
            self._score_clarity(safe_desc),
            self._score_disambiguation(safe_desc),
            self._score_parameter_coverage(safe_desc),
            self._score_fluency(safe_desc),      # was: self._score_boundary(safe_desc)
            self._score_stats(safe_desc),
            self._score_precision(safe_desc),
        ]
```

4. `_score_boundary` 메서드 전체 삭제 (lines 228-249) 및 `_score_fluency` 추가:

```python
    def _score_fluency(self, desc: str) -> DimensionScore:
        """Score description fluency: sentence structure, connectors, readability."""
        score = 0.0
        reasons: list[str] = []

        if not desc.strip():
            return DimensionScore(
                dimension="fluency", score=0.0, explanation="Fluency score 0.00: empty"
            )

        # Sentence count and average length (well-formed descriptions have 2-5 sentences)
        sentences = [s.strip() for s in self._SENTENCE_ENDER.split(desc) if s.strip()]
        if not sentences:
            sentences = [desc]
        n_sentences = len(sentences)

        if n_sentences >= 2:
            score += 0.3
            reasons.append(f"sentences={n_sentences}")
        elif n_sentences == 1 and len(desc) >= 60:
            score += 0.15
            reasons.append("single_long_sentence")

        # Average sentence length (ideal: 10-30 words per sentence)
        avg_words = sum(len(s.split()) for s in sentences) / max(n_sentences, 1)
        if 10 <= avg_words <= 30:
            score += 0.25
            reasons.append(f"avg_words={avg_words:.0f}")
        elif 5 <= avg_words < 10 or 30 < avg_words <= 50:
            score += 0.1
            reasons.append(f"avg_words={avg_words:.0f}_suboptimal")

        # Connector/transition words (indicate structured prose)
        connector_matches = self._CONNECTOR_WORDS.findall(desc)
        connector_contribution = _clamp(len(connector_matches) * 0.1, hi=0.25)
        score += connector_contribution
        if connector_matches:
            reasons.append(f"connectors={len(connector_matches)}")

        # Word diversity (ratio of unique words to total — penalize repetitive text)
        words = desc.lower().split()
        if len(words) >= 5:
            diversity = len(set(words)) / len(words)
            if diversity >= 0.6:
                score += 0.2
                reasons.append(f"diversity={diversity:.2f}")
            elif diversity >= 0.4:
                score += 0.1
                reasons.append(f"diversity={diversity:.2f}_low")

        final = _clamp(score)
        return DimensionScore(
            dimension="fluency",
            score=final,
            explanation=f"Fluency score {final:.2f}: {', '.join(reasons) or 'no signals'}",
        )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_description_optimizer/test_heuristic_analyzer.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/description_optimizer/analyzer/heuristic.py tests/unit/test_description_optimizer/test_heuristic_analyzer.py
git commit -m "refactor(desc-optimizer): boundary 제거, fluency 휴리스틱 추가 — HeuristicAnalyzer"
```

---

### Task 3: 프롬프트에서 boundary 제거, fluency 가이드라인 추가

**Files:**
- Modify: `src/description_optimizer/optimizer/prompts.py:46-53,183-232`
- Modify: `tests/unit/test_description_optimizer/test_grounded_prompts.py`

- [ ] **Step 1: test_grounded_prompts.py에서 boundary 참조 교체**

`tests/unit/test_description_optimizer/test_grounded_prompts.py`에서 모든 `"boundary"` → `"fluency"` 교체.

- [ ] **Step 2: prompts.py에서 boundary 가이드라인을 fluency로 교체**

`src/description_optimizer/optimizer/prompts.py`에서:

1. `build_optimization_prompt`의 dimension_guidance (lines 46-53):

```python
# 변경 전 (line 50):
        "boundary": "Add explicit limitations: 'Does NOT handle X', 'Cannot Y', 'Not suitable for Z'.",

# 변경 후:
        "fluency": "Improve sentence flow and readability. Use complete sentences with natural transitions. Avoid fragments or repetitive phrasing.",
```

2. `_build_grounded_guidance`에서 boundary 특별 처리 제거 (lines 221-226 삭제):

```python
# 삭제:
        if "boundary" in weak_dims:
            guidance_parts.append(
                "**boundary**: ONLY state limitations explicitly mentioned "
                "in the original description. Do NOT invent limitations."
            )
```

3. 일반 가이드라인 맵에 fluency 추가 (line ~183):

```python
        generic_guidance = {
            "clarity": "Start with an action verb. Specify WHAT and WHEN to use.",
            "precision": "Include technical terms from the domain (e.g., SQL, REST, JSON).",
            "stats": "Include quantitative info from the original (numbers, percentages, limits).",
            "fluency": "Write in complete, well-connected sentences. Avoid fragments and repetition.",
        }
```

- [ ] **Step 3: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_description_optimizer/test_grounded_prompts.py -v`
Expected: PASS

- [ ] **Step 4: 커밋**

```bash
git add src/description_optimizer/optimizer/prompts.py tests/unit/test_description_optimizer/test_grounded_prompts.py
git commit -m "refactor(desc-optimizer): 프롬프트에서 boundary 제거, fluency 가이드라인 추가"
```

---

### Task 4: 나머지 모든 테스트에서 boundary → fluency 교체

**Files:**
- Modify: `tests/unit/test_description_optimizer/test_llm_optimizer.py`
- Modify: `tests/unit/test_description_optimizer/test_pipeline.py`
- Modify: `tests/unit/test_description_optimizer/test_quality_gate.py`
- Modify: `tests/verification/test_comparison_verification.py`
- Modify: `tests/verification/test_geo_calibration.py`
- Modify: `tests/verification/test_heuristic_edge_cases.py`
- Modify: `tests/verification/test_heuristic_sensitivity.py`
- Modify: `tests/verification/test_llm_optimizer_robustness.py`
- Modify: `tests/verification/test_pipeline_error_paths.py`
- Modify: `tests/verification/test_quality_gate_edge_cases.py`

- [ ] **Step 1: 모든 테스트 파일에서 "boundary" → "fluency" 일괄 교체**

각 파일에서 dimension 목록과 DimensionScore 생성에 사용된 `"boundary"` 문자열을 `"fluency"`로 교체:

**test_llm_optimizer.py:** lines 45, 93, 98, 149 — `"boundary"` → `"fluency"`

**test_pipeline.py:** line 22 — ALL_DIMS 리스트에서 `"boundary"` → `"fluency"`

**test_quality_gate.py:** lines 38, 50, 65, 80, 92, 95, 131, 143, 146, 161, 173 — 모든 리포트 구성 딕셔너리에서 `"boundary"` → `"fluency"`

**test_comparison_verification.py:** line 105 — dims 리스트에서 `"boundary"` → `"fluency"`

**test_geo_calibration.py:**
- line 229 함수명: `test_postgres_boundary_high` → `test_postgres_fluency_reasonable`
- 해당 테스트 내용을 fluency 기반으로 수정 (PostgreSQL description은 잘 구성된 문장이므로 fluency >= 0.3 예상)

**test_heuristic_edge_cases.py:**
- line 147: `test_high_clarity_low_boundary` → `test_high_clarity_low_fluency` (명확한 내용이지만 단편적 구조)
- line 158: `test_high_boundary_low_stats` → `test_high_fluency_low_stats` (유창하지만 통계 없음)
- 테스트 내용을 fluency 특성에 맞게 수정

**test_heuristic_sensitivity.py:**
- TestBoundaryDimension 클래스 → TestFluencyDimension으로 교체:

```python
class TestFluencyDimension:
    async def test_adding_complete_sentence_increases_fluency(self):
        base = "Search data"
        enhanced = "Search the database for matching records. Use this when you need filtered results."
        analyzer = HeuristicAnalyzer()
        base_report = await analyzer.analyze("t", base)
        enh_report = await analyzer.analyze("t", enhanced)
        base_score = next(s.score for s in base_report.dimension_scores if s.dimension == "fluency")
        enh_score = next(s.score for s in enh_report.dimension_scores if s.dimension == "fluency")
        assert enh_score > base_score

    async def test_adding_connectors_increases_fluency(self):
        base = "Search data. Filter results. Return JSON."
        enhanced = "Search data and filter results, then return JSON format."
        analyzer = HeuristicAnalyzer()
        base_report = await analyzer.analyze("t", base)
        enh_report = await analyzer.analyze("t", enhanced)
        base_score = next(s.score for s in base_report.dimension_scores if s.dimension == "fluency")
        enh_score = next(s.score for s in enh_report.dimension_scores if s.dimension == "fluency")
        assert enh_score > base_score
```

**test_llm_optimizer_robustness.py:** line 15 — ALL_DIMS 리스트에서 `"boundary"` → `"fluency"`

**test_pipeline_error_paths.py:** line 23 — _DIMS 리스트에서 `"boundary"` → `"fluency"`

**test_quality_gate_edge_cases.py:** line 14 — _DIMS 리스트에서 `"boundary"` → `"fluency"`

- [ ] **Step 2: 전체 테스트 실행**

Run: `uv run pytest tests/ -v 2>&1 | tail -30`
Expected: ALL PASS

- [ ] **Step 3: 린트 및 포맷**

Run: `uv run ruff check src/ tests/ && uv run ruff format src/ tests/`
Expected: Clean

- [ ] **Step 4: 커밋**

```bash
git add tests/
git commit -m "refactor(desc-optimizer): 전체 테스트에서 boundary → fluency 차원 교체"
```

---

### Task 5: RAGAS Faithfulness 게이트 추가

**Files:**
- Modify: `src/description_optimizer/quality_gate.py`
- Modify: `tests/unit/test_description_optimizer/test_quality_gate.py`

- [ ] **Step 1: RAGAS faithfulness 게이트 테스트 작성**

`tests/unit/test_description_optimizer/test_quality_gate.py`에 추가:

```python
class TestRAGASFaithfulnessGate:
    """Tests for RAGAS-style faithfulness verification."""

    def test_faithful_description_passes(self):
        """Description that only contains verifiable claims passes."""
        gate = QualityGate()
        result = gate.check_faithfulness(
            original="Search the database for records",
            optimized="Search the PostgreSQL database for matching records. Accepts a `query` parameter.",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            claims=[
                {"claim": "Searches the PostgreSQL database", "supported": True},
                {"claim": "Accepts a query parameter", "supported": True},
            ],
        )
        assert result.passed

    def test_hallucinated_claim_fails(self):
        """Description with unsupported claims fails."""
        gate = QualityGate()
        result = gate.check_faithfulness(
            original="Search the database",
            optimized="Search the database. Does not handle complex queries or batch operations.",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            claims=[
                {"claim": "Searches the database", "supported": True},
                {"claim": "Does not handle complex queries", "supported": False},
                {"claim": "Does not handle batch operations", "supported": False},
            ],
        )
        assert not result.passed
        assert "unsupported" in result.reason.lower() or "hallucin" in result.reason.lower()

    def test_no_claims_passes(self):
        """Empty claims list passes (no verification possible)."""
        gate = QualityGate()
        result = gate.check_faithfulness(
            original="Search data",
            optimized="Search data",
            input_schema=None,
            claims=[],
        )
        assert result.passed

    def test_all_unsupported_fails(self):
        """All claims unsupported results in failure."""
        gate = QualityGate()
        result = gate.check_faithfulness(
            original="Get data",
            optimized="Retrieves data with millisecond latency across 50 shards.",
            input_schema=None,
            claims=[
                {"claim": "millisecond latency", "supported": False},
                {"claim": "50 shards", "supported": False},
            ],
        )
        assert not result.passed
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_description_optimizer/test_quality_gate.py::TestRAGASFaithfulnessGate -v`
Expected: FAIL — check_faithfulness 메서드 없음

- [ ] **Step 3: check_faithfulness 구현**

`src/description_optimizer/quality_gate.py`에 추가:

```python
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
```

- [ ] **Step 4: FullGateResult에 faithfulness_result 추가**

```python
@dataclass(frozen=True)
class FullGateResult:
    passed: bool
    geo_result: GateResult
    similarity_result: GateResult
    hallucination_result: GateResult | None = None
    info_preservation_result: GateResult | None = None
    faithfulness_result: GateResult | None = None  # 추가

    @property
    def reason(self) -> str:
        parts: list[str] = []
        for name, result in [
            ("GEO", self.geo_result),
            ("Similarity", self.similarity_result),
            ("Hallucination", self.hallucination_result),
            ("InfoPreservation", self.info_preservation_result),
            ("Faithfulness", self.faithfulness_result),  # 추가
        ]:
            if result is not None:
                parts.append(f"{name}: {result.reason}")
        return " | ".join(parts)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_description_optimizer/test_quality_gate.py -v`
Expected: ALL PASS

- [ ] **Step 6: 커밋**

```bash
git add src/description_optimizer/quality_gate.py tests/unit/test_description_optimizer/test_quality_gate.py
git commit -m "feat(desc-optimizer): RAGAS faithfulness 게이트 추가 — 주장별 이진 검증"
```

---

### Task 6: doc2query 쿼리 인식 프롬프트 추가

**Files:**
- Modify: `src/description_optimizer/optimizer/prompts.py`
- Modify: `tests/unit/test_description_optimizer/test_grounded_prompts.py`

- [ ] **Step 1: 쿼리 인식 프롬프트 테스트 작성**

`tests/unit/test_description_optimizer/test_grounded_prompts.py`에 추가:

```python
def test_query_aware_prompt_includes_queries():
    """Query-aware prompt includes relevant search queries."""
    from description_optimizer.optimizer.prompts import build_query_aware_prompt
    from description_optimizer.models import OptimizationContext

    context = OptimizationContext(
        tool_id="slack::send_message",
        original_description="Send a message",
        input_schema={"type": "object", "properties": {"channel": {"type": "string"}}},
    )
    prompt = build_query_aware_prompt(
        context, relevant_queries=["send a message on slack", "post to a channel"]
    )
    assert "send a message on slack" in prompt
    assert "post to a channel" in prompt


def test_query_aware_prompt_includes_schema():
    """Query-aware prompt includes input_schema when available."""
    from description_optimizer.optimizer.prompts import build_query_aware_prompt
    from description_optimizer.models import OptimizationContext

    context = OptimizationContext(
        tool_id="test::tool",
        original_description="Do something",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
    )
    prompt = build_query_aware_prompt(context, relevant_queries=[])
    assert "query" in prompt


def test_query_aware_prompt_anti_hallucination():
    """Query-aware prompt includes anti-hallucination rules."""
    from description_optimizer.optimizer.prompts import build_query_aware_prompt
    from description_optimizer.models import OptimizationContext

    context = OptimizationContext(
        tool_id="test::tool", original_description="Do something"
    )
    prompt = build_query_aware_prompt(context, relevant_queries=["find test tool"])
    assert "NEVER" in prompt or "never" in prompt.lower()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_description_optimizer/test_grounded_prompts.py::test_query_aware_prompt_includes_queries -v`
Expected: FAIL — build_query_aware_prompt 없음

- [ ] **Step 3: build_query_aware_prompt 구현**

`src/description_optimizer/optimizer/prompts.py`에 추가:

```python
def build_query_aware_prompt(
    context: OptimizationContext,
    relevant_queries: list[str] | None = None,
) -> str:
    """Build optimization prompt focused on retrieval discoverability.

    Instead of "improve GEO dimension scores", tells the optimizer:
    "Make this tool findable for these search queries."
    """
    queries = relevant_queries or []

    parts = [
        "You are optimizing an MCP tool description for search discoverability.",
        "",
        f"**Tool ID:** {context.tool_id}",
        f"**Original Description:** {context.original_description}",
    ]

    if context.input_schema:
        parts.append(
            f"\n**Input Schema** (factual ground truth):\n"
            f"```json\n{json.dumps(context.input_schema, indent=2)}\n```"
        )

    if context.sibling_tools:
        parts.append("\n**Other tools on this server** (for disambiguation):")
        for t in context.sibling_tools[:5]:
            parts.append(f"- {t.get('tool_name', '')}: {t.get('description', '')[:100]}")

    if queries:
        parts.append("\n**Search queries that should find this tool:**")
        for q in queries[:10]:
            parts.append(f'- "{q}"')
        parts.append(
            "\nMake the description naturally match these search intents. "
            "A user typing any of these queries should find this tool first."
        )

    parts.extend([
        "\n## Rules",
        "1. KEEP the original description text intact — AUGMENT, do not replace",
        "2. ONLY add information from the original description or input_schema",
        "3. NEVER invent limitations, capabilities, or parameters not in the provided data",
        "4. Make the description naturally match the search queries above",
        "5. Include actual parameter names from the schema (with backticks) if available",
        "6. If sibling tools exist, briefly clarify what makes this tool different",
        "",
        '## Output Format',
        'Return JSON: {"optimized_description": "...", "search_description": "..."}',
        "- optimized_description: 50-200 words, human+machine readable",
        "- search_description: 30-80 words, keyword-dense for embedding search",
    ])

    return "\n".join(parts)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_description_optimizer/test_grounded_prompts.py -v`
Expected: ALL PASS

- [ ] **Step 5: 커밋**

```bash
git add src/description_optimizer/optimizer/prompts.py tests/unit/test_description_optimizer/test_grounded_prompts.py
git commit -m "feat(desc-optimizer): doc2query 쿼리 인식 최적화 프롬프트 추가"
```

---

### Task 7: P@1 A/B 검색 평가 스크립트

**Files:**
- Create: `scripts/run_retrieval_ab_eval.py`

- [ ] **Step 1: P@1 A/B 평가 스크립트 작성**

```python
"""Retrieval A/B Evaluation — P@1 비교 (원본 vs 최적화 description).

Description 최적화의 궁극적 검증: "최적화된 description이 실제로 도구 선택 정확도를 높이는가?"

Usage:
    PYTHONPATH=src uv run python scripts/run_retrieval_ab_eval.py \
        --tools data/raw/servers.jsonl \
        --ground-truth data/ground_truth/seed_set.jsonl \
        --optimized data/verification/grounded_optimization_results.jsonl
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loguru import logger


async def load_tools(tools_path: Path) -> dict[str, str]:
    """서버 JSONL에서 tool_id → description 매핑 로드."""
    tool_descriptions: dict[str, str] = {}
    with open(tools_path) as f:
        for line in f:
            server = json.loads(line.strip())
            server_id = server.get("qualifiedName", server.get("name", ""))
            for tool in server.get("tools", []):
                tool_name = tool.get("name", "")
                tool_id = f"{server_id}::{tool_name}"
                desc = tool.get("description", "")
                if desc:
                    tool_descriptions[tool_id] = desc
    return tool_descriptions


async def load_ground_truth(gt_path: Path) -> dict[str, list[str]]:
    """Ground truth를 correct_tool_id별로 쿼리 그룹화."""
    relevant_queries: dict[str, list[str]] = {}
    with open(gt_path) as f:
        for line in f:
            entry = json.loads(line.strip())
            tool_id = entry["correct_tool_id"]
            query = entry["query"]
            relevant_queries.setdefault(tool_id, []).append(query)
    return relevant_queries


async def load_optimized(opt_path: Path) -> dict[str, str]:
    """최적화된 description 로드 (성공 건만)."""
    optimized: dict[str, str] = {}
    with open(opt_path) as f:
        for line in f:
            entry = json.loads(line.strip())
            if entry.get("status") == "success":
                optimized[entry["tool_id"]] = entry["optimized_description"]
    return optimized


async def compute_retrieval_scores(
    embedder: "Embedder",
    tool_descriptions: dict[str, str],
    relevant_queries: dict[str, list[str]],
) -> dict[str, dict]:
    """임베딩 기반 검색 성능 측정 (인메모리 코사인 유사도)."""
    tool_ids = list(tool_descriptions.keys())
    texts = [tool_descriptions[tid] for tid in tool_ids]

    logger.info(f"Embedding {len(texts)} tool descriptions...")
    vectors = await embedder.embed_batch(texts)
    pool = np.stack(vectors)
    norms = np.linalg.norm(pool, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    pool = pool / norms

    results: dict[str, dict] = {}

    for tool_id, queries in relevant_queries.items():
        if tool_id not in tool_ids:
            continue

        tool_idx = tool_ids.index(tool_id)
        ranks: list[int] = []

        for query in queries:
            q_vec = await embedder.embed_one(query)
            q_norm = np.linalg.norm(q_vec)
            if q_norm > 0:
                q_vec = q_vec / q_norm
            sims = pool @ q_vec
            sorted_indices = np.argsort(-sims)
            rank = int(np.where(sorted_indices == tool_idx)[0][0]) + 1
            ranks.append(rank)

        p_at_1 = sum(1 for r in ranks if r == 1) / len(ranks) if ranks else 0
        mrr = sum(1.0 / r for r in ranks) / len(ranks) if ranks else 0
        results[tool_id] = {"p_at_1": p_at_1, "mrr": mrr, "avg_rank": sum(ranks) / len(ranks) if ranks else 0, "n_queries": len(ranks)}

    return results


async def main(args: argparse.Namespace) -> None:
    tools_path = Path(args.tools)
    gt_path = Path(args.ground_truth)
    opt_path = Path(args.optimized)

    for p in [tools_path, gt_path, opt_path]:
        if not p.exists():
            logger.error(f"File not found: {p}")
            return

    tool_descriptions = await load_tools(tools_path)
    relevant_queries = await load_ground_truth(gt_path)
    optimized_descriptions = await load_optimized(opt_path)

    logger.info(
        f"Loaded {len(tool_descriptions)} tools, "
        f"{sum(len(v) for v in relevant_queries.values())} GT queries, "
        f"{len(optimized_descriptions)} optimized descriptions"
    )

    from embedding.openai_embedder import OpenAIEmbedder

    embedder = OpenAIEmbedder()

    # Condition A: 원본 description
    logger.info("=== Condition A: Original descriptions ===")
    scores_original = await compute_retrieval_scores(embedder, tool_descriptions, relevant_queries)

    # Condition B: 최적화 description
    logger.info("=== Condition B: Optimized descriptions ===")
    optimized_pool = dict(tool_descriptions)
    for tool_id, opt_desc in optimized_descriptions.items():
        if tool_id in optimized_pool:
            optimized_pool[tool_id] = opt_desc
    scores_optimized = await compute_retrieval_scores(embedder, optimized_pool, relevant_queries)

    # 비교 리포트
    shared_tools = set(scores_original.keys()) & set(scores_optimized.keys())
    p1_orig = [scores_original[t]["p_at_1"] for t in shared_tools]
    p1_opt = [scores_optimized[t]["p_at_1"] for t in shared_tools]
    mrr_orig = [scores_original[t]["mrr"] for t in shared_tools]
    mrr_opt = [scores_optimized[t]["mrr"] for t in shared_tools]

    logger.info("=" * 60)
    logger.info("RETRIEVAL A/B EVALUATION REPORT")
    logger.info("=" * 60)
    logger.info(f"Tools evaluated: {len(shared_tools)}")
    logger.info(f"Condition A (Original):  P@1={np.mean(p1_orig):.4f}, MRR={np.mean(mrr_orig):.4f}")
    logger.info(f"Condition B (Optimized): P@1={np.mean(p1_opt):.4f}, MRR={np.mean(mrr_opt):.4f}")

    delta_p1 = np.mean(p1_opt) - np.mean(p1_orig)
    delta_mrr = np.mean(mrr_opt) - np.mean(mrr_orig)
    logger.info(f"Delta P@1: {delta_p1:+.4f}")
    logger.info(f"Delta MRR: {delta_mrr:+.4f}")

    # Per-tool 비교
    improved = sum(1 for t in shared_tools if scores_optimized[t]["p_at_1"] > scores_original[t]["p_at_1"])
    degraded = sum(1 for t in shared_tools if scores_optimized[t]["p_at_1"] < scores_original[t]["p_at_1"])
    same = len(shared_tools) - improved - degraded
    logger.info(f"Per-tool: {improved} improved, {degraded} degraded, {same} same")

    if delta_p1 >= 0.05:
        logger.info("RESULT: Optimization IMPROVES retrieval (+5pp or more)")
    elif delta_p1 >= 0:
        logger.info("RESULT: Optimization has MARGINAL positive effect")
    else:
        logger.info("RESULT: Optimization DEGRADES retrieval — investigate")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieval A/B Evaluation")
    parser.add_argument("--tools", default="data/raw/servers.jsonl")
    parser.add_argument("--ground-truth", default="data/ground_truth/seed_set.jsonl")
    parser.add_argument("--optimized", default="data/verification/grounded_optimization_results.jsonl")
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
```

- [ ] **Step 2: 커밋**

```bash
git add scripts/run_retrieval_ab_eval.py
git commit -m "feat(desc-optimizer): P@1 A/B 검색 평가 스크립트"
```

---

### Task 8: 전체 검증 및 문서 업데이트

**Files:**
- Modify: `description_optimizer/CLAUDE.md`

- [ ] **Step 1: 전체 테스트 실행**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: 커버리지 확인**

Run: `uv run pytest tests/ --cov=src -v 2>&1 | tail -20`
Expected: >= 90%

- [ ] **Step 3: 린트 및 포맷**

Run: `uv run ruff check src/ tests/ && uv run ruff format src/ tests/`
Expected: Clean

- [ ] **Step 4: CLAUDE.md 업데이트**

`description_optimizer/CLAUDE.md`에서:
- "6-dimension heuristic" → 차원 목록 업데이트 (boundary 제거, fluency 추가)
- RAGAS faithfulness 게이트 추가 기록
- doc2query 쿼리 인식 프롬프트 추가 기록

- [ ] **Step 5: 최종 커밋**

```bash
git add description_optimizer/CLAUDE.md
git commit -m "docs(desc-optimizer): Phase 2 구현 완료 — boundary→fluency, RAGAS, doc2query"
```

---

## Verification

### 테스트 실행
```bash
uv run pytest tests/unit/test_description_optimizer/ -v    # 단위 테스트
uv run pytest tests/verification/ -v                        # 검증 테스트
uv run pytest tests/ --cov=src -v                           # 커버리지
uv run ruff check src/ tests/                               # 린트
```

### P@1 A/B 평가 (API 키 필요)
```bash
PYTHONPATH=src uv run python scripts/run_retrieval_ab_eval.py
```

### 성공 기준
| 메트릭 | 기준값 |
|--------|--------|
| 전체 테스트 | PASS |
| 커버리지 | >= 90% |
| 린트 | Clean |
| boundary 참조 | 코드에 0건 |
| fluency 차원 | 모든 분석에 포함 |
