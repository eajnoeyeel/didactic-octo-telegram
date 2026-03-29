# Evaluation Metrics Rubric — 11개 지표 정의

> 최종 업데이트: 2026-03-29
> 대시보드/모니터링: `./metrics-dashboard.md`

---

## North Star Metric

### Precision@1

- **정의**: `correct_count / total_queries` (results[0].tool_id == ground_truth.correct_tool_id)
- **데이터 소스**: `evaluate()` harness output, 매 실험 자동 계산
- **시각화**: 실험별 Bar chart (전략 A vs B vs C), 시간 추이 Line chart
- **베이스라인**: RAG-MCP 논문: 43.13% (RAG) vs 13.62% (baseline)
- **초기 목표**: >= 50% (Pool 50, mixed domain)
- **스트레치 목표**: >= 65% (Pool 100, high similarity)
- **Alert**: < 30% → 검색 전략 또는 임베딩 모델 재검토

> `find_best_tool`의 존재 이유. LLM이 한 번에 올바른 Tool을 받는 것이 핵심 가치.

**Ben Yoskovitz 4기준 체크**:
- Understandable: "추천한 것 중 1위가 정답인 비율" — 누구나 이해 가능
- Comparative: 전략 간, 임베딩 모델 간, description 품질 간 비교 가능
- Ratio: 비율 지표
- Behavior-changing: 낮으면 파이프라인 구조를 바꿔야 함

---

## Input Metrics — North Star을 끌어올리는 레버

### 1. Server Recall@K

- **정의**: `count(correct_server in top_K_servers) / total_queries`
- **K값**: K=3 (서버 50개 이하), K=5 (서버 50개 이상)
- **목표**: >= 90% (K값 규칙에 따름: 서버 ≤50이면 K=3, >50이면 K=5)
- **Alert**: < 80% → 서버 임베딩 품질 문제 또는 서버 description 부족
- **논문 근거**: ToolBench/ToolLLM (ICLR 2024)
- **역할**: Leading indicator. Precision@1이 떨어질 때 이 지표를 먼저 확인. Sequential(A)에서 hard gate 역할

### 2. Tool Recall@10

- **정의**: `count(correct_tool in top_10_tools) / total_queries`
- **데이터 소스**: Reranker 입력 전 후보 목록
- **목표**: >= 85%
- **Alert**: < 70% → 임베딩 모델 또는 서버 필터링 문제
- **논문 근거**: ToolBench/ToolLLM, MCP-Bench (arxiv:2508.20453)
- **K=10 이유**: Reranker(Cohere Rerank 3)에 10개 입력 → Top-3 선출. 10개 안에 정답 없으면 복구 불가

### 3. Confusion Rate

- **정의**: `count(wrong_rank1 AND correct_in_topK) / count(wrong_rank1)`
- **데이터 소스**: `evaluate()` harness — Precision@1 오답 케이스 분류
- **목표**: Confusion / Total Error < 50%
- **Alert**: 특정 Tool 쌍 confusion count > 5 → Provider에게 disambiguation 알림
- **논문 근거**: ToolScan (arxiv:2411.13547), MetaTool (ICLR 2024)
- **두 실패 유형**:
  - **Confusion** (정답이 Top-K에 있지만 rank-1 아님): description disambiguation 개선 → Provider 안내
  - **Miss** (정답이 Top-K에 없음): 임베딩/검색 전략 자체 개선
- **Provider 연결**: Provider 대시보드 "경쟁 분석" 기능의 원천 데이터

### 4. Description Quality Score (GEO Score)

- **정의**: `GEO_score = (1/6) × (clarity + disambiguation + parameter_coverage + boundary + stats + precision)`
- **6개 차원**:

  | 차원 | 기존 명칭 | 내용 | GEO 근거 |
  |------|-----------|------|----------|
  | `clarity_score` | specificity_score | 첫 문장의 핵심 기능 명확도 + 구체적 범위 | Fluency Optimization |
  | `disambiguation_score` | — | 유사 도구와의 차별화 | — |
  | `parameter_coverage_score` | — | 파라미터 타입/제약/예제 포함 여부 | — |
  | `boundary_score` | negative_instruction_score | 이 도구가 NOT 하는 것 명확화 | — |
  | `stats_score` | *(신규)* | 수치/커버리지/성능 정보 포함 여부 | Statistics Addition |
  | `precision_score` | *(신규)* | 표준/프로토콜/기술 용어 정확도 | Technical Terms |

- **스코어링 방법**: E7 파일럿에서 정규식 휴리스틱 vs LLM-based vs Description Smells 4D 비교 후 결정
- **목표**: Pool 내 평균 >= 0.6 (1.0 만점)
- **의존성**: Spearman 상관계수의 입력 변수. 이 점수가 나쁘면 상관분석 무의미
- **행동 변화 기준**: 점수 높은 Tool이 실제로 더 많이 선택되면 → Provider 추천에 신뢰성 부여. 상관 없으면 → 점수 산정 방식 교체

**GEO 6D ↔ Description Smells 4D 매핑 테이블** (E7 비교용):

> Description Smells 논문 (arxiv:2602.18914): description 품질 → 선택률 인과 관계 검증 완료 (+11.6%, p<0.001).
> 4차원 18카테고리 smell 분류. 우리 차별점: smell 유무 비교가 아닌 GEO 기법으로 체계적 개선 방법론 제시.

