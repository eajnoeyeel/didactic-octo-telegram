# Description Optimizer — Disambiguation Redesign

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate sibling name contamination from disambiguation by replacing "unlike X, Y, Z" patterns with target-only qualifiers, then re-validate via 3-way A/B evaluation.

**Architecture:** Three-layer change: (1) heuristic analyzer stops rewarding contrast phrases that embed sibling names, (2) LLM prompts stop listing sibling tool names in disambiguation guidance, (3) re-optimize + re-evaluate the 18 GT tools to confirm P@1 recovery.

**Tech Stack:** Python 3.12, pytest, pytest-asyncio, loguru, pydantic v2

---

## Context

- 3-way A/B 결과: original P@1=0.5417, search/optimized P@1=0.4722 (δ=-0.069)
- 근본원인 확인: sibling tool 이름이 target description에 삽입되어 embedding 공간에서 혼동 유발
- 대표 사례: `math-mcp::median` — "unlike addition, subtraction, multiplication, division" 포함 → P@1 1.0→0.0
- 대표 사례: `math-mcp::round` — arithmetic operation 비교 문구 → P@1 1.0→0.0
- 대표 사례: `instagram::INSTAGRAM_GET_USER_MEDIA` — CREATE/POST sibling 대비 문구 → P@1 1.0→0.0

### Root Cause

현재 disambiguation 구현은 두 가지 경로로 sibling 이름을 주입한다:

1. **프롬프트** (`prompts.py`): `_build_grounded_guidance`가 sibling tool 이름을 나열하고 "Differentiate from these sibling tools: X, Y, Z"라고 지시
2. **휴리스틱** (`heuristic.py`): `_CONTRAST_PHRASES` 패턴("unlike", "not to be confused with")과 `_NEGATIVE_INSTRUCTIONS`("not for", "cannot")에 높은 점수를 부여

### Design Decision

**Before (contamination):**
- "Unlike addition, subtraction, and division, this tool specifically calculates the median..."
- Sibling 이름이 target embedding에 포함 → confusion 증가

**After (target-only qualifier):**
- "Calculates the median — the middle value of a sorted numeric list. Use when analyzing central tendency of a dataset."
- Target의 고유 동작/도메인만 강조 → embedding 분리도 유지

## File Structure

| 파일 | 변경 유형 | 역할 |
|------|-----------|------|
| `tests/unit/test_description_optimizer/test_heuristic.py` | Modify | disambiguation 점수 변경 테스트 |
| `src/description_optimizer/analyzer/heuristic.py` | Modify | contrast phrase → target-specificity 스코링 |
| `tests/unit/test_description_optimizer/test_prompts.py` | Modify | 프롬프트 변경 테스트 |
| `src/description_optimizer/optimizer/prompts.py` | Modify | sibling 이름 제거, target-only guidance |
| `scripts/run_grounded_optimization.py` | No change | 기존 스크립트로 재최적화 |
| `scripts/run_retrieval_ab_eval.py` | No change | 기존 스크립트로 재평가 |

---

### Task 1: Heuristic Analyzer — Remove Contrast Phrase Rewards (Test First)

**Files:**
- Modify: `tests/unit/test_description_optimizer/test_heuristic.py`

- [ ] **Step 1: Write test that contrast phrases no longer boost disambiguation score**

Add a new test class to the existing test file:

