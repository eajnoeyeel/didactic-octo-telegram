# Phase 9-12+: Analytics, Experiments, Instrumentation, E2E, Bridge

> 상위 문서: [implementation.md](implementation.md)

---

## Phase 9: Provider Analytics

### 목표
- 로깅 파이프라인 + Provider REST API + SEO Score + Confusion Matrix + A/B Test runner

### 산출물
- file: `src/analytics/logger.py`
- file: `src/analytics/aggregator.py`
- file: `src/analytics/seo_score.py`
- file: `src/analytics/ab_test.py`
- file: `src/analytics/confusion_matrix.py`
- file: `src/api/routes/provider.py`
- file: `tests/unit/test_analytics.py`
- file: `tests/unit/test_seo_score.py`
- file: `tests/integration/test_provider_api.py`

### 구현 단계

**Task 9.1: Query Logger + Aggregator**
1. 실패 테스트 (`test_analytics.py`): tempdir에 JSONL 기록 > query, selected_tool_id 필드 확인
2. `src/analytics/logger.py`: `QueryLogger(log_dir)` — 일별 JSONL 파일, entry 필드: timestamp, query, selected_tool_id, server_id, confidence, disambiguation_needed, strategy, latency_ms, alternatives
3. `src/analytics/aggregator.py`: `LogAggregator(log_dir)`, `ToolStats` dataclass (selection_count, runner_up_count, lost_to dict), `aggregate(days=7)` → per-tool 통계

**Task 9.2: Description SEO Score + A/B Test**
1. 실패 테스트 (`test_seo_score.py`):
   - vague description ("A tool for doing things.") → total < 0.4
   - specific description (Semantic Scholar 예시, NOT 포함) → total > 0.7
   - score에 specificity, disambiguation, parameter_coverage, total 필드 존재
2. `src/analytics/seo_score.py`:
   - `SEOScore` dataclass: specificity, disambiguation, parameter_coverage, total
   - `DescriptionSEOScorer.score(description)`:
     - specificity (0.4 weight): 문장 수, 예시 포함, 단어 수 기반
     - disambiguation (0.4 weight): NOT/AVOID 키워드 + vs/unlike 비교 표현
     - parameter_coverage (0.2 weight): parameter/input/accepts 언급 여부
3. `src/analytics/ab_test.py`:
   - `ABTestRunner(strategy, indexer)` — description variant A vs B 비교
   - **MVP 제한**: Qdrant payload swap 미구현 (Phase 13에서 완성 예정)
   - `run(tool_id, desc_a, desc_b, test_queries)` → winner, delta
4. `src/analytics/confusion_matrix.py`:
   - `build_confusion_matrix(stats)` → per-tool: selections, runner_up, win_rate, lost_to top-5

**Task 9.3: Provider REST API**
1. 실패 테스트 (`test_provider_api.py`):
   - `GET /provider/{server_id}/stats` → 200
   - `POST /provider/seo-score` → 200, total/specificity 필드
2. `src/api/routes/provider.py`:
   - `GET /{server_id}/stats`: LogAggregator > server 필터 > tool별 selections/win_rate
   - `POST /seo-score`: DescriptionSEOScorer.score() 결과 반환
   - `GET /{server_id}/confusion`: build_confusion_matrix > server 필터
3. `src/api/main.py`에 `provider_router` 등록

### 완료 기준
- [ ] `uv run pytest tests/unit/test_analytics.py tests/unit/test_seo_score.py -v` PASS
- [ ] `uv run pytest tests/integration/test_provider_api.py -v` PASS
- [ ] Provider API 3개 endpoint 동작

### 의존성
- Phase 8 완료 필요 (FastAPI app)
- Phase 5 완료 필요 (PrecisionAt1 for A/B test)

---

## Phase 10: Experiment Runner + Description Correlation

### 목표
- 전략 비교 스크립트 + core thesis metric (Description Quality <> Selection Rate Spearman 상관)

### 산출물
- file: `src/evaluation/experiment.py`
- file: `scripts/run_experiments.py`
- file: `tests/evaluation/test_experiment.py`

### 구현 단계

1. 실패 테스트:
   - `ExperimentConfig(pool_sizes=[5,20], strategies=["sequential"])` 생성 가능
   - `DescriptionQualityCorrelation`: positive correlation (r > 0.8, significant), insufficient data (None)
2. `src/evaluation/experiment.py`:
   - `ExperimentConfig`: pool_sizes, similarity_densities, strategies
   - `ExperimentRunner(ground_truth, config)`:
     - `run_all()`: 각 strategy에 evaluate() 실행 > precision, recall, confusion, latency 수집
     - `print_table()`: Strategy / P@1 / R@10 / Confusion / p95 ms
   - `compute_description_correlation(tools, ground_truth, strategy)`:
     - per-tool SEO score + per-tool Precision@1 계산 > `DescriptionQualityCorrelation.compute()`
