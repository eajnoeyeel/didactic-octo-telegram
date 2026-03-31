# Repository Instructions

Keep repository-wide rules here. Use a nearer `AGENTS.md` for directory-specific guidance, and use `.codex/skills/` for repeatable workflows.

## Working Order

1. Follow the user's request and the nearest applicable `AGENTS.md`.
2. **설계 문서(`docs/design/`)가 Source of Truth.** 코드와 설계가 충돌하면 설계 기준으로 코드를 수정한다. 의도적 차이라면 설계 문서에 명시할 것.
3. ADR(`docs/adr/`)은 의사결정의 SOT. 주제별 최신 accepted ADR이 정답.
4. `docs/plan/`, `docs/progress/`는 파생 산출물. 설계 확정 후 재생성.
5. `CLAUDE.md`와 `.claude/`는 Claude Code용 지침. Codex에서는 참고만 하고 이 파일을 우선한다.

## Repository Map

- `src/`: main Python package.
  - `config.py`, `models.py` — 프로젝트 설정, 데이터 모델
  - `data/` — crawler, mcp_connector, ground_truth, indexer, smithery_client, server_selector
  - `embedding/` — Embedder ABC + OpenAI embedder
  - `pipeline/` — PipelineStrategy ABC, StrategyRegistry, flat, sequential, confidence
  - `retrieval/` — Qdrant Store wrapper
  - `evaluation/` — Evaluator ABC, harness, metrics (7개 compute → 11 result fields)
  - `reranking/` — Reranker ABC + CohereReranker
- `scripts/` — collect_data, build_index, generate_ground_truth, verify_ground_truth, import_mcp_zero, convert_mcp_atlas, run_e0
- `tests/unit/` — 주요 단위 테스트 (260 tests, 98%+ coverage)
- `tests/evaluation/` — metrics + harness 테스트 (40 tests)
- `tests/integration/` — Qdrant, Smithery, OpenAI 실제 연동 (28 tests)
- `data/` — ground_truth (seed_set, synthetic JSONL), raw, external (Git-ignored)
- `docs/` — design, plan, research, papers, adr, mentoring, handoff
- `proxy_verification/` — 별도 MCP proxy 프로토타입 (자체 `AGENTS.md`)

## Current Implementation Boundaries

Do not assume planned modules already exist.

- **Implemented**: `src/data/*`, `src/embedding/*`, `src/pipeline/{strategy,flat,sequential,confidence}.py`, `src/retrieval/qdrant_store.py`, `src/evaluation/{evaluator,harness,metrics}.py`, `src/reranking/{base,cohere_reranker}.py`, `src/models.py`, `src/config.py`
- **Not present yet**: `src/api/`, `src/analytics/`, `src/bridge/`, `src/pipeline/parallel.py`, `src/pipeline/taxonomy_gated.py`, `src/retrieval/hybrid.py`, `src/reranking/llm_fallback.py`, `src/embedding/bge_m3.py`
- Docs may refer to planned modules (`parallel`, `taxonomy_gated`, `api`, `analytics`, `bridge`). Add those only when requested and when tests land with the code.

## Common Commands

```bash
uv sync
uv run ruff check src tests
uv run pytest tests/ -v                    # All tests (260+)
uv run pytest tests/unit/ -v               # Unit only
uv run pytest tests/ --cov=src -v          # With coverage
uv run python scripts/build_index.py --pool-size 50
uv run python scripts/run_e0.py            # E0 baseline
```

## Coding Rules

- Python target is 3.12.
- Keep type hints on public functions and model boundaries.
- In `src/`, use async clients for I/O: `AsyncOpenAI`, `AsyncQdrantClient`, `httpx.AsyncClient`.
- Route settings through `src/config.py` (pydantic-settings).
- Tool IDs: `TOOL_ID_SEPARATOR = "::"`. Do not reintroduce `/`-based IDs.
- Logging: `loguru` only. No `print()`, no stdlib `logging`.
- Module-top imports, small pure helpers, Pydantic v2 at boundaries.
- Follow Ruff-based style.

## Verification Expectations

Before handing off non-trivial code changes:

1. `uv run ruff check src tests`
2. Run the relevant `pytest` scope.
3. If you touched shared models/config/embedding/retrieval/pipeline, prefer the affected unit suites.
4. Report any skipped checks (API keys, Qdrant, etc.).

## Documentation Policy

- Update docs when shipped behavior, commands, file layout, or architecture claims change.
- Be explicit about implemented vs planned state.
- Prefer small targeted corrections over broad rewrites.
- When editing `docs/papers/` or `docs/research/`, follow `docs/CONVENTIONS.md`.
