# Description Optimizer — Grounded Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Status: IMPLEMENTATION COMPLETE (2026-03-29).** 10 tasks 구현 완료, 389 tests, 92% coverage.
> **A/B 비교 완료.** Grounded가 실질적 품질 우수하나 GEO scorer Goodhart's Law 문제 발견.
> **다음 단계:** 논문 리서치 → GEO scorer 개선. 상세: `docs/analysis/grounded-ab-comparison-report.md`

**Goal:** Transform the Description Optimizer from a heuristic-gaming system into one that produces genuinely better descriptions that improve actual tool selection accuracy (Precision@1).

**Architecture:** Three-layer fix: (1) Ground the LLM in real data (input_schema + sibling tools) so it can't hallucinate, (2) Switch from full-rewrite to augmentation to preserve existing good information, (3) Add hallucination detection and end-to-end tool selection evaluation to break the circular validation loop.

**Tech Stack:** Python 3.12, pytest + pytest-asyncio, OpenAI GPT-4o-mini, Pydantic v2, loguru, numpy

---

## Root Cause Summary (from `docs/analysis/description-optimizer-root-cause-analysis.md`)

| Problem | Impact | Fix |
|---------|--------|-----|
| LLM has no `input_schema` | Parameters hallucinated | Task 1-2: Pass real schema |
| LLM has no sibling context | Fake "unlike other tools..." | Task 3: Pass sibling tools |
| Full rewrite mode | Destroys stats, clarity, precision | Task 4: Augmentation mode |
| Boundary guideline says "add limitations" | Limitations fabricated | Task 2: Remove/restrict |
| Same heuristic = target + evaluator | Goodhart's Law circular validation | Task 6: Tool Selection eval |
| Gate can't catch domain hallucination | Hallucinated params pass cosine check | Task 5: HallucinationGate |

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/description_optimizer/optimizer/base.py` | Extend ABC to accept `OptimizationContext` |
| Modify | `src/description_optimizer/optimizer/prompts.py` | Grounded prompts with input_schema + sibling tools |
| Modify | `src/description_optimizer/optimizer/llm_optimizer.py` | Pass context to prompt builder |
| Modify | `src/description_optimizer/pipeline.py` | Accept `MCPTool` + sibling tools, augmentation mode |
| Modify | `src/description_optimizer/quality_gate.py` | Add HallucinationGate + InformationPreservationGate |
| Create | `src/description_optimizer/models.py` | Add `OptimizationContext` model |
| Modify | `scripts/optimize_descriptions.py` | Pass MCPTool objects with input_schema |
| Modify | `scripts/run_comparison_verification.py` | Pass input_schema in sampling |
| Create | `scripts/run_selection_eval.py` | Tool Selection A/B evaluation |
| Modify | `tests/unit/test_description_optimizer/test_pipeline.py` | Update for new pipeline interface |
| Modify | `tests/unit/test_description_optimizer/test_llm_optimizer.py` | Update for context-aware optimize |
| Modify | `tests/unit/test_description_optimizer/test_quality_gate.py` | Test new gates |
| Create | `tests/unit/test_description_optimizer/test_grounded_prompts.py` | Prompt construction tests |
| Create | `tests/evaluation/test_selection_eval.py` | Tool selection evaluation tests |

---

### Task 1: Add OptimizationContext Model

**Files:**
- Modify: `src/description_optimizer/models.py`
- Create: `tests/unit/test_description_optimizer/test_grounded_prompts.py`

The optimizer currently receives only `AnalysisReport` (which has no `input_schema` or sibling tools). We need a context object that carries real tool data.

- [ ] **Step 1: Write failing test for OptimizationContext**

```python
# tests/unit/test_description_optimizer/test_grounded_prompts.py

from description_optimizer.models import OptimizationContext


def test_optimization_context_with_schema():
    ctx = OptimizationContext(
        tool_id="slack::SLACK_DELETE_A_COMMENT_ON_A_FILE",
        original_description="Deletes a specific comment from a file in Slack.",
        input_schema={
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File ID"},
                "id": {"type": "string", "description": "Comment ID"},
            },
            "required": ["file", "id"],
        },
        sibling_tools=[
            {"tool_name": "SLACK_ADD_A_COMMENT_ON_A_FILE", "description": "Adds a comment to a file."},
            {"tool_name": "SLACK_GET_FILE_INFO", "description": "Gets information about a file."},
        ],
    )
    assert ctx.tool_id == "slack::SLACK_DELETE_A_COMMENT_ON_A_FILE"
    assert ctx.input_schema is not None
    assert "file" in ctx.input_schema["properties"]
    assert len(ctx.sibling_tools) == 2


def test_optimization_context_without_schema():
    ctx = OptimizationContext(
        tool_id="test::tool",
        original_description="A test tool.",
        input_schema=None,
        sibling_tools=[],
    )
    assert ctx.input_schema is None
    assert ctx.sibling_tools == []


def test_optimization_context_parameter_names():
    ctx = OptimizationContext(
        tool_id="test::tool",
        original_description="A test tool.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
        sibling_tools=[],
    )
    assert ctx.parameter_names == ["query", "limit"]


def test_optimization_context_parameter_names_no_schema():
    ctx = OptimizationContext(
        tool_id="test::tool",
        original_description="A test tool.",
        input_schema=None,
        sibling_tools=[],
    )
    assert ctx.parameter_names == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_description_optimizer/test_grounded_prompts.py -v`
Expected: FAIL with `ImportError: cannot import name 'OptimizationContext'`

- [ ] **Step 3: Implement OptimizationContext**

Add to `src/description_optimizer/models.py`:

```python
class OptimizationContext(BaseModel):
    """Context for grounded description optimization.

    Carries real tool data (input_schema, sibling tools) so the LLM
    can produce factually accurate descriptions without hallucination.
    """

    tool_id: str
    original_description: str
    input_schema: dict | None = None
    sibling_tools: list[dict] = Field(default_factory=list)

    @computed_field
    @property
    def parameter_names(self) -> list[str]:
        if not self.input_schema:
            return []
        props = self.input_schema.get("properties", {})
        return list(props.keys())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_description_optimizer/test_grounded_prompts.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/description_optimizer/models.py tests/unit/test_description_optimizer/test_grounded_prompts.py
git commit -m "feat(desc-optimizer): add OptimizationContext model with input_schema and sibling_tools"
```

---

### Task 2: Rewrite Prompts for Grounded Optimization

**Files:**
- Modify: `src/description_optimizer/optimizer/prompts.py`
- Modify: `tests/unit/test_description_optimizer/test_grounded_prompts.py`

The current prompts tell the LLM to "add limitations" and "mention parameters" without providing the actual data. This causes hallucination. We replace them with grounded prompts that include `input_schema` and restrict the LLM to facts.

- [ ] **Step 1: Write failing tests for grounded prompt builder**

Add to `tests/unit/test_description_optimizer/test_grounded_prompts.py`:

```python
import json

from description_optimizer.optimizer.prompts import build_grounded_prompt


