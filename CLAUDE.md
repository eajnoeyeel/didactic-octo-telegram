# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Summary

MCP Discovery Platform — a two-sided platform connecting LLM clients with MCP tool providers. LLM clients connect to a single Bridge MCP Server that routes queries to the best tool via a 2-stage retrieval pipeline (embedding search → reranker → confidence branching). Providers get analytics on why their tools are/aren't selected.

**North Star**: Precision@1 >= 50% (Pool 50, mixed domain)

**Core Thesis**: "Higher description quality → higher tool selection rate" (validated via E4 A/B experiment)

## Commands

```bash
# Dependencies
uv sync                              # Install all deps

# Run server
uv run uvicorn src.api.main:app --reload

# Tests
uv run pytest tests/ -v              # All tests
uv run pytest tests/unit/ -v         # Unit only
uv run pytest tests/unit/test_config.py -v          # Single file
uv run pytest tests/unit/test_config.py::test_name  # Single test
uv run pytest tests/ --cov=src -v    # With coverage

# Lint & format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Scripts
uv run python scripts/collect_data.py
uv run python scripts/build_index.py --pool-size 50
uv run python scripts/generate_ground_truth.py
uv run python scripts/run_experiments.py --experiment E1
```

## Architecture

### Pipeline Flow

```
LLM → Bridge MCP Server (find_best_tool / execute_tool)
  → Core Pipeline (PipelineStrategy ABC)
    → Stage 1: Embedding search (Qdrant)
    → Stage 2: Reranker (Cohere Rerank 3) + Confidence branching (gap > 0.15)
```

### Three Search Strategies (all implement `PipelineStrategy` ABC)

- **Sequential (A)**: Server index → filtered tool search → rerank. Simple but hard gate at layer 1.
- **Parallel (B)**: Server + tool index in parallel → RRF score fusion → rerank. Robust to layer 1 misses.
- **Taxonomy-gated (C)**: Intent classifier → category sub-index → rerank. Precise but fragile.

### ABC Pattern (Mandatory)

All pluggable components use abstract base classes — business logic depends on ABCs only:
- `PipelineStrategy` — search strategies, swapped via `StrategyRegistry`
- `Embedder` — BGE-M3, OpenAI text-embedding-3-small (voyage-code-2 prohibited)
- `Reranker` — Cohere Rerank 3, LLM fallback
- `Evaluator` — metric computation plugins

### Key Data Models (Pydantic v2)

- `MCPTool`: tool_id format is `server_id::tool_name` (TOOL_ID_SEPARATOR = "::", `/` ambiguous in Smithery qualifiedNames)
- `MCPServer`: contains tools list
- `SearchResult`: tool + score + rank + reason
- `GroundTruth`: query + correct_server_id + correct_tool_id + difficulty + category

### Experiment System (E0-E7)

Experiments run sequentially with dependencies: E0 (1-Layer vs 2-Layer) → E1 (strategy comparison) → E2 (embedding) → E3 (reranker) → E4/E5/E6 (parallel: thesis validation, pool scale, pool similarity). Each experiment changes exactly one independent variable, controlled via `run_experiments.py --experiment E{n}`.

## Design Documents (Source of Truth)

When code conflicts with design docs, **docs/ takes precedence**:

| Area | SOT |
|------|-----|
| Architecture & decisions | `docs/design/architecture.md` |
| Metrics definitions | `docs/design/metrics-rubric.md` |
| Ground truth schema | `docs/design/ground-truth-design.md` |
| Experiment specs | `docs/design/experiment-design.md` + `experiment-details.md` |
| Code structure | `docs/design/code-structure.md` |
| Document conventions | `docs/CONVENTIONS.md` |

## Key Constraints

- **Async only**: All I/O uses async/await (AsyncQdrantClient, AsyncOpenAI, httpx.AsyncClient). Never `requests`.
- **Logging**: loguru only. No `print()`, no `import logging`.
- **Testing**: pytest + pytest-asyncio with `asyncio_mode="auto"`. Integration tests guarded by `@pytest.mark.skipif(not os.getenv("API_KEY"))`.
- **Qdrant IDs**: `uuid.uuid5(MCP_DISCOVERY_NAMESPACE, tool_id)` — deterministic, upsert-safe. (Python `hash()` is process-local and non-deterministic across runs.)
- **Confidence branching**: gap-based threshold 0.15 (rank1 - rank2 score gap).
- **Ground truth**: JSONL format in `data/ground_truth/`. Seed set is manually curated; synthetic is LLM-generated.
