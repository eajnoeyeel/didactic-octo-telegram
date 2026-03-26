---
name: evaluation-workflow
description: Work on ground-truth generation, evaluation scaffolding, or experiment-facing metrics in this repository. Use when editing `data/ground_truth`, `src/data/ground_truth.py`, `tests/evaluation/`, or when adding future evaluation modules. Do not use for ordinary retrieval-code fixes that do not touch evaluation concerns.
---

# Evaluation Workflow

1. Start from the current codebase, not the planned architecture. `src/evaluation/` is not implemented yet in this repository.
2. For schema truth, use [`src/models.py`](/Users/iyeonjae/Desktop/shockwave/mcp-discovery/src/models.py) and the checked-in JSONL files before using design docs.
3. Use `docs/design/evaluation.md`, `docs/design/ground-truth-design.md`, and related plan docs as reference targets only.
4. When changing GT generation or validation, keep JSONL compatibility explicit and add or update tests around `GroundTruthEntry`, loaders, or quality-gate behavior.
5. If a task is really about planned experiment infrastructure rather than current code, say that clearly and separate design work from implementation work.