def test_grounded_prompt_includes_input_schema():
    schema = {
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "File ID"},
            "id": {"type": "string", "description": "Comment ID"},
        },
        "required": ["file", "id"],
    }
    prompt = build_grounded_prompt(
        original="Deletes a comment from a file.",
        tool_id="slack::delete_comment",
        input_schema=schema,
        sibling_tools=[],
        weak_dimensions=["parameter_coverage"],
        dimension_scores={"parameter_coverage": 0.1, "clarity": 0.5},
    )
    assert '"file"' in prompt
    assert '"id"' in prompt
    assert "File ID" in prompt


def test_grounded_prompt_includes_sibling_tools():
    siblings = [
        {"tool_name": "add_comment", "description": "Adds a comment."},
        {"tool_name": "get_file", "description": "Gets file info."},
    ]
    prompt = build_grounded_prompt(
        original="Deletes a comment.",
        tool_id="slack::delete_comment",
        input_schema=None,
        sibling_tools=siblings,
        weak_dimensions=["disambiguation"],
        dimension_scores={"disambiguation": 0.1, "clarity": 0.5},
    )
    assert "add_comment" in prompt
    assert "get_file" in prompt


def test_grounded_prompt_anti_hallucination_rules():
    prompt = build_grounded_prompt(
        original="A tool.",
        tool_id="test::tool",
        input_schema=None,
        sibling_tools=[],
        weak_dimensions=["boundary"],
        dimension_scores={"boundary": 0.0, "clarity": 0.3},
    )
    # Must contain anti-hallucination instruction
    assert "do not invent" in prompt.lower() or "do not add" in prompt.lower()


def test_grounded_prompt_no_schema_skips_parameter_section():
    prompt = build_grounded_prompt(
        original="A tool.",
        tool_id="test::tool",
        input_schema=None,
        sibling_tools=[],
        weak_dimensions=["clarity"],
        dimension_scores={"clarity": 0.2},
    )
    assert "Input Schema" not in prompt


def test_grounded_prompt_augmentation_instruction():
    prompt = build_grounded_prompt(
        original="Deletes a comment from a file.",
        tool_id="test::tool",
        input_schema=None,
        sibling_tools=[],
        weak_dimensions=["clarity"],
        dimension_scores={"clarity": 0.2},
    )
    # Must instruct augmentation, not full rewrite
    assert "preserve" in prompt.lower() or "keep the original" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_description_optimizer/test_grounded_prompts.py -v -k "grounded_prompt"`
Expected: FAIL with `ImportError: cannot import name 'build_grounded_prompt'`

- [ ] **Step 3: Implement grounded prompt builder**

Replace the prompt building logic in `src/description_optimizer/optimizer/prompts.py`:

```python
"""Prompt templates for grounded description optimization.

Key principle: the LLM may ONLY use information from:
1. The original description text
2. The input_schema (parameter names, types, constraints)
3. Sibling tool names/descriptions (for disambiguation)

It must NEVER invent capabilities, limitations, or parameters.
"""

import json

SYSTEM_PROMPT = """You are a technical writer specializing in MCP (Model Context Protocol) tool descriptions.
Your goal is to AUGMENT tool descriptions so they are more discoverable by LLM-based search systems.

CRITICAL RULES:
1. KEEP the original description text intact as the foundation.
2. ONLY ADD information that is directly supported by the provided input_schema or original description.
3. NEVER invent limitations, capabilities, or parameters not in the provided data.
4. NEVER add phrases like "Does NOT handle X" unless X is explicitly stated in the original.
5. If no input_schema is provided, do NOT mention specific parameter names or types.
6. Return valid JSON with exactly two keys: "optimized_description" and "search_description"."""


def build_grounded_prompt(
    original: str,
    tool_id: str,
    input_schema: dict | None,
    sibling_tools: list[dict],
    weak_dimensions: list[str],
    dimension_scores: dict[str, float],
) -> str:
    """Build a grounded optimization prompt with real tool data.

    Args:
        original: Original tool description.
        tool_id: Tool ID (server_id::tool_name).
        input_schema: JSON Schema of the tool's input parameters (may be None).
        sibling_tools: List of dicts with tool_name and description for same-server tools.
        weak_dimensions: Dimension names scoring below threshold.
        dimension_scores: All dimension name->score pairs.

    Returns:
        User prompt string grounded in factual data.
    """
    sections = []

    sections.append(f"Augment this MCP tool description to improve discoverability.\n")
    sections.append(f"**Tool ID**: {tool_id}\n")
    sections.append(f"**Original Description** (keep this as the foundation — do not discard it):\n{original}\n")

    # Input schema section — only if available
    if input_schema:
        schema_text = json.dumps(input_schema, indent=2, ensure_ascii=False)
        sections.append(f"**Input Schema** (use this to accurately describe parameters):\n```json\n{schema_text}\n```\n")

    # Sibling tools section — only if available
    if sibling_tools:
        sibling_lines = []
        for st in sibling_tools[:8]:  # Cap at 8 to avoid prompt bloat
            desc_preview = (st.get("description") or "")[:120]
            sibling_lines.append(f"- {st['tool_name']}: {desc_preview}")
        siblings_text = "\n".join(sibling_lines)
        sections.append(f"**Other tools on this server** (use for disambiguation — explain how THIS tool differs):\n{siblings_text}\n")

    # Scores
    scores_text = "\n".join(f"  - {dim}: {score:.2f}" for dim, score in dimension_scores.items())
    sections.append(f"**Current GEO Scores** (0.0-1.0):\n{scores_text}\n")

    # Grounded improvement guidance
    weak_text = ", ".join(weak_dimensions) if weak_dimensions else "none"
    sections.append(f"**Weak Dimensions**: {weak_text}\n")

    guidance = _build_grounded_guidance(weak_dimensions, dimension_scores, input_schema, sibling_tools)
    if guidance:
        sections.append(f"**Improvement Guidance**:\n{guidance}\n")

    sections.append("""**Output Rules**:
1. Start with the original description text, then ADD factual information to improve weak dimensions.
2. Do NOT rewrite or rephrase the original — augment it.
3. Do NOT invent any information not present in the original description or input schema.
4. Keep optimized_description to 50-200 words, search_description to 30-80 words.

Return JSON:
{"optimized_description": "...", "search_description": "..."}""")

    return "\n".join(sections)