```python
class TestDisambiguationRedesign:
    """Verify disambiguation no longer rewards sibling name contamination."""

    @pytest.fixture
    def analyzer(self) -> HeuristicAnalyzer:
        return HeuristicAnalyzer()

    @pytest.mark.asyncio
    async def test_contrast_phrases_do_not_boost_score(self, analyzer: HeuristicAnalyzer) -> None:
        """'Unlike X, Y, Z' should NOT increase disambiguation score."""
        clean = "Calculates the median value of a sorted numeric list."
        contaminated = (
            "Calculates the median value. Unlike addition, subtraction, "
            "and division, this tool specifically finds the middle value."
        )
        report_clean = await analyzer.analyze("s::median", clean)
        report_dirty = await analyzer.analyze("s::median", contaminated)
        score_clean = next(s for s in report_clean.dimension_scores if s.dimension == "disambiguation")
        score_dirty = next(s for s in report_dirty.dimension_scores if s.dimension == "disambiguation")
        # Contaminated text should NOT score higher than clean text
        assert score_dirty.score <= score_clean.score

    @pytest.mark.asyncio
    async def test_target_specificity_rewards_action_object(self, analyzer: HeuristicAnalyzer) -> None:
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
    async def test_domain_qualifier_without_sibling_names(self, analyzer: HeuristicAnalyzer) -> None:
        """Domain qualifiers like 'specifically for' boost score without sibling names."""
        desc = "Specifically handles rounding numeric values to the nearest whole integer."
        report = await analyzer.analyze("s::round", desc)
        score = next(s for s in report.dimension_scores if s.dimension == "disambiguation")
        assert score.score > 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_description_optimizer/test_heuristic.py::TestDisambiguationRedesign -v`
Expected: FAIL — `test_contrast_phrases_do_not_boost_score` fails because contrast phrases still get +0.3 each

---

### Task 2: Implement Target-Specificity Disambiguation Scoring

**Files:**
- Modify: `src/description_optimizer/analyzer/heuristic.py:41-54,161-189`

- [ ] **Step 1: Replace contrast phrase patterns with target-specificity patterns**

Replace the disambiguation pattern block (lines 41-54) with:

```python
    # --- Disambiguation patterns (target-specificity, NO sibling name rewards) ---
    _UNIQUE_ACTION: re.Pattern[str] = re.compile(
        r"\b(specifically|exclusively|dedicated to|focused on|specializes in)\b",
        re.IGNORECASE,
    )
    _ACTION_OBJECT_PAIR: re.Pattern[str] = re.compile(
        r"\b(calculates? the|retrieves? the|converts? the|rounds? the|finds? the"
        r"|creates? a|generates? a|searches? for|lists? all|fetches? the"
        r"|deletes? the|updates? the|sends? a|gets? the|posts? a)\b",
        re.IGNORECASE,
    )
    _SCOPE_DELIMITER: re.Pattern[str] = re.compile(
        r"\b(only for|limited to|restricted to|within the|from the)\b",
        re.IGNORECASE,
    )
```

- [ ] **Step 2: Replace `_score_disambiguation` method**

Replace lines 161-189 with:

```python
    def _score_disambiguation(self, desc: str) -> DimensionScore:
        score = 0.0
        reasons: list[str] = []

        # Action-object pairs — each +0.2, cap 0.4
        # Rewards descriptions that clearly state WHAT the tool does to WHAT
        ao_matches = self._ACTION_OBJECT_PAIR.findall(desc)
        ao_contribution = _clamp(len(ao_matches) * 0.2, hi=0.4)
        score += ao_contribution
        if ao_matches:
            reasons.append(f"action_object_pairs={len(ao_matches)}")

        # Unique action qualifiers — each +0.2, cap 0.3
        # Rewards "specifically", "exclusively", "dedicated to" WITHOUT naming siblings
        unique_matches = self._UNIQUE_ACTION.findall(desc)
        unique_contribution = _clamp(len(unique_matches) * 0.2, hi=0.3)
        score += unique_contribution
        if unique_matches:
            reasons.append(f"unique_qualifiers={len(unique_matches)}")

        # Scope delimiters — each +0.15, cap 0.3
        # Rewards scope narrowing like "only for", "limited to", "within the"
        scope_matches = self._SCOPE_DELIMITER.findall(desc)
        scope_contribution = _clamp(len(scope_matches) * 0.15, hi=0.3)
        score += scope_contribution
        if scope_matches:
            reasons.append(f"scope_delimiters={len(scope_matches)}")

        final = _clamp(score)
        return DimensionScore(
            dimension="disambiguation",
            score=final,
            explanation=f"Disambiguation score {final:.2f}: {', '.join(reasons) or 'no signals'}",
        )
```

- [ ] **Step 3: Remove the old `_CONTRAST_PHRASES`, `_DOMAIN_QUALIFIERS`, `_NEGATIVE_INSTRUCTIONS` patterns**

