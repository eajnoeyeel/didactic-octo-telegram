# MCP Discovery Platform — 구현 계획 Hub

> **Source of truth**: 구현 스펙. Phase별 상세는 개별 파일 참조.
> 각 Phase 파일에 코드 스니펫, 테스트, 파일 구조 포함.

---

## 프로젝트 개요

- **Goal**: MCP Gateway + Analytics Platform
  - `find_best_tool(query)` → 최적 Provider MCP 추천
  - `execute_tool(tool_id, params)` → Provider MCP 프록시 호출
  - Provider에게 Analytics 대시보드 제공 (왜 선택 안 되는지, 개선법)
- **Architecture**: Bridge/Router (DP1) — LLM <> Our MCP Bridge <> Provider MCPs
  - Core: 2-stage retrieval pipeline (Embedding > Vector Search > Reranker > Confidence 분기)
  - MetaMCP base + 벡터 서치 라우터 교체
  - 3 Strategy variants: Sequential, Parallel, Taxonomy-gated (`PipelineStrategy` interface)

---

## 기술 스택

| 영역 | 도구 |
|------|------|
| 언어 | Python 3.12, type hints 필수 |
| 프레임워크 | FastAPI, pydantic v2 |
| 벡터 DB | Qdrant Cloud (free tier) |
| 임베딩 | BGE-M3 or OpenAI `text-embedding-3-small` (실험으로 결정, voyage-code-2 사용 금지) |
| 리랭커 | Cohere Rerank 3 |
| 트레이싱 | Langfuse (LLM tracing) |
| 실험 추적 | Weights & Biases |
| 테스트 | pytest, pytest-asyncio |
| 패키지 관리 | uv |

---

## Phase 요약 테이블

| Phase | 이름 | 상세 파일 | 주요 산출물 |
|-------|------|-----------|-------------|
| 0 | Project Foundation | [phase-0-2.md](phase-0-2.md) | `pyproject.toml`, `src/config.py`, `src/models.py` |
| 1 | Data Collection | [phase-0-2.md](phase-0-2.md) | `src/data/crawler.py`, `src/data/mcp_connector.py` |
| 2 | Embedding & Vector Store | [phase-0-2.md](phase-0-2.md) | `src/embedding/`, `src/retrieval/qdrant_store.py`, `src/data/indexer.py` |
| 3 | Core Pipeline (Sequential) | [phase-3-5.md](phase-3-5.md) | `src/pipeline/strategy.py`, `src/pipeline/sequential.py` |
| 4 | Ground Truth Generation | [phase-3-5.md](phase-3-5.md) | `src/data/ground_truth.py`, `data/ground_truth/` |
| 5 | Evaluation Harness | [phase-3-5.md](phase-3-5.md) | `src/evaluation/`, 6개 core metrics |
| 6 | Reranker | [phase-6-8.md](phase-6-8.md) | `src/reranking/`, Cohere + LLM fallback |
| 7 | Hybrid Search (RRF) | [phase-6-8.md](phase-6-8.md) | `src/retrieval/hybrid.py`, Strategy B (Parallel) |
| 8 | FastAPI + MCP Tool Server | [phase-6-8.md](phase-6-8.md) | `src/api/`, `/search` endpoint |
| 9 | Provider Analytics | [phase-9-12.md](phase-9-12.md) | `src/analytics/`, SEO Score, Confusion Matrix |
| 10 | Experiment Runner | [phase-9-12.md](phase-9-12.md) | `src/evaluation/experiment.py`, Description Correlation |
| 11 | Instrumentation | [phase-9-12.md](phase-9-12.md) | Langfuse tracing, W&B logging |
| 12 | E2E Smoke Test | [phase-9-12.md](phase-9-12.md) | 전체 파이프라인 로컬 실행 검증 |
| 13 | Bridge/Router | [phase-9-12.md](phase-9-12.md) | `src/bridge/`, find_best_tool + execute_tool MCP Server |

---

## 의존성 그래프

```
Phase 0 (Foundation)
  |
  v
Phase 1 (Data Collection) --> Phase 2 (Embedding & Vector Store)
                                  |
                                  v
                              Phase 3 (Sequential Pipeline)
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
              Phase 4 (Ground Truth)      Phase 6 (Reranker)
                    |                           |
                    v                           v
              Phase 5 (Evaluation)        Phase 7 (Hybrid Search / RRF)
                    |                           |
                    +-------------+-------------+
                                  |
                                  v
                            Phase 8 (FastAPI)
                                  |
                    +-------------+-------------+
                    |             |             |
                    v             v             v
              Phase 9        Phase 10       Phase 11
              (Analytics)    (Experiments)  (Instrumentation)
                    |             |             |
                    +-------------+-------------+
                                  |
                                  v
                            Phase 12 (E2E Smoke Test)
                                  |
                                  v
                            Phase 13 (Bridge/Router)
```

---

## 공통 컨벤션

- **TDD**: 실패 테스트 먼저 > 구현 > 통과 확인
- **ABC 패턴**: Embedder, Reranker, Strategy, Evaluator는 추상 클래스
- **네이밍**
  - tool_id: `"{server_id}/{tool_name}"`
  - query_id: `"gt-{category}-{number}"`
- **커밋**: Phase 단위, `feat: ...` / `test: ...` / `fix: ...` prefix
- **환경변수**: `.env` + pydantic-settings, 하드코딩 금지
- **테스트**: 외부 API는 AsyncMock, integration은 `@pytest.mark.skipif(no_api_key)`

---

## Agentic Worker 지침

- `superpowers:subagent-driven-development` 또는 `superpowers:executing-plans` 사용
- 각 Step의 `- [ ]` 체크박스로 진행 추적
- Phase 파일 내 코드 스니펫을 그대로 사용 (경로, import 정확히 일치)