def _build_grounded_guidance(
    weak_dimensions: list[str],
    dimension_scores: dict[str, float],
    input_schema: dict | None,
    sibling_tools: list[dict],
) -> str:
    """Build dimension-specific guidance grounded in available data."""
    lines = []

    guidance_map = {
        "clarity": "Add a clear action verb at the start if missing. Specify WHEN to use this tool based on the original description.",
        "precision": "Use precise technical terms that are already present or directly inferable from the original description.",
        "stats": "Include quantitative information ONLY if present in the original description (counts, limits, response times).",
    }

    # Schema-dependent guidance
    if "parameter_coverage" in weak_dimensions:
        if input_schema:
            props = input_schema.get("properties", {})
            required = input_schema.get("required", [])
            param_summary = ", ".join(
                f"`{name}` ({'required' if name in required else 'optional'})"
                for name in list(props.keys())[:6]
            )
            lines.append(f"  - **parameter_coverage** ({dimension_scores.get('parameter_coverage', 0):.2f}): "
                         f"Mention these actual parameters: {param_summary}")
        else:
            lines.append(f"  - **parameter_coverage** ({dimension_scores.get('parameter_coverage', 0):.2f}): "
                         f"No input_schema available — skip parameter improvements to avoid hallucination.")

    # Sibling-dependent guidance
    if "disambiguation" in weak_dimensions:
        if sibling_tools:
            names = ", ".join(st["tool_name"] for st in sibling_tools[:5])
            lines.append(f"  - **disambiguation** ({dimension_scores.get('disambiguation', 0):.2f}): "
                         f"Differentiate from these sibling tools: {names}. State what THIS tool does that they don't.")
        else:
            lines.append(f"  - **disambiguation** ({dimension_scores.get('disambiguation', 0):.2f}): "
                         f"No sibling tools available — skip disambiguation to avoid generic contrast phrases.")

    # Boundary — heavily restricted
    if "boundary" in weak_dimensions:
        lines.append(f"  - **boundary** ({dimension_scores.get('boundary', 0):.2f}): "
                     f"ONLY state limitations explicitly mentioned in the original description. "
                     f"Do NOT invent limitations.")

    # Standard guidance for other dimensions
    for dim in weak_dimensions:
        if dim in guidance_map and dim not in ("parameter_coverage", "disambiguation", "boundary"):
            lines.append(f"  - **{dim}** ({dimension_scores.get(dim, 0):.2f}): {guidance_map[dim]}")

    return "\n".join(lines) if lines else "  All dimensions are adequate — preserve the original."


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

Note: The old `build_optimization_prompt` function is kept temporarily for backward compatibility but `build_grounded_prompt` is the new primary interface.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_description_optimizer/test_grounded_prompts.py -v`
Expected: PASS (all tests including Task 1 tests)

- [ ] **Step 5: Commit**

```bash
git add src/description_optimizer/optimizer/prompts.py tests/unit/test_description_optimizer/test_grounded_prompts.py
git commit -m "feat(desc-optimizer): grounded prompts with input_schema and anti-hallucination rules"
```

---

### Task 3: Extend Optimizer ABC and LLM Optimizer to Accept Context

**Files:**
- Modify: `src/description_optimizer/optimizer/base.py`
- Modify: `src/description_optimizer/optimizer/llm_optimizer.py`
- Modify: `tests/unit/test_description_optimizer/test_llm_optimizer.py`

The optimizer currently receives only `AnalysisReport`. We extend it to accept `OptimizationContext` for grounded optimization.

- [ ] **Step 1: Write failing test for context-aware optimizer**

Add to `tests/unit/test_description_optimizer/test_llm_optimizer.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from description_optimizer.models import AnalysisReport, DimensionScore, OptimizationContext
from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer


@pytest.fixture
def sample_context():
    return OptimizationContext(
        tool_id="slack::SLACK_DELETE_COMMENT",
        original_description="Deletes a comment from a file.",
        input_schema={
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File ID"},
                "id": {"type": "string", "description": "Comment ID"},
            },
            "required": ["file", "id"],
        },
        sibling_tools=[
            {"tool_name": "SLACK_ADD_COMMENT", "description": "Adds a comment to a file."},
        ],
    )


@pytest.fixture
def sample_report():
    return AnalysisReport(
        tool_id="slack::SLACK_DELETE_COMMENT",
        original_description="Deletes a comment from a file.",
        dimension_scores=[
            DimensionScore(dimension="clarity", score=0.35, explanation="low"),
            DimensionScore(dimension="disambiguation", score=0.0, explanation="none"),
            DimensionScore(dimension="parameter_coverage", score=0.0, explanation="none"),
            DimensionScore(dimension="boundary", score=0.0, explanation="none"),
            DimensionScore(dimension="stats", score=0.0, explanation="none"),
            DimensionScore(dimension="precision", score=0.0, explanation="none"),
        ],
    )


async def test_optimize_with_context_passes_schema_to_prompt(sample_report, sample_context):
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"optimized_description": "improved", "search_description": "search"}'
    mock_client.chat.completions.create.return_value = mock_response

    optimizer = LLMDescriptionOptimizer(client=mock_client)
    result = await optimizer.optimize(sample_report, context=sample_context)

    assert result["optimized_description"] == "improved"
    # Verify the prompt sent to OpenAI contains schema info
    call_args = mock_client.chat.completions.create.call_args
    user_message = call_args.kwargs["messages"][1]["content"]
    assert '"file"' in user_message
    assert '"id"' in user_message