Delete lines 41-54 (the three old regex patterns). They are fully replaced by the new patterns in Step 1.

- [ ] **Step 4: Run disambiguation tests**

Run: `uv run pytest tests/unit/test_description_optimizer/test_heuristic.py::TestDisambiguationRedesign -v`
Expected: ALL PASS

- [ ] **Step 5: Run full heuristic test suite**

Run: `uv run pytest tests/unit/test_description_optimizer/test_heuristic.py -v`
Expected: Check for any regressions. Some existing tests may need updating if they asserted on old contrast phrase behavior.

- [ ] **Step 6: Fix any failing existing tests**

If existing tests assert that contrast phrases boost disambiguation, update them to match the new behavior. For example, tests that check "unlike X increases score" should be removed or inverted.

- [ ] **Step 7: Commit**

```bash
git add src/description_optimizer/analyzer/heuristic.py tests/unit/test_description_optimizer/test_heuristic.py
git commit -m "feat(heuristic): replace contrast-phrase disambiguation with target-specificity scoring"
```

---

### Task 3: Prompt — Remove Sibling Name Listing (Test First)

**Files:**
- Modify: `tests/unit/test_description_optimizer/test_prompts.py`

- [ ] **Step 1: Write test that sibling names are NOT listed in disambiguation guidance**

Add to the existing test file:

```python
class TestDisambiguationPromptRedesign:
    """Verify prompts no longer list sibling tool names in disambiguation guidance."""

    def test_grounded_guidance_no_sibling_names_in_disambiguation(self) -> None:
        """Disambiguation guidance should NOT mention sibling tool names."""
        guidance = _build_grounded_guidance(
            weak_dimensions=["disambiguation"],
            dimension_scores={"disambiguation": 0.1},
            input_schema=None,
            sibling_tools=[
                {"tool_name": "add", "description": "Adds two numbers"},
                {"tool_name": "subtract", "description": "Subtracts numbers"},
            ],
        )
        # Should NOT list sibling tool names for comparison
        # Note: "add" may appear in words like "additionally" — check for standalone usage
        assert "sibling tools: add" not in guidance.lower()
        assert "subtract" not in guidance.lower()
        assert "Differentiate from these sibling tools" not in guidance

    def test_grounded_guidance_uses_target_only_language(self) -> None:
        """Disambiguation guidance should focus on target tool's unique qualities."""
        guidance = _build_grounded_guidance(
            weak_dimensions=["disambiguation"],
            dimension_scores={"disambiguation": 0.2},
            input_schema=None,
            sibling_tools=[
                {"tool_name": "mean", "description": "Calculates the mean"},
            ],
        )
        # Should contain target-focused language
        assert "unique" in guidance.lower() or "specific" in guidance.lower()

    def test_grounded_prompt_sibling_section_removed(self) -> None:
        """build_grounded_prompt should NOT include sibling tools section."""
        prompt = build_grounded_prompt(
            original="Calculates the median of a list of numbers",
            tool_id="math::median",
            input_schema={"properties": {"numbers": {"type": "array"}}, "required": ["numbers"]},
            sibling_tools=[
                {"tool_name": "mean", "description": "Calculates the mean"},
                {"tool_name": "mode", "description": "Calculates the mode"},
            ],
            weak_dimensions=["disambiguation"],
            dimension_scores={"disambiguation": 0.1},
        )
        assert "Other tools on this server" not in prompt
        # Sibling tool names should not appear as listed items
        assert "- mean:" not in prompt.lower()
        assert "- mode:" not in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_description_optimizer/test_prompts.py::TestDisambiguationPromptRedesign -v`
Expected: FAIL — sibling names are still listed

---

### Task 4: Implement Prompt Changes — Remove Sibling Contamination

**Files:**
- Modify: `src/description_optimizer/optimizer/prompts.py:51-58,130-140,213-225,282-285`

- [ ] **Step 1: Update `build_optimization_prompt` disambiguation guidance**

Replace the `dimension_guidance` dict entry for `"disambiguation"` (line 54):

