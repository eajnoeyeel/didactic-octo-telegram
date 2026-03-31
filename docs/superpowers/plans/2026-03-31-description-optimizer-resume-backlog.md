# Description Optimizer Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resume `description_optimizer` only after core pipeline work is stable, focusing first on gate throughput and regression control instead of more prompt churn.

**Architecture:** Keep `retrieval_description` as the canonical retrieval text, treat GEO as diagnostic-only, and add evidence-first tooling around gate rejects before changing prompt or gate behavior. Re-run MCP-Zero evaluation only after each bounded change so regressions stay attributable.

**Tech Stack:** Python 3.12, pytest, pytest-asyncio, loguru, AsyncOpenAI, existing `src/description_optimizer/` module, JSONL artifacts in `data/verification/`

---

### Task 1: Add Gate-Rejection Inventory Tooling

**Files:**
- Create: `scripts/analyze_gate_rejections.py`
- Create: `tests/verification/test_gate_rejection_analysis.py`
- Modify: `description_optimizer/docs/development-history.md`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from scripts.analyze_gate_rejections import summarize_gate_rejections


def test_summarize_gate_rejections_buckets_similarity_and_contamination(tmp_path: Path) -> None:
    input_path = tmp_path / "results.jsonl"
    input_path.write_text(
        "\n".join(
            [
                '{"tool_id":"exa::web_search_exa","status":"gate_rejected","skip_reason":"Similarity: Semantic similarity 0.742 below threshold 0.75"}',
                '{"tool_id":"math::median","status":"gate_rejected","skip_reason":"Contamination: sibling names leaked into retrieval text"}',
                '{"tool_id":"fetch::fetch","status":"success","skip_reason":null}',
            ]
        )
        + "\n"
    )

    summary = summarize_gate_rejections(input_path)

    assert summary["total_gate_rejected"] == 2
    assert summary["by_category"]["similarity"] == 1
    assert summary["by_category"]["contamination"] == 1
    assert summary["examples"]["similarity"] == ["exa::web_search_exa"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/verification/test_gate_rejection_analysis.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing `summarize_gate_rejections`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


def _categorize(skip_reason: str) -> str:
    lowered = skip_reason.lower()
    if "similarity" in lowered:
        return "similarity"
    if "contamination" in lowered:
        return "contamination"
    if "hallucination" in lowered:
        return "hallucination"
    if "infopreservation" in lowered or "information lost" in lowered:
        return "info_preservation"
    if "faithfulness" in lowered:
        return "faithfulness"
    return "other"


def summarize_gate_rejections(input_path: Path) -> dict:
    by_category: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    total = 0

    with input_path.open() as fh:
        for line in fh:
            entry = json.loads(line)
            if entry.get("status") != "gate_rejected":
                continue
            total += 1
            category = _categorize(entry.get("skip_reason") or "")
            by_category[category] += 1
            if len(examples[category]) < 5:
                examples[category].append(entry["tool_id"])

    return {
        "total_gate_rejected": total,
        "by_category": dict(by_category),
        "examples": dict(examples),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/verification/test_gate_rejection_analysis.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/analyze_gate_rejections.py tests/verification/test_gate_rejection_analysis.py description_optimizer/docs/development-history.md
git commit -m "feat(desc-optimizer): add gate rejection inventory tooling"
```

### Task 2: Add Retrieval-Anchor Prompt Rules Before More Prompt Iteration

**Files:**
- Modify: `src/description_optimizer/optimizer/prompts.py`
- Modify: `tests/unit/test_description_optimizer/test_prompts.py`
- Modify: `tests/unit/test_description_optimizer/test_quality_gate.py`

- [ ] **Step 1: Write the failing test**

```python
from description_optimizer.optimizer.prompts import (
    build_grounded_prompt,
    build_optimization_prompt,
)


def test_grounded_prompt_requires_short_anchor_preserving_retrieval_text() -> None:
    prompt = build_grounded_prompt(
        original="List records from an Airtable table.",
        tool_id="airtable::list_records",
        input_schema={"type": "object", "properties": {"table_id": {"type": "string"}}},
        sibling_tools=[],
        weak_dimensions=["clarity"],
        dimension_scores={"clarity": 0.2},
    )
    lower = prompt.lower()
    assert "exactly one sentence of 8-22 words" in lower
    assert "start with the original action verb" in lower


def test_non_grounded_prompt_reuses_the_same_retrieval_rules() -> None:
    prompt = build_optimization_prompt(
        original="Search GitHub code by keyword.",
        tool_id="github::search_code",
        weak_dimensions=["clarity"],
        dimension_scores={"clarity": 0.2},
    )
    assert "keep the original object phrase" in prompt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_description_optimizer/test_prompts.py -v`
Expected: FAIL because the prompt builders do not yet include the retrieval-anchor rules

- [ ] **Step 3: Write minimal implementation**

```python
RETRIEVAL_RULES = [
    "Write exactly one sentence of 8-22 words for retrieval_description.",
    "Start with the original action verb when possible.",
    "Keep the original object phrase or at least two meaningful tokens from the original description.",
    "Do not replace specific nouns with generic nouns like data, resource, system, or item.",
]


def _render_retrieval_rules() -> str:
    return "\n".join(f"{idx}. {rule}" for idx, rule in enumerate(RETRIEVAL_RULES, start=1))


def build_optimization_prompt(...) -> str:
    ...
    return f\"\"\"Optimize this MCP tool description for retrieval.
...
**Retrieval Rules**:
{_render_retrieval_rules()}
...
\"\"\"


def build_grounded_prompt(...) -> str:
    ...
    sections.append(f"**Retrieval Rules**:\n{_render_retrieval_rules()}\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_description_optimizer/test_prompts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/description_optimizer/optimizer/prompts.py tests/unit/test_description_optimizer/test_prompts.py tests/unit/test_description_optimizer/test_quality_gate.py
git commit -m "fix(desc-optimizer): enforce retrieval anchor prompt rules"
```

### Task 3: Re-run MCP-Zero Optimization With Explicit CLI Inputs

**Files:**
- Modify: `scripts/optimize_gt_tools.py`
- Modify: `scripts/run_retrieval_ab_eval.py`
- Create: `tests/verification/test_mcp_zero_resume_regression.py`
- Modify: `description_optimizer/docs/development-history.md`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from scripts.optimize_gt_tools import build_parser


def test_optimize_gt_tools_parser_accepts_resume_inputs() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--ground-truth",
            "data/verification/mcp_zero_gt_filtered.jsonl",
            "--pool",
            "data/raw/mcp_zero_servers.jsonl",
            "--output",
            "data/verification/mcp_zero_gt_optimized_descriptions.jsonl",
            "--min-similarity",
            "0.75",
        ]
    )

    assert args.ground_truth.endswith("mcp_zero_gt_filtered.jsonl")
    assert args.pool.endswith("mcp_zero_servers.jsonl")
    assert args.min_similarity == 0.75
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/verification/test_mcp_zero_resume_regression.py -v`
Expected: FAIL because `build_parser()` does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", default="data/ground_truth/seed_set.jsonl")
    parser.add_argument("--pool", default="data/raw/servers.jsonl")
    parser.add_argument("--output", default="data/verification/gt_optimized_descriptions.jsonl")
    parser.add_argument("--min-similarity", type=float, default=0.75)
    return parser


async def main(args: argparse.Namespace) -> None:
    gt_path = Path(args.ground_truth)
    raw_data = Path(args.pool)
    output_path = Path(args.output)
    gate = QualityGate(min_similarity=args.min_similarity)
    ...
```

- [ ] **Step 4: Run verification commands**

Run: `uv run pytest tests/verification/test_mcp_zero_resume_regression.py -v`
Expected: PASS

Run: `PYTHONPATH=src uv run python scripts/optimize_gt_tools.py --ground-truth data/verification/mcp_zero_gt_filtered.jsonl --pool data/raw/mcp_zero_servers.jsonl --output data/verification/mcp_zero_gt_optimized_descriptions.jsonl --min-similarity 0.75`
Expected: JSONL regenerated without CLI errors

Run: `PYTHONPATH=src uv run python scripts/run_retrieval_ab_eval.py --tools data/raw/mcp_zero_servers.jsonl --ground-truth data/verification/mcp_zero_gt_filtered.jsonl --optimized data/verification/mcp_zero_gt_optimized_descriptions.jsonl --top-k 10 --output data/verification/mcp_zero_retrieval_ab_report.json`
Expected: updated report JSON emitted

- [ ] **Step 5: Commit**

```bash
git add scripts/optimize_gt_tools.py scripts/run_retrieval_ab_eval.py tests/verification/test_mcp_zero_resume_regression.py description_optimizer/docs/development-history.md data/verification/mcp_zero_gt_optimized_descriptions.jsonl data/verification/mcp_zero_retrieval_ab_report.json
git commit -m "feat(desc-optimizer): refresh mcp-zero resume workflow"
```

### Task 4: Sync Documentation After Resume Batch

**Files:**
- Modify: `description_optimizer/CLAUDE.md`
- Modify: `description_optimizer/docs/evaluation-design.md`
- Modify: `docs/analysis/description-optimizer-mcp-zero-validation-20260330.md`
- Modify: `description_optimizer/docs/development-history.md`

- [ ] **Step 1: Write the failing documentation check**

```python
from pathlib import Path


def test_resume_docs_reference_current_primary_artifacts() -> None:
    text = Path("description_optimizer/docs/development-history.md").read_text()
    assert "mcp_zero_gt_optimized_descriptions.jsonl" in text
    assert "gate throughput" in text
```

- [ ] **Step 2: Run test to verify it fails if docs drift**

Run: `uv run pytest tests/verification/test_mcp_zero_resume_regression.py -v`
Expected: FAIL when the history doc is not refreshed with the new run output

- [ ] **Step 3: Update the documents**

```markdown
- update the latest success/reject counts
- refresh primary query-level metrics
- keep the "do not repeat" list aligned with the newest evidence
- preserve backlog status unless the root project plan changed first
```

- [ ] **Step 4: Run docs check**

Run: `uv run pytest tests/verification/test_mcp_zero_resume_regression.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add description_optimizer/CLAUDE.md description_optimizer/docs/evaluation-design.md docs/analysis/description-optimizer-mcp-zero-validation-20260330.md description_optimizer/docs/development-history.md tests/verification/test_mcp_zero_resume_regression.py
git commit -m "docs(desc-optimizer): refresh resume-state documentation"
```
