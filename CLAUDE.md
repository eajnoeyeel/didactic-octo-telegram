# CLAUDE.md

> **이 파일은 규칙(conventions, constraints)과 참조 포인터만 둔다.** 상세 컨텍스트는 각 문서에 분리.
> 매 세션마다 전체 로드되므로 prompt bloat 방지를 위해 간결하게 유지할 것.
> 최종 업데이트: 2026-03-29

---

## 메타 규칙

- **CLAUDE.md에는 규칙(conventions, constraints)과 참조 포인터만 기록한다.**
- 상세 정보가 필요하면 해당 파일을 Read tool로 직접 읽는다.
- CLAUDE.md 수정 시 200줄 이하를 유지한다.

---

## 프로젝트 한줄 요약

MCP Discovery Platform — a two-sided platform connecting LLM clients with MCP tool providers. LLM clients connect to a single Bridge MCP Server that routes queries to the best tool via a 2-stage retrieval pipeline (embedding search → reranker → confidence branching). Providers get analytics on why their tools are/aren't selected.

**North Star**: Precision@1 >= 50% (Pool 50, mixed domain)

**Core Thesis**: "Higher description quality → higher tool selection rate" (E4에서 검증할 핵심 가설)

---

## 상세 컨텍스트 참조 (Lazy Loading)

필요 시 아래 파일을 Read tool로 읽을 것:

| 파일 | 내용 |
|------|------|
| `docs/context/project-overview.md` | 프로젝트 요약, North Star, 테제, 타임라인 |
| `docs/design/architecture.md` | DP0-DP9 결정, 기술 스택, Provider 기능, 통제 변인 |
| `docs/design/architecture-diagrams.md` | Mermaid 다이어그램 (파이프라인, 데이터 흐름, 모듈 의존관계) |
| `docs/design/evaluation.md` | **평가 참조 허브** — 요약 + 하위 상세 문서 포인터 |
| `docs/design/metrics-rubric.md` | 11개 지표 정의, 임계값 |
| `docs/design/metrics-dashboard.md` | 대시보드 레이아웃, Metric Tree, Alert, Review Cadence |
| `docs/design/experiment-design.md` | E0-E7 실험 허브 |
| `docs/design/experiment-details.md` | 실험 상세 스펙 (조건 테이블, CLI, 출력 형식) |
| `docs/design/ground-truth-design.md` | GT 스키마, 생성 전략 |
| `docs/design/code-structure.md` | 계획된 디렉토리/파일 구조 |
| `docs/plan/implementation.md` | 구현 로드맵 (Phase 요약 + 상세 파일 포인터) |
| `docs/plan/deferred.md` | 후순위 기능 + Phase 13 (Gated) |
| `docs/plan/checklist.md` | 진행 체크리스트 |
| `docs/mentoring/open-questions.md` | 과거 멘토링 작업 메모 (historical). 현재 blockers는 `docs/plan/checklist.md` 기준 |
| `docs/research/external-benchmarks-20260328.md` | 외부 벤치마크 조사 (MCP-Zero, MCP-Atlas, Description Smells) |
| `docs/handoff/external-data-strategy-20260328.md` | 외부 데이터 전략 변경 핸드오프 (ADR-0011, ADR-0012) |
| `docs/CONVENTIONS.md` | papers/, research/ 문서 템플릿, 네이밍 규약 |
| `proxy_verification/CLAUDE.md` | Proxy MCP 검증 작업 지침 (하위 문서 포인터 포함) |
| `docs/progress/status-report.md` | **진행 현황 보고서** — Phase별 완료 현황, 테스트/커버리지, 백로그 |

When code conflicts with design docs, **docs/ takes precedence**.

---

## Commands

```bash
# Dependencies
uv sync                              # Install all deps

# Run server (planned; `src/api/main.py` not present yet)
# uv run uvicorn src.api.main:app --reload

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
uv run python scripts/verify_ground_truth.py   # GT 품질 검증 (통계/QualityGate/무결성)
uv run python scripts/import_mcp_zero.py       # MCP-Zero → MCPServer/MCPTool + Qdrant
uv run python scripts/convert_mcp_atlas.py     # MCP-Atlas → GT JSONL
uv run python scripts/run_e0.py                         # E0 baseline 실행
```

---

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
- `Embedder` — BGE-M3, OpenAI text-embedding-3-small, OpenAI text-embedding-3-large (E2 결정, voyage-code-2 prohibited)
- `Reranker` — Cohere Rerank 3, LLM fallback
- `Evaluator` — metric computation plugins

### Key Data Models (Pydantic v2)

- `MCPTool`: tool_id format is `server_id::tool_name` (TOOL_ID_SEPARATOR = "::", `/` ambiguous in Smithery qualifiedNames)
- `MCPServer`: contains tools list
- `SearchResult`: tool + score + rank + reason
- `GroundTruth`: query + correct_server_id + correct_tool_id + difficulty + category

### Experiment System (E0-E7)

Experiments run sequentially with dependencies: E0 (1-Layer vs 2-Layer) → E1 (strategy comparison) → E2 (embedding) → E3 (reranker) → E4/E5/E6 (parallel: thesis validation, pool scale, pool similarity). Each experiment changes exactly one independent variable. Currently only `scripts/run_e0.py` (Flat + Sequential) is implemented; `run_experiments.py` CLI는 Phase 10 이후 구현 예정.

---

## Key Constraints

- **Async only**: All I/O uses async/await (AsyncQdrantClient, AsyncOpenAI, httpx.AsyncClient). Never `requests`.
- **Logging**: loguru only. No `print()`, no `import logging`.
- **Testing**: pytest + pytest-asyncio with `asyncio_mode="auto"`. Integration tests guarded by `@pytest.mark.skipif(not os.getenv("API_KEY"))`.
- **Qdrant IDs**: `uuid.uuid5(MCP_DISCOVERY_NAMESPACE, tool_id)` — deterministic, upsert-safe.
- **Confidence branching**: gap-based threshold 0.15 (rank1 - rank2 score gap).
- **Ground truth**: JSONL format in `data/ground_truth/`. Seed set is manually curated; MCP-Atlas is per-step decomposed (ADR-0012); synthetic is LLM-generated (보조).
- **`.env` 파일은 절대 커밋하지 않음** — `.env.example` 참조하여 생성 (필수: OPENAI_API_KEY, QDRANT_URL, COHERE_API_KEY)
- **External data** (`data/external/`)는 Git-ignored. 별도 다운로드 필요 (`data/external/README.md` 참조)

---

## 코딩 컨벤션

### 네이밍
- 파일/변수: `snake_case`, 클래스: `PascalCase`, 상수: `UPPER_SNAKE_CASE`
- tool_id: `"{server_id}::{tool_name}"`, query_id: `"gt-{category}-{number}"`

### Git
- 커밋 메시지: `feat: ...`, `fix: ...`, `test: ...`, `docs: ...`, `refactor: ...`
- Phase 단위 커밋 권장