| GEO 6D 차원 | Description Smells 4D 매핑 | 비고 |
|-------------|--------------------------|------|
| `clarity_score` | Accuracy + Functionality | 핵심 기능 명확도 |
| `disambiguation_score` | — (GEO 고유) | 유사 도구 차별화 |
| `parameter_coverage_score` | Completeness | 파라미터/제약 포함 |
| `boundary_score` | — (GEO 고유) | NOT 할 것 명확화 |
| `stats_score` | Completeness | 수치/커버리지 정보 |
| `precision_score` | Accuracy | 기술 용어 정확도 |
| — | Conciseness (Smells 고유) | 불필요한 장황함 탐지 |

E7에서 3축 비교: GEO 6D vs Description Smells 4D vs 통합 모델

---

## Health Metrics — 시스템 가드레일

### 5. ECE (Expected Calibration Error)

- **정의**: `Sum (|B_m|/n) * |acc(B_m) - conf(B_m)|` over M bins
- **데이터 소스**: `confidence` field + `precision@1` per query
- **시각화**: Reliability diagram (expected vs actual accuracy per bin)
- **목표**: ECE < 0.15
- **Alert**: ECE > 0.25 → gap-based confidence 분기(DP6)가 신뢰 불가
- **논문 근거**: Naeini et al., AAAI 2015

### 6. Latency p50 / p95 / p99

- **정의**: 각 레이어 + 전체 파이프라인의 백분위 응답 시간 (ms)
- **측정 포인트**: Layer 1 검색, Layer 2 검색, Reranker (Cohere API), 전체 E2E
- **데이터 소스**: `time.perf_counter()` in strategy, Langfuse trace spans
- **목표**: E2E p95 < 2000ms (로컬), p95 < 3000ms (Lambda)
- **Alert**: p99 > 5000ms → Reranker 병목 또는 Qdrant Cloud 연결 문제

### 7. Server Classification Error Rate

- **정의**: `1 - Server Recall@K` = 정답 서버가 Top-K에서 빠진 비율
- **목표**: < 10% (K값 규칙에 따름: 서버 ≤50이면 K=3, >50이면 K=5)
- **Alert**: > 20% → Sequential 전략의 Layer 1 cutoff가 너무 공격적
- **진단 용도**: Precision@1 낮을 때 "Layer 1 문제 vs Layer 2 문제" 분리

---

## Provider / Business Metrics — 테제 증명 (Evidence Triangulation)

### 8a. A/B Selection Rate Lift (Primary — Causal)

- **정의**: `lift = (precision_B - precision_A) / precision_A * 100%`
- **설계**: 자체 MCP 서버 Version A (Poor) vs Version B (Good)
- **목표**: lift > 30%, p < 0.05 (McNemar's test)
- **Alert**: lift < 10% OR p > 0.1
- **논문 근거**: ToolTweak (arxiv:2510.02554) — 20%→81% 선택률 변화

### 8b. Spearman (Secondary — Correlational)

- **정의**: `scipy.stats.spearmanr(quality_scores, precision_per_tool)`
- **데이터 소스**: GEO score (#4) x Precision@1 per tool — Pool 전체 Tool 대상
- **목표**: r_s > 0.6, p < 0.05
- **Alert**: r_s < 0.3 OR p > 0.1 → GEO 점수 산정 방식 교체 (OQ-1)

### 8c. Regression R-squared (Supplementary — Explanatory)

- **정의**: `OLS(selection_rate ~ clarity + disambiguation + parameter_coverage + boundary + stats + precision).R²`
- **목표**: R-squared > 0.4, 최소 1개 요소 coefficient p < 0.05
- **Alert**: R-squared < 0.2 → quality 하위 요소가 selection rate 설명 불가

### Evidence Triangulation 판정 기준

| 결과 | 판정 |
|------|------|
| 3개 모두 통과 | **강한 증거** — "description 품질이 선택률을 인과적으로 개선" 주장 가능 |
| Primary + 1개 | **보통 증거** — 인과 확인, 일반화/분해 중 하나 미달 |
| Primary만 통과 | **약한 증거** — 범위 좁지만 방향은 맞음 |
| Primary 미통과 | **테제 기각** — Provider 기능 전체 가치 재검토 |

---

## Secondary Metrics

### 9. Pass Rate (자체 MCP 서버 한정)

- **정의**: `count(query → tool selected → execution success) / total_queries`
- **적용 범위**: 자체 서버 (mcp-arxiv, mcp-calculator, mcp-korean-news)만
- **목표**: >= 70%
- **Alert**: < 50% → 파라미터 매핑 또는 서버 안정성 문제

### 10. NDCG@5

- **정의**: `DCG@5 / IDCG@5`, DCG@5 = Sum rel_i / log2(i+1)
- **목표**: >= 0.70
- **Alert**: < 0.50
- **Precision@1 보완**: disambiguation 케이스(Top-3 반환)에서 순위 전체 품질 측정. DP6 동적 분기 효과 필수 지표

### 11. MRR (Tool 레벨)

- **정의**: `(1/|Q|) * Sum (1/rank_i)` (rank_i = 정답 tool의 검색 결과 내 순위)
- **목표**: >= 0.80
- **Alert**: < 0.60 → 서버 임베딩 또는 서버 description 품질 문제
- **논문 근거**: Voorhees (TREC-8 QA, 1999)

---

## GT 레이블 필수 필드

| 필드 | 지원 지표 |
|------|----------|
| `query` | 모든 지표 입력 |
| `correct_server_id` | Server Recall@K, MRR, Server Error Rate |
| `correct_tool_id` | Precision@1, Tool Recall@10, NDCG@5, Confusion Rate |
| `difficulty` | 난이도별 Precision@1 분석 |
| `category` | 도메인별 분석, Taxonomy-gated 평가 |
| `alternative_tools` | NDCG graded relevance (correct_tool=2, alternative=1, else=0) |
| `manually_verified` | seed vs synthetic 구분 |
| `ambiguity` | 모호도별 분석 |