```python
        "disambiguation": "Clarify what makes THIS tool unique: its specific action, target data type, or domain. Do NOT mention or compare with other tools by name.",
```

- [ ] **Step 2: Remove sibling tools section from `build_grounded_prompt`**

Remove lines 130-140 (the sibling tools section):

```python
    # Sibling tools section — only if available
    if sibling_tools:
        sibling_lines = []
        for st in sibling_tools[:8]:
            desc_preview = (st.get("description") or "")[:120]
            sibling_lines.append(f"- {st['tool_name']}: {desc_preview}")
        siblings_text = "\n".join(sibling_lines)
        sections.append(
            f"**Other tools on this server** (use for disambiguation — "
            f"explain how THIS tool differs):\n{siblings_text}\n"
        )
```

Replace with nothing (delete the entire block). The sibling_tools parameter stays in the function signature for backward compatibility but is no longer used in the prompt text.

- [ ] **Step 3: Update `_build_grounded_guidance` disambiguation section**

Replace lines 213-225 (the disambiguation guidance):

```python
    if "disambiguation" in weak_dimensions:
        lines.append(
            f"  - **disambiguation** ({dimension_scores.get('disambiguation', 0):.2f}): "
            f"Clarify what makes THIS tool unique — its specific action, target data type, "
            f"or domain scope. Use phrases like 'specifically handles [action] for [domain]'. "
            f"Do NOT mention other tools by name or compare with siblings."
        )
```

- [ ] **Step 4: Update `build_query_aware_prompt` sibling section**

Replace lines 282-285 (the sibling section in query-aware prompt):

```python
    if context.sibling_tools:
        parts.append("\n**Other tools on this server** (for disambiguation):")
        for t in context.sibling_tools[:5]:
            parts.append(f"- {t.get('tool_name', '')}: {t.get('description', '')[:100]}")
```

Replace with:

```python
    if context.sibling_tools:
        parts.append(
            f"\nThis server has {len(context.sibling_tools)} other tools. "
            f"Focus on what makes THIS tool unique without naming the others."
        )
```

- [ ] **Step 5: Run prompt tests**

Run: `uv run pytest tests/unit/test_description_optimizer/test_prompts.py -v`
Expected: ALL PASS (including new tests from Task 3)

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/description_optimizer/optimizer/prompts.py tests/unit/test_description_optimizer/test_prompts.py
git commit -m "feat(prompt): remove sibling name contamination from disambiguation guidance"
```

---

### Task 5: Lint & Verification

**Files:** All modified files

- [ ] **Step 1: Lint and format**

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

- [ ] **Step 2: Full test suite with coverage**

```bash
uv run pytest tests/ --cov=src -v --tb=short
```
Expected: ALL PASS, coverage >= 80%

- [ ] **Step 3: Security scan**

```bash
grep -rn "api_key\s*=\s*['\"]" src/ tests/
grep -rn "print(" src/
```
Expected: No hardcoded secrets, no print() statements

- [ ] **Step 4: Commit any lint fixes**

```bash
git add -u
git commit -m "style: lint and format fixes for disambiguation redesign"
```

---

### Task 6: Re-Optimize GT Tools (Integration — API key required)

**Files:**
- Script: `scripts/run_grounded_optimization.py` (existing, no changes)
- Output: `data/verification/gt_optimized_descriptions_v2.jsonl`

- [ ] **Step 1: Run grounded optimization with new prompts on the 18 GT tools**

```bash
PYTHONPATH=src uv run python scripts/run_grounded_optimization.py \
    --tools data/raw/servers.jsonl \
    --ground-truth data/ground_truth/seed_set.jsonl \
    --output data/verification/gt_optimized_descriptions_v2.jsonl
```

- [ ] **Step 2: Verify no sibling names in optimized descriptions**

```python
# Quick verification script
import json
sibling_contamination = []
with open("data/verification/gt_optimized_descriptions_v2.jsonl") as f:
    for line in f:
        d = json.loads(line)
        if d.get("status") == "success":
            opt = d["optimized_description"].lower()
            search = d["search_description"].lower()
            for phrase in ["unlike ", "not to be confused with", "as opposed to", "different from"]:
                if phrase in opt or phrase in search:
                    sibling_contamination.append(d["tool_id"])
                    break
