# 진행 체크리스트

> 최종 업데이트: 2026-03-30
> 상세 구현 스펙: `docs/plan/implementation.md`
> 타임라인: 2026-03-20 ~ 2026-04-26 (5주)

---

## 해결된 사항

- **OQ-1 (GEO 점수 산정)**: RESOLVED (2026-03-21, 2026-03-26 업데이트) — 5-dimension DQS → 6-dimension GEO Score 확장. 동등 가중치 1/6 x 6, E7 calibration. 상세: `docs/research/description-quality-scoring.md`, SOT: `docs/design/metrics-rubric.md`

---

## 미결 Blockers

### OQ-2: Tool Pool 구성 (MCP-Zero + Smithery 보조) — ADR-0011 — 핵심 완료 (2026-03-30)
- [x] MCP-Zero 데이터셋 다운로드 → `data/external/mcp-zero/servers.json` (308 servers, 2,797 tools)
- [x] MCP-Atlas GT 다운로드 → `data/external/mcp-atlas/MCP-Atlas.parquet` (500 human-authored tasks)
- [x] `scripts/import_mcp_zero.py` 검증된 스키마로 재작성 + 25 unit tests
- [x] `scripts/import_mcp_zero.py` 실행 → 308 servers, 2,797 tools 변환 완료
- [x] `scripts/convert_mcp_atlas.py` ADR-0012 per-step 분해 완성 + 17 unit tests
- [x] `scripts/convert_mcp_atlas.py` 실행 → 394 per-step GT entries (80 tasks, 35 servers)
- [x] MCP-Atlas per-step GT + self seed 80 병합 검증 (194 covered, query_id 중복 없음)
- [x] `scripts/run_e0.py` 업데이트 → MCP-Zero pool + 다중 GT 소스 지원
- [ ] Description Smells 4D vs GEO Score 6D 매핑 테이블 작성 (E7 비교용)
- [ ] 4종 Pool 정의 (Base, High Similarity, Low Similarity, Description Quality) — MCP-Zero 308 servers에서 선별
- [ ] Smithery API rate limit 확인 (보조 소스)
- [ ] `tools/list` 직접 연결 가능한 서버 목록 확인

### OQ-3: 자체 MCP 서버 구축 (A/B 실증)
- [ ] mcp-arxiv, mcp-calculator, mcp-korean-news 서버 구현
- [ ] 각 서버 x 2 description 버전 (Version A: Poor, Version B: Good)
- [ ] 실제 `tools/list` 연결 검증

### OQ-4: Sequential 2-Layer 버그 수정 — 부분 해결
- [x] `sequential.py`를 진짜 2-Layer로 수정 (서버 인덱스 → 필터 → 툴 검색)
- [ ] Server Classification Error Rate 별도 로깅 추가

### OQ-5: 2-Layer 아키텍처 유효성 검증 (E0 선행)
- [x] 1-Layer 파이프라인 구현 (`src/pipeline/flat.py`)
- [ ] E0 실행: 1-Layer vs 2-Layer Sequential vs 2-Layer Parallel
- [ ] 판정: Precision@1 +5%p 이상 차이 → 2-Layer 유효
- [ ] CTO 멘토링에서 결과 논의

---

## Phase 0: 프로젝트 기반 (Week 1) — ✅ 완료 (2026-03-25)
- [x] `pyproject.toml` + `uv sync --extra dev`
- [x] `src/config.py` — pydantic-settings
- [x] `src/models.py` — MCPTool, MCPServer, SearchResult, GroundTruth 등
- [x] `.env.example` + `git init` + 첫 커밋
- [x] `tests/unit/test_config.py`, `tests/unit/test_models.py` 통과

## Phase 1: 데이터 수집 (Week 1) — ✅ 완료 (2026-03-25)
- [x] `src/data/crawler.py` — SmitheryCrawler
- [x] `src/data/mcp_connector.py` — Direct MCP 연결
- [x] `scripts/collect_data.py` → `data/raw/servers.jsonl` (8 서버 수집 완료)
- [x] 단위 테스트 통과

