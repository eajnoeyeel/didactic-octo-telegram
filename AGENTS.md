# Repository Instructions

Keep repository-wide rules here. Use a nearer `AGENTS.md` for directory-specific guidance, and use `.agents/skills/` only for repeatable workflows.

## Working Order

1. Follow the user's request and the nearest applicable `AGENTS.md`.
2. Treat current code, tests, and checked-in config as the source of truth.
3. Treat `docs/` as secondary context. Many files are planning artifacts and may describe modules that do not exist yet.
4. Treat `CLAUDE.md` and `.claude/` as legacy migration inputs, not active Codex instructions.

If code and docs disagree, follow the current repository state and call out the drift.

## Repository Map

- `src/`: main Python package. Current implementation is centered on `config.py`, `models.py`, `data/`, `embedding/`, `pipeline/`, and `retrieval/`.
- `scripts/`: runnable entry points for crawling, indexing, and synthetic ground-truth generation.
- `tests/unit/`: main active automated coverage.
- `tests/integration/` and `tests/evaluation/`: sparse or placeholder at the moment.
- `data/`: checked-in raw snapshots and ground-truth artifacts.
- `docs/`: design, planning, research, and paper notes. Useful, but not authoritative over code.
- `proxy_verification/`: separate MCP proxy prototype with its own local `AGENTS.md`.

## Current Implementation Boundaries

Do not assume planned modules already exist.

- Implemented now: `src/data/*`, `src/embedding/*`, `src/pipeline/{strategy,flat,sequential,confidence}.py`, `src/retrieval/qdrant_store.py`, `src/models.py`, `src/config.py`.
- Not present yet in the main app: `src/api/`, `src/evaluation/`, `src/reranking/`, `src/analytics/`, `scripts/run_experiments.py`.
- Several docs still refer to planned `parallel`, `taxonomy_gated`, rerankers, FastAPI routes, and experiment runners. Add those only when the user asks for them and when tests/doc updates land with the code.

## Common Commands

```bash
uv sync
uv run ruff check src tests
uv run pytest tests/unit -v
uv run python scripts/collect_data.py --max-servers 20
uv run python scripts/build_index.py --input data/raw/servers.jsonl
uv run python scripts/generate_ground_truth.py --servers data/raw/servers.jsonl
```

## Coding Rules

- Python target is 3.12.
- Keep type hints on public functions and model boundaries.
- In the main `src/` package, use async clients for I/O. Prefer `AsyncOpenAI`, `AsyncQdrantClient`, and `httpx.AsyncClient`.
- Route new application settings through [`src/config.py`](/Users/iyeonjae/Desktop/shockwave/mcp-discovery/src/config.py) instead of scattering direct environment parsing across modules.
- In the main project, tool IDs use `TOOL_ID_SEPARATOR = "::"`. Do not reintroduce `/`-based IDs from older planning docs.
- In the main project, use `loguru` rather than `print()` or stdlib `logging`.
- Prefer module-top imports, small pure helpers for transformations, and Pydantic v2 models at external boundaries.
- Follow the existing Ruff-based style; do not add Black/isort-specific workflow assumptions.

## Verification Expectations

Before handing off non-trivial code changes in the main project:

1. Run `uv run ruff check src tests`.
2. Run the smallest relevant `pytest` scope for the files you changed.
3. If you touched shared models, config, embedding, retrieval, or pipeline code, prefer the affected unit suites over no-op spot checks.
4. Explicitly report any skipped or unrun checks, especially when API keys, Qdrant, or other external services are required.

Useful targeted test groups:

```bash
uv run pytest tests/unit/test_config.py tests/unit/test_models.py -v
uv run pytest tests/unit/test_embedder.py tests/unit/test_qdrant_store.py -v
uv run pytest tests/unit/test_flat_strategy.py tests/unit/test_sequential_strategy.py -v
uv run pytest tests/unit/test_ground_truth.py -v
```

If you change anything under `proxy_verification/`, also follow the local verification rules in [`proxy_verification/AGENTS.md`](/Users/iyeonjae/Desktop/shockwave/mcp-discovery/proxy_verification/AGENTS.md).

## Documentation Policy

- Update docs when shipped behavior, commands, file layout, or architecture claims changed.
- Be explicit about implemented vs planned state.
- Prefer small targeted corrections over broad rewrites of brainstorming material.
- When editing `docs/papers/` or `docs/research/`, follow [`docs/CONVENTIONS.md`](/Users/iyeonjae/Desktop/shockwave/mcp-discovery/docs/CONVENTIONS.md).

## Skills

Use `.agents/skills/` for repeatable workflows such as review, debugging, verification, or experiment planning. Keep skill metadata explicit about when to use and when not to use a skill, and keep repo-wide rules in this file rather than duplicating them in every skill.