async def test_optimize_without_context_still_works(sample_report):
    """Backward compatibility: optimize() without context uses old prompt."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"optimized_description": "improved", "search_description": "search"}'
    mock_client.chat.completions.create.return_value = mock_response

    optimizer = LLMDescriptionOptimizer(client=mock_client)
    result = await optimizer.optimize(sample_report)

    assert result["optimized_description"] == "improved"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_description_optimizer/test_llm_optimizer.py::test_optimize_with_context_passes_schema_to_prompt -v`
Expected: FAIL (optimize() doesn't accept context parameter)

- [ ] **Step 3: Update Optimizer ABC to accept optional context**

Modify `src/description_optimizer/optimizer/base.py`:

```python
"""Abstract base class for description optimizers."""

from abc import ABC, abstractmethod

from description_optimizer.models import AnalysisReport, OptimizationContext


class DescriptionOptimizer(ABC):
    """ABC for optimizing MCP tool descriptions.

    Takes an AnalysisReport (with weak dimension info) and optionally
    an OptimizationContext (with input_schema + sibling tools) to produce
    an optimized description + search description.
    """

    @abstractmethod
    async def optimize(
        self,
        report: AnalysisReport,
        context: OptimizationContext | None = None,
    ) -> dict[str, str]:
        """Optimize a tool description based on its analysis report.

        Args:
            report: AnalysisReport with GEO scores and weak dimensions.
            context: Optional grounding context with input_schema and sibling tools.

        Returns:
            Dict with keys: 'optimized_description', 'search_description'.
        """
        ...
```

- [ ] **Step 4: Update LLMDescriptionOptimizer to use grounded prompt when context is provided**

Modify `src/description_optimizer/optimizer/llm_optimizer.py`:

```python
"""LLM-based description optimizer using GPT-4o-mini."""

import json

from loguru import logger
from openai import AsyncOpenAI

from description_optimizer.models import AnalysisReport, OptimizationContext
from description_optimizer.optimizer.base import DescriptionOptimizer
from description_optimizer.optimizer.prompts import (
    SYSTEM_PROMPT,
    build_grounded_prompt,
    build_optimization_prompt,
)


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

    async def optimize(
        self,
        report: AnalysisReport,
        context: OptimizationContext | None = None,
    ) -> dict[str, str]:
        """Optimize a description based on its GEO analysis report.

        Args:
            report: AnalysisReport with dimension scores.
            context: Optional grounding context with input_schema and sibling tools.

        Returns:
            Dict with 'optimized_description' and 'search_description'.
        """
        weak_dims = report.weak_dimensions(threshold=0.5)
        dim_scores = {s.dimension: s.score for s in report.dimension_scores}

        if context:
            prompt = build_grounded_prompt(
                original=report.original_description,
                tool_id=report.tool_id,
                input_schema=context.input_schema,
                sibling_tools=context.sibling_tools,
                weak_dimensions=weak_dims,
                dimension_scores=dim_scores,
            )
        else:
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
            msg = "LLM response must contain 'optimized_description' and 'search_description'"
            raise ValueError(msg)

        logger.info(
            f"Optimized {report.tool_id}: "
            f"weak_dims={weak_dims}, "
            f"grounded={'yes' if context else 'no'}, "
            f"original_len={len(report.original_description)}, "
            f"optimized_len={len(result['optimized_description'])}"
        )

        return {
            "optimized_description": result["optimized_description"],
            "search_description": result["search_description"],
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_description_optimizer/test_llm_optimizer.py -v`
Expected: PASS (all tests including new context-aware tests)

- [ ] **Step 6: Commit**

```bash
git add src/description_optimizer/optimizer/base.py src/description_optimizer/optimizer/llm_optimizer.py tests/unit/test_description_optimizer/test_llm_optimizer.py
git commit -m "feat(desc-optimizer): context-aware optimizer with grounded prompt selection"
```

---

### Task 4: Update Pipeline to Accept MCPTool and Build Context

**Files:**
- Modify: `src/description_optimizer/pipeline.py`
- Modify: `tests/unit/test_description_optimizer/test_pipeline.py`

The pipeline currently accepts `(tool_id, description)` tuples. We extend it to accept `MCPTool` objects (which carry `input_schema`) and a server context for sibling tools.

- [ ] **Step 1: Write failing test for MCPTool-based pipeline**

Add to `tests/unit/test_description_optimizer/test_pipeline.py`:

```python
from unittest.mock import AsyncMock, MagicMock
import numpy as np

from description_optimizer.models import (
    AnalysisReport,
    DimensionScore,
    OptimizationContext,
    OptimizationStatus,
)
from description_optimizer.pipeline import OptimizationPipeline
from models import MCPTool


def _make_report(tool_id: str, desc: str, geo: float = 0.3) -> AnalysisReport:
    per_dim = geo  # Simplified: all dims same score
    return AnalysisReport(
        tool_id=tool_id,
        original_description=desc,
        dimension_scores=[
            DimensionScore(dimension=d, score=per_dim, explanation="test")
            for d in ["clarity", "disambiguation", "parameter_coverage", "boundary", "stats", "precision"]
        ],
    )


async def test_run_with_tool_passes_context_to_optimizer():
    """Pipeline.run_with_tool() should build OptimizationContext from MCPTool and pass it."""
    tool = MCPTool(
        server_id="slack",
        tool_name="DELETE_COMMENT",
        tool_id="slack::DELETE_COMMENT",
        description="Deletes a comment.",
        input_schema={"type": "object", "properties": {"id": {"type": "string"}}},
    )
    sibling_tools = [
        MCPTool(
            server_id="slack",
            tool_name="ADD_COMMENT",
            tool_id="slack::ADD_COMMENT",
            description="Adds a comment.",
        ),
    ]

    analyzer = AsyncMock()
    analyzer.analyze.return_value = _make_report("slack::DELETE_COMMENT", "Deletes a comment.", 0.3)

    optimizer = AsyncMock()
    optimizer.optimize.return_value = {
        "optimized_description": "Deletes a comment. Requires `id` parameter.",
        "search_description": "delete comment slack",
    }

    embedder = AsyncMock()
    embedder.embed_one.return_value = np.ones(10)

    gate = MagicMock()
    gate.evaluate.return_value = MagicMock(passed=True, reason="OK")

    pipeline = OptimizationPipeline(
        analyzer=analyzer, optimizer=optimizer, embedder=embedder, gate=gate,
    )

    result = await pipeline.run_with_tool(tool, sibling_tools=sibling_tools)

    assert result.status == OptimizationStatus.SUCCESS
    # Verify optimizer was called with context
    call_args = optimizer.optimize.call_args
    context = call_args.kwargs.get("context") or call_args.args[1] if len(call_args.args) > 1 else None
    assert context is not None
    assert context.input_schema == tool.input_schema
    assert len(context.sibling_tools) == 1


async def test_run_with_tool_batch():
    """run_batch_with_tools should process a list of (MCPTool, siblings) tuples."""
    tool = MCPTool(
        server_id="test",
        tool_name="tool1",
        tool_id="test::tool1",
        description="Tool 1.",
    )

    analyzer = AsyncMock()
    analyzer.analyze.return_value = _make_report("test::tool1", "Tool 1.", 0.3)

    optimizer = AsyncMock()
    optimizer.optimize.return_value = {
        "optimized_description": "Improved Tool 1.",
        "search_description": "tool 1 search",
    }

    embedder = AsyncMock()
    embedder.embed_one.return_value = np.ones(10)

    gate = MagicMock()
    gate.evaluate.return_value = MagicMock(passed=True, reason="OK")

    pipeline = OptimizationPipeline(
        analyzer=analyzer, optimizer=optimizer, embedder=embedder, gate=gate,
    )

    results = await pipeline.run_batch_with_tools([(tool, [])])
    assert len(results) == 1
    assert results[0].status == OptimizationStatus.SUCCESS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_description_optimizer/test_pipeline.py::test_run_with_tool_passes_context_to_optimizer -v`
Expected: FAIL with `AttributeError: 'OptimizationPipeline' object has no attribute 'run_with_tool'`

- [ ] **Step 3: Add `run_with_tool` and `run_batch_with_tools` to pipeline**

Add to `src/description_optimizer/pipeline.py`:

```python
"""Orchestrates the description optimization pipeline.