## Phase 2: 임베딩 + Vector Store (Week 1) — ✅ 완료 (2026-03-25)
- [x] `src/embedding/base.py` — Embedder ABC
- [x] `src/embedding/openai_embedder.py`
- [ ] `src/embedding/bge_m3.py` — E2 임베딩 비교 실험에서 구현 예정 (의도적 연기)
- [x] `src/retrieval/qdrant_store.py` — Qdrant Cloud wrapper
- [x] `src/data/indexer.py` + `scripts/build_index.py`
- [x] Qdrant 로컬 Docker 실행 (`docker run -p 6333:6333 qdrant/qdrant`) + 통합 테스트 검증 완료
- [ ] (배포 시) Qdrant Cloud API key 설정 + URL 전환

## Phase 3: 코어 파이프라인 — Strategy A (Week 1) — ✅ 완료 (2026-03-25)
- [x] `src/pipeline/strategy.py` — PipelineStrategy ABC + StrategyRegistry
- [x] `src/pipeline/confidence.py` — Gap-based confidence (threshold 0.15)
- [x] `src/pipeline/sequential.py` — 진짜 2-Layer (OQ-4 반영)
- [x] `src/pipeline/flat.py` — 1-Layer (E0 비교용)
- [x] 단위 테스트 + 수동 E2E 검증

## Phase 4: Ground Truth (Week 1) — ✅ 완료 (2026-03-25)
- [x] `data/ground_truth/seed_set.jsonl` — 80개 (8 카테고리 x 10개, Easy:Medium:Hard = 4:4:2)
- [x] `src/data/ground_truth.py` — Synthetic GT + Quality Gate
- [x] `scripts/generate_ground_truth.py`
- [x] OpenAI API 키 설정 + 통합 테스트 활성화 (6 skip → 0)
- [x] Synthetic GT 생성 완료 — 838개 (`data/ground_truth/synthetic.jsonl`)
- [x] QualityGate 검증 통과 (난이도 분포 PASS, leakage 실질 위반 0건)
- [x] 검증 스크립트 작성 (`scripts/verify_ground_truth.py`)
- [ ] 파일럿 검증: seed 20개로 파이프라인 테스트 (Phase 5 이후)

## Phase 5: 평가 하네스 (Week 2) — ✅ 완료 (2026-03-26)
- [x] `src/evaluation/evaluator.py` — Evaluator ABC
- [x] Precision@1, Recall@K, MRR, NDCG@5, Confusion Rate, ECE, Latency 구현 (7개 메트릭)
- [x] `src/evaluation/harness.py` — `evaluate(strategy, queries, gt) → Metrics`
- [x] 메트릭 단위 테스트 31개 + 하네스 통합 테스트 9개 (총 40개)

## Phase 6: Reranker (Week 2)
- [x] `src/reranking/base.py`, `cohere_reranker.py`
- [ ] `src/reranking/llm_fallback.py`
- [ ] Sequential + Parallel 전략에 Reranker 연결
- [ ] 단위 테스트

## Phase 7: Hybrid Search + Strategy B (Week 2)
- [ ] `src/retrieval/hybrid.py` — RRF fusion
- [ ] `src/pipeline/parallel.py` — Strategy B
- [ ] 단위 테스트

## Phase 8: FastAPI (Week 2)
- [ ] `src/api/main.py` + `src/api/routes/search.py`
- [ ] 단위 테스트 + curl 수동 테스트

## Phase 9: Provider Analytics (Week 2-3)
- [ ] Query 로거, 로그 집계, GEO Score, A/B 테스트, 유사도 히트맵, Confusion matrix
- [ ] Provider REST endpoints
- [ ] 단위 테스트

## Phase 10: 실험 러너 (Week 3)
- [ ] `src/evaluation/experiment.py` + `scripts/run_experiments.py`
- [ ] W&B 연동 + JSON/CSV 결과 출력

## Phase 11: 인스트루멘테이션 (Week 3)
- [ ] Langfuse 트레이싱 + W&B 대시보드