print(f"Contaminated: {len(sibling_contamination)} / total success")
print(sibling_contamination)
```
Expected: 0 contaminated descriptions

- [ ] **Step 3: Spot-check the 3 previously degraded tools**

Verify that `median`, `round`, `INSTAGRAM_GET_USER_MEDIA` no longer contain sibling tool names:

```bash
cat data/verification/gt_optimized_descriptions_v2.jsonl | python3 -c "
import sys, json
targets = ['median', 'round', 'INSTAGRAM_GET_USER_MEDIA']
for line in sys.stdin:
    d = json.loads(line)
    if d.get('status') == 'success' and any(t in d['tool_id'] for t in targets):
        print(f\"=== {d['tool_id']} ===\")
        print(f\"OPTIMIZED: {d['optimized_description']}\")
        print(f\"SEARCH: {d['search_description']}\")
        print()
"
```

- [ ] **Step 4: Commit re-optimization results**

```bash
git add data/verification/gt_optimized_descriptions_v2.jsonl
git commit -m "data: re-optimized GT tools with disambiguation redesign (no sibling names)"
```

---

### Task 7: 3-Way A/B Re-Evaluation (Integration — API key required)

**Files:**
- Script: `scripts/run_retrieval_ab_eval.py` (existing, no changes)
- Output: `data/verification/retrieval_3way_ab_gt_report_v2.json`

- [ ] **Step 1: Run 3-way A/B evaluation with v2 descriptions**

```bash
PYTHONPATH=src uv run python scripts/run_retrieval_ab_eval.py \
    --tools data/raw/servers.jsonl \
    --ground-truth data/ground_truth/seed_set.jsonl \
    --optimized data/verification/gt_optimized_descriptions_v2.jsonl \
    --output data/verification/retrieval_3way_ab_gt_report_v2.json
```

- [ ] **Step 2: Analyze results — compare with v1 baseline**

Read `data/verification/retrieval_3way_ab_gt_report_v2.json` and compare:

| Metric | v1 (sibling contamination) | v2 (target-only) | Δ |
|--------|---------------------------|-------------------|---|
| Original P@1 | 0.5417 | should be same | 0 |
| Search P@1 | 0.4722 | target: >= 0.5417 | ? |
| Optimized P@1 | 0.4722 | target: >= 0.5417 | ? |

**Success criteria:**
- `delta_search_vs_orig >= 0.0` (search_description no longer degrades retrieval)
- The 3 previously degraded tools (median, round, INSTAGRAM_GET_USER_MEDIA) recover to P@1=1.0
- No new degradations introduced

- [ ] **Step 3: Commit evaluation results**

```bash
git add data/verification/retrieval_3way_ab_gt_report_v2.json
git commit -m "data: 3-way A/B v2 results — disambiguation redesign validation"
```

---

### Task 8: Update Documentation

**Files:**
- Modify: `docs/progress/status-report.md`
- Modify: `docs/analysis/description-optimizer-root-cause-analysis.md`

- [ ] **Step 1: Update status report with v2 results**

Add disambiguation redesign results section to `docs/progress/status-report.md` with actual P@1 numbers from Task 7.

- [ ] **Step 2: Update root cause analysis with resolution**

Add a "## 10. Resolution" section to `docs/analysis/description-optimizer-root-cause-analysis.md`:
- Document that sibling name contamination was removed
- Record v1 vs v2 P@1 comparison
- Note whether the core thesis ("higher description quality → higher tool selection rate") is now validated

- [ ] **Step 3: Update memory file**

Update `/Users/iminjae/.claude/projects/-Users-iminjae-mcp-optimizer/memory/project_desc_optimizer.md` with v2 results.

- [ ] **Step 4: Commit**

```bash
git add docs/progress/status-report.md docs/analysis/description-optimizer-root-cause-analysis.md
git commit -m "docs: update progress with disambiguation redesign results"
```