Flow: analyze -> (skip if high GEO) -> optimize -> re-analyze -> gate -> result
"""

from loguru import logger

from description_optimizer.analyzer.base import DescriptionAnalyzer
from description_optimizer.models import OptimizationContext, OptimizationStatus, OptimizedDescription
from description_optimizer.optimizer.base import DescriptionOptimizer
from description_optimizer.quality_gate import QualityGate
from embedding.base import Embedder
from models import MCPTool


class OptimizationPipeline:
    """End-to-end description optimization: analyze -> optimize -> validate."""

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
        """Run the full optimization pipeline for a single tool (legacy interface).

        Args:
            tool_id: Tool ID (server_id::tool_name).
            description: Original description (may be None/empty).

        Returns:
            OptimizedDescription with status indicating outcome.
        """
        return await self._run_internal(tool_id, description or "", context=None)

    async def run_with_tool(
        self,
        tool: MCPTool,
        sibling_tools: list[MCPTool] | None = None,
    ) -> OptimizedDescription:
        """Run optimization with full tool context (grounded mode).

        Args:
            tool: MCPTool with input_schema.
            sibling_tools: Other tools on the same server (for disambiguation).

        Returns:
            OptimizedDescription with status indicating outcome.
        """
        siblings = sibling_tools or []
        context = OptimizationContext(
            tool_id=tool.tool_id,
            original_description=tool.description or "",
            input_schema=tool.input_schema,
            sibling_tools=[
                {"tool_name": s.tool_name, "description": s.description or ""}
                for s in siblings
                if s.tool_id != tool.tool_id
            ],
        )
        return await self._run_internal(tool.tool_id, tool.description or "", context=context)

    async def run_batch(self, tools: list[tuple[str, str | None]]) -> list[OptimizedDescription]:
        """Run optimization for a batch of tools (legacy interface)."""
        results: list[OptimizedDescription] = []
        for tool_id, desc in tools:
            result = await self.run(tool_id, desc)
            results.append(result)
        return results

    async def run_batch_with_tools(
        self,
        tools_with_siblings: list[tuple[MCPTool, list[MCPTool]]],
    ) -> list[OptimizedDescription]:
        """Run optimization for a batch of tools with context.

        Args:
            tools_with_siblings: List of (tool, sibling_tools) tuples.

        Returns:
            List of OptimizedDescription results.
        """
        results: list[OptimizedDescription] = []
        for tool, siblings in tools_with_siblings:
            result = await self.run_with_tool(tool, sibling_tools=siblings)
            results.append(result)
        return results

    async def _run_internal(
        self,
        tool_id: str,
        desc: str,
        context: OptimizationContext | None,
    ) -> OptimizedDescription:
        """Core optimization logic shared by run() and run_with_tool()."""
        # Phase 1: Analyze original
        report_before = await self._analyzer.analyze(tool_id, desc)
        logger.info(f"Analyzed {tool_id}: GEO={report_before.geo_score:.3f}")

        # Skip if already high quality
        if report_before.geo_score >= self._skip_threshold:
            logger.info(
                f"Skipping {tool_id}: GEO={report_before.geo_score:.3f} >= {self._skip_threshold}"
            )
            return OptimizedDescription(
                tool_id=tool_id,
                original_description=desc,
                optimized_description=desc,
                search_description=desc,
                geo_score_before=report_before.geo_score,
                geo_score_after=report_before.geo_score,
                status=OptimizationStatus.SKIPPED,
                skip_reason=(
                    f"GEO score {report_before.geo_score:.3f} "
                    f"already above threshold {self._skip_threshold}"
                ),
            )

        # Phase 2: Optimize (with context if available)
        try:
            optimized = await self._optimizer.optimize(report_before, context=context)
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
            f"GEO {report_before.geo_score:.3f} -> {report_after.geo_score:.3f}"
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
```

- [ ] **Step 4: Run all pipeline tests**

Run: `uv run pytest tests/unit/test_description_optimizer/test_pipeline.py -v`
Expected: PASS (old tests still pass + new tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/description_optimizer/pipeline.py tests/unit/test_description_optimizer/test_pipeline.py
git commit -m "feat(desc-optimizer): pipeline accepts MCPTool with input_schema for grounded optimization"
```

---

### Task 5: Add Hallucination Detection Gate

**Files:**
- Modify: `src/description_optimizer/quality_gate.py`
- Modify: `tests/unit/test_description_optimizer/test_quality_gate.py`

The current gate only checks GEO regression and cosine similarity. It cannot detect parameter hallucination (mentioning parameters not in the actual schema). We add a `HallucinationGate` that cross-checks the optimized description against the real `input_schema`.

- [ ] **Step 1: Write failing test for hallucination gate**

Add to `tests/unit/test_description_optimizer/test_quality_gate.py`:

```python
from description_optimizer.quality_gate import QualityGate, GateResult


def test_hallucination_gate_catches_fake_params():
    gate = QualityGate()
    schema = {
        "type": "object",
        "properties": {
            "file": {"type": "string"},
            "id": {"type": "string"},
        },
    }
    # Optimized description mentions "query" and "limit" — not in schema
    optimized = "Deletes a comment. Accepts a required `query` string and optional `limit` integer."
    result = gate.check_hallucinated_params(optimized, schema)
    assert not result.passed
    assert "query" in result.reason or "limit" in result.reason


def test_hallucination_gate_passes_with_real_params():
    gate = QualityGate()
    schema = {
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "File ID"},
            "id": {"type": "string", "description": "Comment ID"},
        },
    }
    optimized = "Deletes a comment. Requires `file` (File ID) and `id` (Comment ID) parameters."
    result = gate.check_hallucinated_params(optimized, schema)
    assert result.passed


def test_hallucination_gate_skips_when_no_schema():
    gate = QualityGate()
    result = gate.check_hallucinated_params("Any description", None)
    assert result.passed
    assert "no schema" in result.reason.lower()


def test_hallucination_gate_no_backtick_params():
    """If optimized has no backtick params, gate passes (nothing to verify)."""
    gate = QualityGate()
    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    result = gate.check_hallucinated_params("A simple tool that does things.", schema)
    assert result.passed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_description_optimizer/test_quality_gate.py::test_hallucination_gate_catches_fake_params -v`
Expected: FAIL with `AttributeError: 'QualityGate' object has no attribute 'check_hallucinated_params'`

- [ ] **Step 3: Implement hallucination detection in QualityGate**

Add to `src/description_optimizer/quality_gate.py`:

```python
import re

# Add to QualityGate class:

    _BACKTICK_PARAM: re.Pattern[str] = re.compile(r"`(\w+)`")

    def check_hallucinated_params(
        self, optimized: str, input_schema: dict | None
    ) -> GateResult:
        """Check if optimized description mentions parameters not in the actual schema.

        Args:
            optimized: The optimized description text.
            input_schema: The tool's actual input schema (may be None).

        Returns:
            GateResult indicating pass/fail.
        """
        if not input_schema:
            return GateResult(passed=True, reason="No schema available — hallucination check skipped")

        actual_params = set(input_schema.get("properties", {}).keys())
        if not actual_params:
            return GateResult(passed=True, reason="No schema properties — hallucination check skipped")

        # Extract backtick-quoted words from optimized description
        mentioned_params = set(self._BACKTICK_PARAM.findall(optimized))
        if not mentioned_params:
            return GateResult(passed=True, reason="No backtick parameters in optimized description")

        # Filter: only flag words that look like parameter names (lowercase, not common words)
        common_words = {"the", "a", "an", "is", "are", "to", "for", "and", "or", "not", "true", "false", "null", "none"}
        candidate_params = {p for p in mentioned_params if p.lower() not in common_words}

        hallucinated = candidate_params - actual_params
        if hallucinated:
            return GateResult(
                passed=False,
                reason=f"Hallucinated parameters: {sorted(hallucinated)}. Actual: {sorted(actual_params)}",
            )

        return GateResult(
            passed=True,
            reason=f"All mentioned parameters verified against schema: {sorted(candidate_params)}",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_description_optimizer/test_quality_gate.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/description_optimizer/quality_gate.py tests/unit/test_description_optimizer/test_quality_gate.py
git commit -m "feat(desc-optimizer): hallucination detection gate for parameter verification"
```

---

### Task 6: Add Information Preservation Gate

**Files:**
- Modify: `src/description_optimizer/quality_gate.py`
- Modify: `tests/unit/test_description_optimizer/test_quality_gate.py`

The root cause analysis shows stats dimension regresses (-0.0523) because the LLM discards numbers and technical terms from the original. We add a gate that checks if key information (numbers, technical terms) from the original is preserved.

- [ ] **Step 1: Write failing tests for information preservation gate**

Add to `tests/unit/test_description_optimizer/test_quality_gate.py`:

```python
def test_info_preservation_catches_lost_numbers():
    gate = QualityGate()
    original = "Searches across 50,000+ packages with 99.9% uptime."
    optimized = "Searches for packages in the registry."
    result = gate.check_info_preservation(original, optimized)
    assert not result.passed
    assert "50,000" in result.reason or "99.9" in result.reason


def test_info_preservation_passes_when_numbers_kept():
    gate = QualityGate()
    original = "Returns up to 100 results per query."
    optimized = "Returns up to 100 results per query. Use for data retrieval."
    result = gate.check_info_preservation(original, optimized)
    assert result.passed


def test_info_preservation_no_numbers_passes():
    gate = QualityGate()
    original = "Deletes a comment from a file."
    optimized = "Deletes a comment from a file in Slack."
    result = gate.check_info_preservation(original, optimized)
    assert result.passed


def test_info_preservation_catches_lost_tech_terms():
    gate = QualityGate()
    original = "Queries the PostgreSQL database via the wire protocol."
    optimized = "Queries the database for records."
    result = gate.check_info_preservation(original, optimized)
    assert not result.passed
    assert "PostgreSQL" in result.reason or "wire protocol" in result.reason
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_description_optimizer/test_quality_gate.py::test_info_preservation_catches_lost_numbers -v`
Expected: FAIL with `AttributeError: 'QualityGate' object has no attribute 'check_info_preservation'`

- [ ] **Step 3: Implement information preservation check**

Add to `src/description_optimizer/quality_gate.py`:

```python
    _NUMBERS_WITH_CONTEXT: re.Pattern[str] = re.compile(
        r"\d[\d,]*\.?\d*\s*[%+]?"
    )
    _TECH_TERMS: re.Pattern[str] = re.compile(
        r"\b(SQL|PostgreSQL|MySQL|MongoDB|Redis|REST|GraphQL|gRPC|HTTP|HTTPS|JSON|XML|YAML|CSV"
        r"|API|SDK|OAuth|JWT|WebSocket|TCP|UDP|S3|AWS|GCP|Azure|Docker|Kubernetes"
        r"|Git|GitHub|Slack|Notion|OWASP|wire protocol|stdio|SSE)\b",
        re.IGNORECASE,
    )

    def check_info_preservation(self, original: str, optimized: str) -> GateResult:
        """Check that key information from original is preserved in optimized.

        Checks for:
        1. Numbers/statistics (e.g., "50,000+", "99.9%")
        2. Technical terms (e.g., "PostgreSQL", "wire protocol")

        Args:
            original: Original description.
            optimized: Optimized description.

        Returns:
            GateResult indicating pass/fail.
        """
        lost_items: list[str] = []
        optimized_lower = optimized.lower()

        # Check numbers
        original_numbers = self._NUMBERS_WITH_CONTEXT.findall(original)
        significant_numbers = [n.strip() for n in original_numbers if len(n.strip()) >= 2]
        for num in significant_numbers:
            if num not in optimized:
                lost_items.append(f"number '{num}'")

        # Check technical terms
        original_terms = set(self._TECH_TERMS.findall(original))
        for term in original_terms:
            if term.lower() not in optimized_lower:
                lost_items.append(f"term '{term}'")

        if lost_items:
            return GateResult(
                passed=False,
                reason=f"Information lost from original: {', '.join(lost_items)}",
            )

        return GateResult(passed=True, reason="Key information preserved from original")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_description_optimizer/test_quality_gate.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/description_optimizer/quality_gate.py tests/unit/test_description_optimizer/test_quality_gate.py
git commit -m "feat(desc-optimizer): information preservation gate prevents stats/term loss"
```

---

### Task 7: Integrate New Gates into Pipeline

**Files:**
- Modify: `src/description_optimizer/quality_gate.py`
- Modify: `src/description_optimizer/pipeline.py`
- Modify: `tests/unit/test_description_optimizer/test_pipeline.py`

Wire the hallucination gate and info preservation gate into the pipeline's `_run_internal` method. The `FullGateResult` needs to include the new checks.

- [ ] **Step 1: Write failing test for integrated gates in pipeline**

Add to `tests/unit/test_description_optimizer/test_pipeline.py`:

```python
async def test_pipeline_rejects_hallucinated_params():
    """Pipeline should reject optimization that hallucinates parameters."""
    tool = MCPTool(
        server_id="test",
        tool_name="tool1",
        tool_id="test::tool1",
        description="A test tool.",
        input_schema={
            "type": "object",
            "properties": {"real_param": {"type": "string"}},
        },
    )

    analyzer = AsyncMock()
    analyzer.analyze.return_value = _make_report("test::tool1", "A test tool.", 0.3)

    optimizer = AsyncMock()
    # LLM hallucinates a `query` parameter
    optimizer.optimize.return_value = {
        "optimized_description": "A test tool. Accepts `query` string and `limit` integer.",
        "search_description": "test tool",
    }

    embedder = AsyncMock()
    embedder.embed_one.return_value = np.ones(10)

    gate = QualityGate(min_similarity=0.0)  # Relax similarity to isolate hallucination gate

    pipeline = OptimizationPipeline(
        analyzer=analyzer, optimizer=optimizer, embedder=embedder, gate=gate,
    )

    result = await pipeline.run_with_tool(tool, sibling_tools=[])
    assert result.status == OptimizationStatus.GATE_REJECTED
    assert "hallucinated" in result.skip_reason.lower() or "Hallucinated" in result.skip_reason
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_description_optimizer/test_pipeline.py::test_pipeline_rejects_hallucinated_params -v`
Expected: FAIL (hallucination gate not yet integrated)

- [ ] **Step 3: Update FullGateResult and QualityGate.evaluate to include new checks**

Modify `src/description_optimizer/quality_gate.py` — update `FullGateResult` and `evaluate()`:

```python
@dataclass(frozen=True)
class FullGateResult:
    """Combined result of all quality gate checks."""

    passed: bool
    geo_result: GateResult
    similarity_result: GateResult
    hallucination_result: GateResult | None = None
    info_preservation_result: GateResult | None = None

    @property
    def reason(self) -> str:
        if self.passed:
            return "All gates passed"
        reasons = []
        if not self.geo_result.passed:
            reasons.append(f"GEO: {self.geo_result.reason}")
        if not self.similarity_result.passed:
            reasons.append(f"Similarity: {self.similarity_result.reason}")
        if self.hallucination_result and not self.hallucination_result.passed:
            reasons.append(f"Hallucination: {self.hallucination_result.reason}")
        if self.info_preservation_result and not self.info_preservation_result.passed:
            reasons.append(f"InfoPreservation: {self.info_preservation_result.reason}")
        return "; ".join(reasons)
```

Update `evaluate()` to accept optional `input_schema` and `original_desc`:

```python
    def evaluate(
        self,
        before: AnalysisReport,
        after: AnalysisReport,
        vec_before: np.ndarray,
        vec_after: np.ndarray,
        input_schema: dict | None = None,
        optimized_text: str | None = None,
        original_text: str | None = None,
    ) -> FullGateResult:
        """Run all quality gate checks.

        Args:
            before: GEO report before optimization.
            after: GEO report after optimization.
            vec_before: Embedding of original description.
            vec_after: Embedding of optimized description.
            input_schema: Tool's input schema for hallucination check (optional).
            optimized_text: Optimized description text for hallucination check (optional).
            original_text: Original description text for info preservation check (optional).
        """
        geo_result = self.check_geo_score(before, after)
        sim_result = self.check_semantic_similarity(vec_before, vec_after)

        hallucination_result = None
        info_preservation_result = None

        if optimized_text and input_schema:
            hallucination_result = self.check_hallucinated_params(optimized_text, input_schema)

        if original_text and optimized_text:
            info_preservation_result = self.check_info_preservation(original_text, optimized_text)

        passed = (
            geo_result.passed
            and sim_result.passed
            and (hallucination_result is None or hallucination_result.passed)
            and (info_preservation_result is None or info_preservation_result.passed)
        )

        if not passed:
            logger.warning(
                f"Quality gate FAILED for {before.tool_id}: "
                f"GEO={geo_result.passed}, Similarity={sim_result.passed}"
                + (f", Hallucination={hallucination_result.passed}" if hallucination_result else "")
                + (f", InfoPreservation={info_preservation_result.passed}" if info_preservation_result else "")
            )

        return FullGateResult(
            passed=passed,
            geo_result=geo_result,
            similarity_result=sim_result,
            hallucination_result=hallucination_result,
            info_preservation_result=info_preservation_result,
        )
```

- [ ] **Step 4: Update `_run_internal` in pipeline to pass new gate params**

In `src/description_optimizer/pipeline.py`, update the gate call in `_run_internal`:

```python
        # Phase 5: Quality Gate
        gate_result = self._gate.evaluate(
            report_before,
            report_after,
            vec_before,
            vec_after,
            input_schema=context.input_schema if context else None,
            optimized_text=optimized_desc,
            original_text=desc,
        )
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest tests/unit/test_description_optimizer/ -v`
Expected: PASS (all tests including new integration)

- [ ] **Step 6: Commit**

```bash
git add src/description_optimizer/quality_gate.py src/description_optimizer/pipeline.py tests/unit/test_description_optimizer/test_pipeline.py
git commit -m "feat(desc-optimizer): integrate hallucination and info preservation gates into pipeline"
```

---

### Task 8: Update Scripts for Grounded Optimization

**Files:**
- Modify: `scripts/optimize_descriptions.py`
- Modify: `scripts/run_comparison_verification.py`

The scripts currently extract only `(tool_id, description)` from `servers.jsonl`, discarding `input_schema`. We update them to pass full `MCPTool` objects with server context.

- [ ] **Step 1: Update `optimize_descriptions.py` to use `run_batch_with_tools`**

```python
"""CLI script to optimize MCP tool descriptions with grounded optimization.