## Phase 12: E2E 스모크 테스트 (Week 3)
- [ ] 전체 파이프라인 E2E: collect → index → search → evaluate
- [ ] 전체 테스트 스위트 통과

---

## 백로그

> OpenAI API 키 확보 완료 (2026-03-25).

| # | 항목 | 의존 Phase | 우선순위 | 상태 |
|---|------|-----------|---------|------|
| ~~1~~ | ~~`openai_embedder.py` 통합 테스트 활성화 (skip 6개 → 0개)~~ | Phase 2 | ~~높음~~ | **완료** |
| ~~2~~ | ~~Synthetic GT 생성 실행 (`scripts/generate_ground_truth.py`)~~ | Phase 4 | ~~높음~~ | **완료** |
| 3 | 임베딩 인덱스 빌드 (`scripts/build_index.py`) | Phase 2 | 높음 | 대기 |
| 4 | E0 실험: 1-Layer vs 2-Layer 검증 | Phase 5 | 중간 | 대기 |

---

## 실험

### E0: 1-Layer vs 2-Layer 아키텍처 검증 (Week 2 선행)
- [x] `src/pipeline/flat.py` 구현 (100% 커버리지)
- [ ] E0-A/B/C 실행 (1-Layer, 2-Layer Sequential, 2-Layer Parallel)
- [ ] 판정: +5%p 이상 → E1 진행. 결과 CTO 공유

### E1: 전략 비교 (Week 2, E0 후)
- [ ] Sequential (A), Parallel (B) 실행 + 결과 비교
- [ ] 지표: Precision@1, Server Recall@K, Tool Recall@10, MRR, Confusion Rate, Latency

### E2: 임베딩 모델 비교 (Week 3)
- [ ] BGE-M3, OpenAI text-embedding-3-small, OpenAI text-embedding-3-large (MCP-Zero 제공) 비교
- [ ] BGE-M3 sparse 기여도 측정 (Dense-only vs Dense+Sparse)

### E3: Reranker 비교 (Week 3)
- [ ] Cohere Rerank 3, Cohere + LLM fallback (threshold sweep), LLM-as-Judge 비교

### E4: Description A/B — 테제 검증 (Week 4, 핵심)
- [ ] Version A (Poor) vs Version B (Good) 평가
- [ ] McNemar's test, Spearman, OLS Regression R²
- [ ] Evidence Triangulation: 3개 중 2개 이상 통과 여부

### E5: Pool 스케일 (Week 4)
- [ ] Pool 5/20/50/100/200/308에서 Precision@1, Latency, Confusion Rate 측정 (MCP-Zero 활용)

### E6: Pool 유사도 (Week 4)
- [ ] Low/Base/High Similarity Pool에서 Confusion Rate, Precision@1, NDCG@5

### E7: GEO 점수 비교 (OQ-1 해결 후)
- [ ] 휴리스틱 vs LLM vs Description Smells 4D Spearman 비교 + Human agreement (20-30개)

---

## Phase 13: 게이트 기능 (CTO 확인 후)
- [ ] Strategy C: Taxonomy-gated (`src/pipeline/taxonomy_gated.py`)
- [ ] MCP Tool Server (`src/api/mcp_server.py`)
- [ ] A/B Test Qdrant 페이로드 교체 자동화

---

## 최종 제출 (Week 5, 4/17~4/25)
- [ ] 최종 보고서 (Abstract, 실험 설정, E1-E6 결과, Discussion, Provider Analytics 데모)
- [ ] 코드 정리 + README.md
- [ ] **4/26 제출**

---

## CTO 멘토링

### 3/25 첫 세션 의제
- [ ] E1 전략 비교 방향, Strategy C 가치, Cross-Encoder+LLM fallback 현실성
- [ ] GT 최소 규모(80개), 6개 지표 완전성, Gap-based Confidence 적절성

### 이후 세션 (매주 화)
- [ ] 실험 진행 상황 + 지표 해석 + 블로커 논의
