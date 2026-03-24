# 진행 체크리스트

> 최종 업데이트: 2026-03-22
> 상세 구현 스펙: `docs/plan/implementation.md`
> 타임라인: 2026-03-20 ~ 2026-04-26 (5주)

---

## 해결된 사항

- **OQ-1 (SEO 점수 산정)**: RESOLVED (2026-03-21) — 5-dimension DQS 채택, 동등 가중치 0.2x5, E7 calibration. 상세: `docs/research/description-quality-scoring.md`

---

## 미결 Blockers

### OQ-2: Smithery 크롤링 + Pool 구성 (데이터)
- [ ] Smithery API rate limit 확인
- [ ] 크롤링 범위 결정: 카테고리별 5-10개 균형 수집
- [ ] `tools/list` 직접 연결 가능한 서버 목록 확인
- [ ] 4종 Pool 정의 (Base, High Similarity, Low Similarity, Description Quality)
- [ ] 각 Pool에 포함할 서버 목록 수동 작성

### OQ-3: 자체 MCP 서버 구축 (A/B 실증)
- [ ] mcp-arxiv, mcp-calculator, mcp-korean-news 서버 구현
- [ ] 각 서버 x 2 description 버전 (Version A: Poor, Version B: Good)
- [ ] 실제 `tools/list` 연결 검증

### OQ-4: Sequential 2-Layer 버그 수정
- [ ] `sequential.py`를 진짜 2-Layer로 수정 (서버 인덱스 → 필터 → 툴 검색)
- [ ] Server Classification Error Rate 별도 로깅 추가

### OQ-5: 2-Layer 아키텍처 유효성 검증 (E0 선행)
- [ ] 1-Layer 파이프라인 구현 (`src/pipeline/flat.py`)
- [ ] E0 실행: 1-Layer vs 2-Layer Sequential vs 2-Layer Parallel
- [ ] 판정: Precision@1 +5%p 이상 차이 → 2-Layer 유효
- [ ] CTO 멘토링에서 결과 논의

---

## Phase 0: 프로젝트 기반 (Week 1)
- [ ] `pyproject.toml` + `uv sync --extra dev`
- [ ] `src/config.py` — pydantic-settings
- [ ] `src/models.py` — MCPTool, MCPServer, SearchResult, GroundTruth 등
- [ ] `.env.example` + `git init` + 첫 커밋
- [ ] `tests/unit/test_config.py`, `tests/unit/test_models.py` 통과

## Phase 1: 데이터 수집 (Week 1)
- [ ] `src/data/crawler.py` — SmitheryCrawler
- [ ] `src/data/mcp_connector.py` — Direct MCP 연결
- [ ] `scripts/collect_data.py` → `data/raw/servers.jsonl`
- [ ] 단위 테스트 통과

## Phase 2: 임베딩 + Vector Store (Week 1)
- [ ] `src/embedding/base.py` — Embedder ABC
- [ ] `src/embedding/openai_embedder.py`, `src/embedding/bge_m3.py`
- [ ] `src/retrieval/qdrant_store.py` — Qdrant Cloud wrapper
- [ ] `src/data/indexer.py` + `scripts/build_index.py`
- [ ] Qdrant 로컬 Docker 실행 (`docker run -p 6333:6333 qdrant/qdrant`) + 단위 테스트
- [ ] (배포 시) Qdrant Cloud API key 설정 + URL 전환

## Phase 3: 코어 파이프라인 — Strategy A (Week 1)
- [ ] `src/pipeline/strategy.py` — PipelineStrategy ABC + StrategyRegistry
- [ ] `src/pipeline/confidence.py` — Gap-based confidence (threshold 0.15)
- [ ] `src/pipeline/sequential.py` — 진짜 2-Layer (OQ-4 반영)
- [ ] 단위 테스트 + 수동 E2E 검증

## Phase 4: Ground Truth (Week 1)
- [ ] `data/ground_truth/seed_set.jsonl` — 80개 (8 카테고리 x 10개, Easy:Medium:Hard = 4:4:2)
- [ ] `src/data/ground_truth.py` — Synthetic GT + Quality Gate
- [ ] `scripts/generate_ground_truth.py`
- [ ] 파일럿 검증: seed 20개로 파이프라인 테스트

## Phase 5: 평가 하네스 (Week 2)
- [ ] `src/evaluation/evaluator.py` — Evaluator ABC
- [ ] Precision@1, Recall@K, Latency, Confusion Rate, ECE, Spearman 구현
- [ ] `src/evaluation/harness.py` — `evaluate(strategy, queries, gt) → Metrics`
- [ ] 전체 메트릭 단위 테스트 + E2E 평가 흐름 테스트

## Phase 6: Reranker (Week 2)
- [ ] `src/reranking/base.py`, `cohere_reranker.py`, `llm_fallback.py`
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
- [ ] Query 로거, 로그 집계, SEO 점수, A/B 테스트, 유사도 히트맵, Confusion matrix
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

## 실험

### E0: 1-Layer vs 2-Layer 아키텍처 검증 (Week 2 선행)
- [ ] `src/pipeline/flat.py` 구현
- [ ] E0-A/B/C 실행 (1-Layer, 2-Layer Sequential, 2-Layer Parallel)
- [ ] 판정: +5%p 이상 → E1 진행. 결과 CTO 공유

### E1: 전략 비교 (Week 2, E0 후)
- [ ] Sequential (A), Parallel (B) 실행 + 결과 비교
- [ ] 지표: Precision@1, Server Recall@K, Tool Recall@10, MRR, Confusion Rate, Latency

### E2: 임베딩 모델 비교 (Week 3)
- [ ] BGE-M3, OpenAI text-embedding-3-small, Voyage voyage-3 비교
- [ ] BGE-M3 sparse 기여도 측정 (Dense-only vs Dense+Sparse)

### E3: Reranker 비교 (Week 3)
- [ ] Cohere Rerank 3, Cohere + LLM fallback (threshold sweep), LLM-as-Judge 비교

### E4: Description A/B — 테제 검증 (Week 4, 핵심)
- [ ] Version A (Poor) vs Version B (Good) 평가
- [ ] McNemar's test, Spearman, OLS Regression R²
- [ ] Evidence Triangulation: 3개 중 2개 이상 통과 여부

### E5: Pool 스케일 (Week 4)
- [ ] Pool 5/20/50/100에서 Precision@1, Latency, Confusion Rate 측정

### E6: Pool 유사도 (Week 4)
- [ ] Low/Base/High Similarity Pool에서 Confusion Rate, Precision@1, NDCG@5

### E7: SEO 점수 비교 (OQ-1 해결 후)
- [ ] 휴리스틱 vs LLM Spearman 비교 + Human agreement (20-30개)

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