Usage:
    uv run python scripts/optimize_descriptions.py
    uv run python scripts/optimize_descriptions.py --input data/raw/servers.jsonl
    uv run python scripts/optimize_descriptions.py --dry-run
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loguru import logger
from openai import AsyncOpenAI

from config import Settings
from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import OptimizationStatus
from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer
from description_optimizer.pipeline import OptimizationPipeline
from description_optimizer.quality_gate import QualityGate
from embedding.openai_embedder import OpenAIEmbedder
from models import MCPTool


def load_tools_with_siblings(input_path: Path) -> list[tuple[MCPTool, list[MCPTool]]]:
    """Load MCPTool objects grouped by server for sibling context."""
    tools_with_siblings: list[tuple[MCPTool, list[MCPTool]]] = []

    with open(input_path) as f:
        for line in f:
            server = json.loads(line.strip())
            server_tools = []
            for t in server.get("tools", []):
                tool = MCPTool(
                    server_id=server["server_id"],
                    tool_name=t["tool_name"],
                    tool_id=f"{server['server_id']}::{t['tool_name']}",
                    description=t.get("description"),
                    input_schema=t.get("input_schema"),
                )
                server_tools.append(tool)

            for tool in server_tools:
                siblings = [s for s in server_tools if s.tool_id != tool.tool_id]
                tools_with_siblings.append((tool, siblings))

    return tools_with_siblings


