# Phase 3-5: Core Pipeline, Ground Truth, Evaluation Harness

> 상위 문서: [implementation.md](implementation.md)

---

## Phase 3: Core Pipeline — Strategy A (Sequential 2-Layer)

### 목표
- `find_best_tool` 동작: sequential search + confidence 분기

### 산출물
- file: `src/pipeline/strategy.py`
- file: `src/pipeline/confidence.py`
- file: `src/pipeline/sequential.py`
- file: `tests/unit/test_confidence.py`
- file: `tests/unit/test_sequential.py`

### 구현 단계

**Task 3.1: PipelineStrategy 인터페이스 + Confidence**
1. 실패 테스트 (`test_confidence.py`):
   - `compute_confidence(0.92, 0.61)` == 0.31
   - `should_disambiguate(0.92, 0.61, threshold=0.15)` is False
   - `should_disambiguate(0.85, 0.82, threshold=0.15)` is True
   - `should_disambiguate(0.90, None, threshold=0.15)` is False (단일 결과)
2. `src/pipeline/confidence.py`:
   - `compute_confidence(rank1, rank2)`: gap = rank1 - rank2 (rank2=None이면 1.0)
   - `should_disambiguate(rank1, rank2, threshold)`: gap < threshold이면 True
3. `src/pipeline/strategy.py`:
   - `PipelineStrategy(ABC)`: `name: str`, `execute(request) -> FindBestToolResponse`
   - `StrategyRegistry`: `register()`, `get(name)` 클래스 메서드

**Task 3.2: Strategy A — Sequential**
1. 실패 테스트 (`test_sequential.py`):
   - mock store/embedder 사용
   - `SequentialStrategy.execute(req)` → response.strategy_used == "sequential", len(results) >= 1
2. `src/pipeline/sequential.py`:
   - Layer 1: embed query > store.search (top_k_retrieval)
   - Layer 2: placeholder (Reranker는 Phase 6에서 주입)
   - Confidence 분기: compute_confidence > should_disambiguate

### 완료 기준
- [ ] `uv run pytest tests/unit/test_confidence.py -v` PASS
- [ ] `uv run pytest tests/unit/test_sequential.py -v` PASS
- [ ] 커밋: `feat: PipelineStrategy interface + gap-based confidence` + `feat: Strategy A — sequential 2-layer pipeline`

### 의존성
- Phase 2 완료 필요 (embedding, qdrant_store)

---

## Phase 4: Ground Truth Generation

### 목표
- `data/ground_truth/` JSONL: (query, server_id, tool_id) triples, 50+ manually verified

### 산출물
- file: `src/data/ground_truth.py`
- file: `tests/unit/test_ground_truth.py`
- file: `scripts/generate_ground_truth.py`

### 구현 단계

1. 실패 테스트 (`test_ground_truth.py`):
   - `parse_queries(raw_output, tool)` → 3개 GroundTruth, correct_tool_id 일치, manually_verified=False
2. `src/data/ground_truth.py`:
   - `QUERY_GEN_PROMPT`: tool_name, description 기반 다양한 쿼리 생성 프롬프트
     - 규칙: 줄당 1개 쿼리, 넘버링 없음, 자연어/약어/크로스도메인 다양성, 모호한 쿼리 포함, 이름 exact match 금지
   - `GroundTruthGenerator(llm_client, model="gpt-4o-mini")`
   - `parse_queries(raw, tool) -> list[GroundTruth]`
   - `generate_for_tool(tool, n=10) -> list[GroundTruth]` (temperature=0.8)
   - `save(ground_truth, output_dir)` → JSONL 형식

### 완료 기준
- [ ] `uv run pytest tests/unit/test_ground_truth.py -v` PASS
- [ ] 커밋: `feat: synthetic ground truth generator`

### 의존성
- Phase 0 완료 필요 (models)

---

## Phase 5: Evaluation Harness

### 목표
- `evaluate(strategy, queries, gt) -> Metrics` — 6개 core metrics 전체 구현

### 산출물
- file: `src/evaluation/evaluator.py`
- file: `src/evaluation/metrics/precision.py`
- file: `src/evaluation/metrics/recall.py`
- file: `src/evaluation/metrics/latency.py`
- file: `src/evaluation/metrics/confusion_rate.py`
- file: `src/evaluation/metrics/description_correlation.py`
- file: `src/evaluation/metrics/calibration.py`
- file: `src/evaluation/harness.py`
- file: `tests/evaluation/test_metrics.py`

### 구현 단계

**Task 5.1: 6개 Core Metrics**

1. 실패 테스트 (`tests/evaluation/test_metrics.py`) — 헬퍼 함수:
   - `make_tool(tool_id)`, `make_response(tool_ids, query, latency_ms)`
2. **Precision@1** (`precision.py`):
   - top-1 tool_id == ground_truth.correct_tool_id 이면 1.0, 아니면 0.0
3. **Recall@K** (`recall.py`):
   - top-K 내 correct_tool_id 존재하면 1.0, 아니면 0.0
4. **Latency** (`latency.py`):
   - `aggregate(responses)` → p50, p95, p99, mean (numpy percentile)
5. **Confusion Rate** (`confusion_rate.py`):
   - top-1 틀렸으나 correct가 top-k에 있으면 1.0 (유사 도구와 혼동)
   - Ref: arxiv:2601.16280
6. **Description Quality Correlation** (`description_correlation.py`):
   - `compute(quality_scores, selection_rates)` → Spearman r, p-value, significant(p<0.05)
   - n < 3이면 None 반환

**Task 5.2: ECE (Calibration) — 6번째 Metric**

1. 실패 테스트:
   - perfect calibration: ECE < 0.2
   - always wrong + high confidence: ECE > 0.5
   - empty input: None
2. `src/evaluation/metrics/calibration.py`:
   - `ECEMetric(n_bins=10)`, Naeini et al. AAAI 2015 기반
   - `ECE = Sum (|B_m|/n) * |acc(B_m) - conf(B_m)|`

**Task 5.3: Evaluation Harness**

1. `src/evaluation/harness.py`:
   - `EvalResult` dataclass: strategy, precision_at_1, recall_at_10, confusion_rate, latency, ece, n_queries, per_query
   - `evaluate(strategy, test_queries, top_k)` → 각 GT에 대해 execute > score > aggregate
   - **주의**: position bias shuffling은 자동 메트릭에 적용하지 않음 (human-judge 전용)

### 완료 기준
- [ ] `uv run pytest tests/evaluation/test_metrics.py -v` PASS (전체 metric 테스트)
- [ ] ECE가 EvalResult에 포함됨
- [ ] 커밋: `feat: evaluation harness — all 6 baseline metrics complete`

### 의존성
- Phase 3 완료 필요 (PipelineStrategy interface)
- Phase 4 완료 필요 (GroundTruth data)