3. `scripts/run_experiments.py`:
   - ground_truth 로드 > ExperimentRunner 실행 > 테이블 출력 > `data/experiments/` 저장

### 완료 기준
- [ ] `uv run pytest tests/evaluation/test_experiment.py -v` PASS
- [ ] Spearman 상관 계산 가능 (n >= 3)
- [ ] 커밋: `feat: experiment runner + description quality correlation`

### 의존성
- Phase 5 완료 필요 (evaluation harness)
- Phase 9 완료 필요 (SEO scorer)

---

## Phase 11: Instrumentation (Langfuse + W&B)

### 목표
- 모든 LLM 호출 Langfuse 트레이싱 + 실험 결과 W&B 추적

### 구현 단계
1. `src/api/routes/search.py`: Langfuse trace 추가 (name="find_best_tool", input=query, output=top1/confidence/latency)
2. `scripts/run_experiments.py`: `wandb.init(project="mcp-discovery")` > `wandb.log(r)` > `wandb.finish()`

### 완료 기준
- [ ] Langfuse/W&B 대시보드에서 확인 가능
- [ ] 커밋: `feat: Langfuse LLM tracing + W&B experiment tracking`
- 의존성: Phase 8, 10 완료 필요

---

## Phase 12: End-to-End Smoke Test

### 목표
- 전체 파이프라인 로컬 실행 검증

### 구현 단계

1. `uv run python scripts/collect_data.py` → `data/raw/servers.jsonl` (50+ servers)
2. `uv run python scripts/build_index.py` → Qdrant 인덱스 구축
3. `uv run python scripts/generate_ground_truth.py` → `data/ground_truth/synthetic.jsonl` (200+ queries)
4. `uv run python scripts/run_experiments.py` → Strategy 비교 테이블 출력
5. `uv run pytest --cov=src --cov-report=term-missing -v` → 전체 테스트 PASS
6. 서버 시작 + 수동 curl 테스트:

```bash
uv run uvicorn src.api.main:app --reload
curl -X POST http://localhost:8000/search -H "Content-Type: application/json" \
  -d '{"query": "search for academic papers about transformers", "top_k": 3}'
```

### 완료 기준
- [ ] 데이터 수집 > 인덱싱 > GT 생성 > 실험 실행 전체 흐름 동작
- [ ] 전체 테스트 PASS + 커버리지 리포트
- [ ] 커밋: `feat: end-to-end smoke test passing — MCP Discovery Platform v0.1`

### 의존성
- Phase 0-11 전체 완료 필요

---

## Phase 13: Bridge/Router (Week 3 — find_best_tool 완성 후)

### 목표
- LLM이 우리 MCP만 연결하면 find_best_tool + execute_tool로 Provider MCP 자동 라우팅

### 산출물
- file: `src/bridge/registry.py`
- file: `src/bridge/proxy.py`
- file: `src/bridge/mcp_bridge.py`

### 구현 단계

**Task 13.1: MetaMCP 분석 + Bridge 구축**
1. MetaMCP(metatool-ai/metamcp) 소스 분석: aggregator.py, router.py 흐름 파악
2. `src/bridge/registry.py`:
   - `ProviderEndpoint`: tool_id, server_id, transport (stdio/http), url, command, args
   - `ProviderRegistry`: register(), get(tool_id), load_from_jsonl()
3. `src/bridge/proxy.py`:
   - `execute_via_proxy(tool_id, params, registry)` → ToolResult
   - stdio: MCP Python SDK `ClientSession` + `stdio_client` 사용
   - HTTP transport: Phase 13.2에서 구현 (NotImplementedError)
4. `src/bridge/mcp_bridge.py`:
   - MCP Server "mcp-selection-optimizer" 정의
   - `list_tools()`: find_best_tool, execute_tool 2개 도구 노출
   - `call_tool(name, arguments)`: find_best_tool → StrategyRegistry, execute_tool → execute_via_proxy

**Task 13.2: Provider MCP 통합 테스트**
1. Smithery에서 stdio 지원 Provider 3개 선정 (예: mcp-arxiv, mcp-weather, mcp-filesystem)
2. Claude Desktop 설정: `mcp-selection-optimizer` MCP 서버 등록
3. E2E 검증: "오늘 날씨 어때?" → find_best_tool → execute_tool → 결과 반환
4. 로그 검증: `data/logs/queries.jsonl` 에 기록 확인

### 완료 기준
- [ ] Claude Desktop에서 find_best_tool, execute_tool 두 도구 노출
- [ ] Provider MCP 3개 이상 프록시 호출 성공
- [ ] 커밋: `feat: Bridge/Router — find_best_tool + execute_tool, MetaMCP 기반 프록시`

### 의존성
- Phase 12 완료 필요 (전체 파이프라인 검증 완료 후)