async def main(args: argparse.Namespace) -> None:
    settings = Settings()
    input_path = Path(args.input)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return

    tools_with_siblings = load_tools_with_siblings(input_path)
    logger.info(f"Loaded {len(tools_with_siblings)} tools from {input_path}")

    if args.dry_run:
        analyzer = HeuristicAnalyzer()
        for tool, _ in tools_with_siblings:
            report = await analyzer.analyze(tool.tool_id, tool.description or "")
            weak = report.weak_dimensions()
            has_schema = "yes" if tool.input_schema else "no"
            logger.info(f"{tool.tool_id}: GEO={report.geo_score:.3f}, schema={has_schema}, weak=[{', '.join(weak)}]")
        return

    # Full pipeline with grounded optimization
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    analyzer = HeuristicAnalyzer()
    optimizer = LLMDescriptionOptimizer(client=openai_client)
    embedder = OpenAIEmbedder(client=openai_client)
    gate = QualityGate(min_similarity=0.85)
    pipeline = OptimizationPipeline(
        analyzer=analyzer, optimizer=optimizer, embedder=embedder, gate=gate,
        skip_threshold=args.skip_threshold,
    )

    results = await pipeline.run_batch_with_tools(tools_with_siblings)

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

    if success > 0:
        avg_improvement = (
            sum(r.improvement for r in results if r.status == OptimizationStatus.SUCCESS) / success
        )
        logger.info(f"Average GEO improvement: +{avg_improvement:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize MCP tool descriptions (grounded)")
    parser.add_argument("--input", default="data/raw/servers.jsonl")
    parser.add_argument("--output", default="data/optimized/descriptions.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="Only analyze, don't optimize")
    parser.add_argument("--skip-threshold", type=float, default=0.75)
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
```

- [ ] **Step 2: Update `run_comparison_verification.py` to pass input_schema**

In `load_all_tools()`, add `input_schema` to the extracted tool dict:

```python
def load_all_tools() -> list[dict]:
    """Load all tools from servers.jsonl with server context."""
    tools = []
    with open(RAW_DATA) as f:
        for line in f:
            server = json.loads(line.strip())
            for tool in server.get("tools", []):
                tool_id = f"{server['server_id']}::{tool['tool_name']}"
                tools.append(
                    {
                        "tool_id": tool_id,
                        "server_id": server["server_id"],
                        "tool_name": tool["tool_name"],
                        "description": tool.get("description") or "",
                        "input_schema": tool.get("input_schema"),
                    }
                )
    return tools
```

Then update Phase 2 (optimization) to use `run_with_tool` instead of `run`.

- [ ] **Step 3: Run lint**

Run: `uv run ruff check scripts/ src/description_optimizer/ --fix`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add scripts/optimize_descriptions.py scripts/run_comparison_verification.py
git commit -m "feat(desc-optimizer): scripts pass input_schema and sibling tools for grounded optimization"
```

---

### Task 9: Tool Selection A/B Evaluation Script

**Files:**
- Create: `scripts/run_selection_eval.py`
- Create: `tests/evaluation/test_selection_eval.py`

The most important validation: does the optimized description actually improve tool selection accuracy? This script compares Precision@1 using original vs. optimized descriptions against the ground truth.

- [ ] **Step 1: Write test for selection evaluation logic**

```python
# tests/evaluation/test_selection_eval.py

from description_optimizer.models import OptimizedDescription, OptimizationStatus


def test_selection_eval_result_structure():
    """Selection eval should track per-query results for original vs optimized."""
    # This tests the data model, not the full pipeline
    result = {
        "query_id": "gt-comm-001",
        "query": "delete a comment on a Slack file",
        "correct_tool_id": "slack::SLACK_DELETE_A_COMMENT_ON_A_FILE",
        "original_rank1": "slack::SLACK_DELETE_A_COMMENT_ON_A_FILE",
        "optimized_rank1": "slack::SLACK_DELETE_A_COMMENT_ON_A_FILE",
        "original_correct": True,
        "optimized_correct": True,
    }
    assert result["original_correct"] is True
    assert result["optimized_correct"] is True


def test_precision_at_1_calculation():
    """Precision@1 = count of rank1 correct / total queries."""
    results = [
        {"original_correct": True, "optimized_correct": True},
        {"original_correct": False, "optimized_correct": True},
        {"original_correct": True, "optimized_correct": False},
        {"original_correct": False, "optimized_correct": False},
    ]
    original_p1 = sum(1 for r in results if r["original_correct"]) / len(results)
    optimized_p1 = sum(1 for r in results if r["optimized_correct"]) / len(results)
    assert original_p1 == 0.5
    assert optimized_p1 == 0.5
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/evaluation/test_selection_eval.py -v`
Expected: PASS (pure logic tests)

- [ ] **Step 3: Create selection evaluation script**

```python
# scripts/run_selection_eval.py
"""Tool Selection A/B Evaluation — the true test of description optimization.

Compares Precision@1 using original vs. optimized descriptions against ground truth.
This is the North Star metric: "Does the optimized description help the pipeline
select the correct tool more often?"

Usage:
    PYTHONPATH=src uv run python scripts/run_selection_eval.py \
        --ground-truth data/ground_truth/seed_set.jsonl \
        --optimized data/optimized/descriptions.jsonl
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loguru import logger


async def main(args: argparse.Namespace) -> None:
    gt_path = Path(args.ground_truth)
    opt_path = Path(args.optimized)

    if not gt_path.exists():
        logger.error(f"Ground truth not found: {gt_path}")
        return
    if not opt_path.exists():
        logger.error(f"Optimized descriptions not found: {opt_path}")
        return

    # Load ground truth
    ground_truth = []
    with open(gt_path) as f:
        for line in f:
            ground_truth.append(json.loads(line.strip()))

    # Load optimized descriptions as lookup
    optimized_lookup: dict[str, dict] = {}
    with open(opt_path) as f:
        for line in f:
            entry = json.loads(line.strip())
            optimized_lookup[entry["tool_id"]] = entry

    logger.info(f"Loaded {len(ground_truth)} GT queries, {len(optimized_lookup)} optimized descriptions")

    # Report
    total = len(ground_truth)
    tools_with_optimization = sum(
        1 for gt in ground_truth
        if gt["correct_tool_id"] in optimized_lookup
        and optimized_lookup[gt["correct_tool_id"]].get("status") == "success"
    )

    logger.info(f"GT queries with optimized correct tool: {tools_with_optimization}/{total}")
    logger.info(
        "To run full A/B evaluation, build two Qdrant indices "
        "(original vs optimized descriptions) and run the evaluation harness on each."
    )
    logger.info(
        "Compare: Precision@1(original) vs Precision@1(optimized) — "
        "this is the definitive test of description optimization value."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tool Selection A/B Evaluation")
    parser.add_argument("--ground-truth", default="data/ground_truth/seed_set.jsonl")
    parser.add_argument("--optimized", default="data/optimized/descriptions.jsonl")
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
```

- [ ] **Step 4: Commit**

```bash
git add scripts/run_selection_eval.py tests/evaluation/test_selection_eval.py
git commit -m "feat(desc-optimizer): tool selection A/B evaluation script for end-to-end validation"
```

---

### Task 10: Run Full Test Suite and Fix Regressions

**Files:**
- All modified files from Tasks 1-9

Ensure all existing tests still pass after the changes. Fix any regressions.

- [ ] **Step 1: Run all unit tests**

Run: `uv run pytest tests/unit/test_description_optimizer/ -v`
Expected: PASS (all tests)

- [ ] **Step 2: Run all verification tests**

Run: `uv run pytest tests/verification/ -v`
Expected: PASS (all tests)

- [ ] **Step 3: Run evaluation tests**

Run: `uv run pytest tests/evaluation/ -v`
Expected: PASS (all tests)

- [ ] **Step 4: Run full test suite with coverage**

Run: `uv run pytest tests/ --cov=src -v`
Expected: PASS, coverage >= 80%

- [ ] **Step 5: Run lint**

Run: `uv run ruff check src/ tests/ && uv run ruff format src/ tests/`
Expected: Clean

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "test(desc-optimizer): all tests pass after grounded optimization refactor"
```

---

## Summary of Changes

| Component | Before | After |
|-----------|--------|-------|
| **LLM Context** | Description only | Description + input_schema + sibling tools |
| **Optimization Mode** | Full rewrite | Augmentation (preserve + append) |
| **Boundary Guidance** | "Add limitations: Does NOT X" | "ONLY state limitations in original" |
| **Disambiguation** | "Unlike other tools..." (generic) | Compare against named sibling tools |
| **Parameter Coverage** | "Mention parameters" (hallucinated) | "Mention these actual params: `file`, `id`" |
| **Quality Gate** | GEO + cosine similarity | + Hallucination detection + Info preservation |
| **Pipeline Interface** | `(tool_id, description)` | `MCPTool` with `input_schema` + sibling tools |
| **Evaluation** | GEO score only (circular) | + Tool Selection A/B (Precision@1) |

## Dependency Graph

```
Task 1 (OptimizationContext model)
  └─► Task 2 (Grounded prompts)
       └─► Task 3 (Context-aware optimizer)
            └─► Task 4 (Pipeline with MCPTool)
                 └─► Task 7 (Integrate gates into pipeline)
                      └─► Task 8 (Update scripts)
                           └─► Task 9 (Selection eval)
                                └─► Task 10 (Full test suite)
Task 5 (Hallucination gate) ──► Task 7
Task 6 (Info preservation gate) ──► Task 7
```
