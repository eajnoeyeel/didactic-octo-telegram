# MCP Discovery Platform — Evaluation Metrics Rubric

> 작성: 2026-03-19
> 근거: `docs/research/evaluation-metrics.md`
> 목적: 모든 실험과 평가에 사용하는 공식 루브릭. Ground Truth 설계, 실험 설계, 코드 스펙이 이 문서를 참조한다.

---

## North Star Metric

**Precision@1** — 최종 추천된 툴 #1이 정답인 비율

| 항목 | 내용 |
| --- | --- |
| 정의 | `correct_count / total_queries` where correct = `results[0].tool_id == ground_truth.correct_tool_id` |
| 데이터 소스 | `evaluate()` harness output, 매 실험 실행마다 자동 계산 |
| 시각화 | 실험별 Bar chart (전략 A vs B vs C), 시간 추이 Line chart |
| 현재 베이스라인 | RAG-MCP 논문: 43.13% (RAG) vs 13.62% (baseline) |
| 초기 목표 | >= 50% (Pool 50, mixed domain) |
| 스트레치 목표 | >= 65% (Pool 100, high similarity) |
| Alert | < 30% on any Pool configuration → 검색 전략 또는 임베딩 모델 재검토 필요 |

**왜 이것이 North Star인가**: `find_best_tool`의 존재 이유. LLM이 한 번에 올바른 Tool을 받는 것이 핵심 가치. 모든 input metric이 이 하나를 끌어올리기 위해 존재한다.

**Ben Yoskovitz 4기준 체크**:
- Understandable: "추천한 것 중 1위가 정답인 비율" — 누구나 이해 가능
- Comparative: 전략 간, 임베딩 모델 간, description 품질 간 비교 가능
- Ratio: 비율 지표
- Behavior-changing: 낮으면 파이프라인 구조를 바꿔야 함

---

## Input Metrics — North Star을 끌어올리는 레버 4개

### 1. Layer 1 Server Recall@K

| 항목 | 내용 |
| --- | --- |
| 정의 | `count(correct_server in top_K_servers) / total_queries` |
| K값 | K=3 (서버 50개 이하), K=5 (서버 50개 이상) |
| 데이터 소스 | Layer 1 검색 결과 독립 로깅 (strategy 내부) |
| 시각화 | 전략별 Grouped bar chart |
| 목표 | >= 90% (K=3). Layer 1이 정답을 놓치면 Layer 2가 복구 불가 |
| Alert | < 80% → 서버 임베딩 품질 문제 또는 서버 description 부족 |
| 논문 근거 | ToolBench/ToolLLM (ICLR 2024) — API Retriever를 Recall@K로 독립 평가 |

**Leading indicator**: Precision@1이 떨어질 때 이 지표를 먼저 본다. Layer 1이 정답 서버를 놓치면 아무리 Reranker가 좋아도 불가능.

**Parallel 전략과의 차이**: Parallel(B)은 서버 인덱스를 독립적으로 검색하므로 동일하게 측정 가능. Sequential(A)에서만 이 지표가 "hard gate" 역할.

---

### 2. Layer 2 Tool Recall@10

| 항목 | 내용 |
| --- | --- |
| 정의 | `count(correct_tool in top_10_tools) / total_queries` |
| 데이터 소스 | Reranker 입력 전 후보 목록 |
| 시각화 | 전략별 Bar chart, Pool 구성별 Heatmap |
| 목표 | >= 85% |
| Alert | < 70% → 임베딩 모델 또는 서버 필터링 문제 |
| 논문 근거 | ToolBench/ToolLLM, MCP-Bench (arxiv:2508.20453) |

**왜 K=10인가**: Reranker (Cohere Rerank 3)에 10개를 넣어 Top-3을 뽑는 구조. 10개 안에 정답이 없으면 Reranker가 복구 불가.

---

### 3. Confusion Rate

| 항목 | 내용 |
| --- | --- |
| 정의 | `count(wrong_rank1 AND correct_in_topK) / count(wrong_rank1)` |
| 데이터 소스 | `evaluate()` harness — Precision@1 오답 케이스 중 분류 |
| 시각화 | Confusion Matrix heatmap (어떤 Tool 쌍에서 혼동 발생하는지), Pie chart (confusion vs miss) |
| 목표 | Confusion / Total Error < 50% (에러의 절반 이상이 confusion이면 description 문제) |
| Alert | 특정 Tool 쌍의 confusion count > 5 → Provider에게 disambiguation 알림 |
| 논문 근거 | ToolScan (arxiv:2411.13547) — 7 error patterns, MetaTool (ICLR 2024) — similar tool confusion subtask |

**왜 중요한가**: 두 실패 유형은 처방이 다르다.
- **Confusion** (정답이 Top-K에 있지만 rank-1이 아님): description disambiguation 개선 → Provider에게 안내
- **Miss** (정답이 Top-K에 없음): 임베딩/검색 전략 자체를 개선

**Provider Analytics와의 연결**: 이 지표가 Provider 대시보드의 "경쟁 분석" 기능의 원천 데이터. "당신의 Tool은 X에게 이 쿼리 유형에서 N번 졌습니다."

---

### 4. Description Quality Score (SEO Score)

| 항목 | 내용 |
| --- | --- |
| 정의 | `weighted_average(specificity, disambiguation, parameter_coverage)` |
| 스코어링 방법 | **미결 (OQ-1)**: 정규식 휴리스틱 vs LLM-based. 파일럿 실험 후 결정 |
| 데이터 소스 | `seo_score.py` (현재) 또는 LLM judge (대안) |
| 시각화 | Tool별 Radar chart (3축), Score 분포 Histogram |
| 목표 | Pool 내 평균 >= 0.6 (1.0 만점) |
| Alert | 측정 불가 — 이 지표 자체의 validity 검증이 선행 필요 (OQ-1) |
| 의존성 | Spearman 상관계수의 입력 변수. 이 점수가 나쁘면 상관분석이 무의미해짐 |

**행동 변화 기준** (Behavior-changing test):
- 이 점수가 높은 Tool이 실제로 더 많이 선택되면 → Provider에게 "이렇게 고치세요" 추천에 신뢰성 부여
- 상관관계가 없으면 → 점수 산정 방식 자체를 교체해야 함

---

## Health Metrics — 시스템이 정상인지 확인하는 가드레일

### 5. ECE (Expected Calibration Error)

| 항목 | 내용 |
| --- | --- |
| 정의 | `Σ (|B_m|/n) × |acc(B_m) - conf(B_m)|` over M bins |
| 데이터 소스 | `confidence` field + `precision@1` per query |
| 시각화 | Reliability diagram (expected accuracy vs actual accuracy per bin) |
| 목표 | ECE < 0.15 |
| Alert | ECE > 0.25 → gap-based confidence 분기(DP6)가 신뢰할 수 없다는 의미 |
| 논문 근거 | Naeini et al., AAAI 2015 |

**왜 Health인가**: Precision@1을 직접 올리지는 않지만, ECE가 나쁘면 confidence 분기의 "Top-1 vs Top-3 + 힌트" 판단이 틀린다. 시스템이 정상 작동한다는 전제 조건.

---

### 6. Latency p50 / p95 / p99

| 항목 | 내용 |
| --- | --- |
| 정의 | 각 레이어 + 전체 파이프라인의 백분위 응답 시간 (ms) |
| 측정 포인트 | Layer 1 검색, Layer 2 검색, Reranker (Cohere API), 전체 E2E |
| 데이터 소스 | `time.perf_counter()` in strategy, Langfuse trace spans |
| 시각화 | Layer별 Stacked bar chart, p50/p95/p99 Line chart over experiments |
| 목표 | E2E p95 < 2000ms (로컬), p95 < 3000ms (Lambda) |
| Alert | p99 > 5000ms → Reranker 병목 또는 Qdrant Cloud 연결 문제 |
| 논문 근거 | JSPLIT (arxiv:2510.14537) |

---

### 7. Server Classification Error Rate

| 항목 | 내용 |
| --- | --- |
| 정의 | `1 - Server Recall@K` = 정답 서버가 Top-K에서 빠진 비율 |
| 데이터 소스 | Layer 1 검색 결과 |
| 시각화 | Number widget (현재 값), Trend sparkline |
| 목표 | < 10% (K=3) |
| Alert | > 20% → Sequential 전략의 Layer 1 cutoff가 너무 공격적 |

**진단 용도**: Precision@1이 낮을 때 "Layer 1 문제인가, Layer 2 문제인가" 분리. Sequential vs Parallel 전략 비교 시 이 지표 차이가 핵심.

---

## Provider / Business Metrics — 프로젝트 테제 증명 (Evidence Triangulation)

> **변경 이력 (2026-03-19)**: 기존 단일 Spearman 지표를 3중 증거 체계로 교체.
> **이유**: Spearman 상관계수만으로는 인과 관계를 증명할 수 없다. ToolTweak(arxiv:2510.02554)도 실제로는 직접적 selection rate 조작(A/B)을 사용했지 Spearman이 아니었다. 프로젝트 테제("description 품질 → 선택률")를 입증하려면 인과적(causal), 상관적(correlational), 설명적(explanatory) 증거가 모두 필요하다.

### 8a. A/B Selection Rate Lift (Primary Evidence — Causal)

| 항목 | 내용 |
| --- | --- |
| 정의 | `lift = (precision_B - precision_A) / precision_A × 100%` |
| 설계 | 자체 MCP 서버의 Version A (Poor description) vs Version B (Good description) |
| 데이터 소스 | 동일 쿼리셋을 Pool A/B에 실행한 Precision@1 |
| 시각화 | Paired bar chart (Version A vs B per server), Lift % badge |
| 목표 | lift > 30%, p < 0.05 (McNemar's test) |
| Alert | lift < 10% OR p > 0.1 → description 차이가 불충분하거나, 다른 요인이 지배적 |
| 논문 근거 | ToolTweak (arxiv:2510.02554) — 직접적 description 조작으로 20%→81% 선택률 변화 관찰 |

**왜 Primary인가**: 인과 관계의 가장 직접적 증거. 다른 조건을 모두 고정하고 description만 변경했으므로 `Δselection_rate`가 description 품질의 인과적 효과.

---

### 8b. Spearman(Description Quality, Selection Rate) (Secondary Evidence — Correlational)

| 항목 | 내용 |
| --- | --- |
| 정의 | `scipy.stats.spearmanr(quality_scores, precision_per_tool)` |
| 데이터 소스 | SEO score (metric #4) × Precision@1 per tool (metric NSM 집계) — **Pool 전체 Tool 대상** |
| 시각화 | Scatter plot (quality vs selection rate) + regression line, Correlation coefficient badge |
| 목표 | r_s > 0.6, p < 0.05 |
| Alert | r_s < 0.3 OR p > 0.1 → SEO 점수 산정 방식 교체 필요 (OQ-1) |
| 논문 근거 | Spearman rank correlation은 IR 분야 표준 연관 분석 도구 |

**왜 Secondary인가**: A/B는 자체 서버 3개에서만 측정하므로 범위가 좁다. Spearman은 Pool 전체의 관측적 상관을 보여줌으로써 **일반화 가능성**을 보여준다. 단, 상관 ≠ 인과이므로 Spearman만으로는 테제를 증명할 수 없다.

---

### 8c. Regression R² (Supplementary Evidence — Explanatory)

| 항목 | 내용 |
| --- | --- |
| 정의 | `OLS(selection_rate ~ specificity + disambiguation + param_coverage + negative_instruction).R²` |
| 데이터 소스 | SEO score 하위 요소별 점수 × Precision@1 per tool |
| 시각화 | Coefficient bar chart (각 요소의 기여도), R² badge |
| 목표 | R² > 0.4, 최소 1개 요소의 coefficient p < 0.05 |
| Alert | R² < 0.2 → quality score 하위 요소가 selection rate를 설명하지 못함 |
| 논문 근거 | 다변량 회귀 분석 — 어떤 quality 요소가 selection에 가장 기여하는지 분해 |

**왜 Supplementary인가**: "description 품질이 선택률에 영향을 미친다"(8a에서 증명)를 넘어, **어떤 품질 요소가 가장 중요한지** 분해. Provider에게 "구체적으로 specificity를 높이세요" 같은 actionable 피드백의 근거.

---

### Evidence Triangulation 종합

| 증거 유형 | 메서드 | 질문 | 목표 | 성격 |
|-----------|--------|------|------|------|
| **Primary** | A/B Lift (#8a) | "Good description이 실제로 선택률을 높이는가?" | lift > 30%, p < 0.05 | Causal |
| **Secondary** | Spearman (#8b) | "전체 Tool에서 품질과 선택률이 상관있는가?" | r > 0.6, p < 0.05 | Correlational |
| **Supplementary** | Regression R² (#8c) | "어떤 품질 요소가 가장 중요한가?" | R² > 0.4 | Explanatory |

**테제 증명 판정 기준**:
- 3개 모두 통과 → **강한 증거** (논문/보고서에서 "description 품질이 선택률을 인과적으로 개선한다" 주장 가능)
- Primary + 1개 → **보통 증거** (인과는 확인, 일반화 또는 분해 중 하나 미달)
- Primary만 통과 → **약한 증거** (범위가 좁지만 방향은 맞음)
- Primary 미통과 → **테제 기각** (description 품질이 선택률을 유의미하게 변화시키지 못함)

**이 프로젝트에서 가장 중요한 "비즈니스" 지표**: Provider Analytics의 존재 근거. Evidence triangulation이 "강한 증거" 이상이면 "description을 이렇게 고치면 더 많이 선택됩니다"가 데이터에 기반한 진짜 제안이 됨. 기각되면 Provider 기능 전체의 가치를 재검토해야 함.

---

### 9. Pass Rate (자체 MCP 서버 한정)

| 항목 | 내용 |
| --- | --- |
| 정의 | `count(query → tool selected → execution success) / total_queries` |
| 적용 범위 | 직접 만드는 MCP 서버 (mcp-arxiv, mcp-calculator, mcp-korean-news)에 대해서만 측정 |
| 데이터 소스 | 실제 MCP 서버 실행 로그 |
| 시각화 | 서버별 Bar chart |
| 목표 | >= 70% (자체 서버) |
| Alert | < 50% → 파라미터 매핑 또는 서버 안정성 문제 |
| 논문 근거 | ToolBench (ICLR 2024), StableToolBench (ACL 2024) — Solvable Pass Rate |

---

### 10. NDCG@5 (Ranked List Quality)

| 항목 | 내용 |
| --- | --- |
| 정의 | `DCG@5 / IDCG@5`, where `DCG@5 = Σ rel_i / log₂(i+1)` |
| 데이터 소스 | 전체 Top-5 결과 + relevance grading (binary or graded) |
| 시각화 | 전략별 Box plot (분포 확인) |
| 목표 | >= 0.70 |
| Alert | < 0.50 → 랭킹 품질 전반 문제 |
| 논문 근거 | TREC IR 표준, ToolBench 계열 공통 reporting |

**Precision@1과의 보완 관계**: Precision@1은 1위만 본다. NDCG@5는 disambiguation 케이스(Top-3 반환)에서 순위 전체 품질을 본다. DP6 동적 분기의 효과를 측정하려면 NDCG@5가 필수.

---

### 11. MRR (Mean Reciprocal Rank, 서버 레벨)

| 항목 | 내용 |
| --- | --- |
| 정의 | `(1/|Q|) × Σ (1/rank_i)` where rank_i = 정답 서버의 순위 |
| 데이터 소스 | Layer 1 검색 결과 |
| 시각화 | 전략별 Bar chart |
| 목표 | >= 0.80 |
| Alert | < 0.60 → 서버 임베딩 또는 서버 description 품질 문제 |
| 논문 근거 | Voorhees (TREC-8 QA, 1999) |

---

## Dashboard Layout

```text
┌──────────────────────────────────────────────────────────────────┐
│  NORTH STAR: Precision@1 — [current]%                            │
│  vs baseline: [↑/↓ X%]  |  by strategy: [A: X% | B: Y% | C: Z%]│
├────────────────────┬────────────────────┬────────────────────────┤
│  INPUT 1           │  INPUT 2           │  INPUT 3               │
│  Server Recall@K   │  Tool Recall@10    │  Confusion Rate        │
│  [sparkline]       │  [sparkline]       │  [pie: confuse vs miss]│
│  Target: >=90%     │  Target: >=85%     │  Target: <50% of errs  │
├────────────────────┴────────────────────┼────────────────────────┤
│  INPUT 4                                │  HEALTH                │
│  Description Quality Score              │  ECE / Latency p95 /   │
│  [histogram: score distribution]        │  Server Error Rate     │
│  OQ-1 미결                               │  [sparklines]          │
├─────────────────────────────────────────┴────────────────────────┤
│  EVIDENCE TRIANGULATION (프로젝트 테제 증명)                        │
│  8a. A/B Lift [paired bar]  │  8b. Spearman [scatter]  │  8c. R² │
│  Target: >30%               │  Target: r>0.6           │  >0.4   │
├──────────────────────────────────────────────────────────────────┤
│  SECONDARY: NDCG@5 [box plot]  |  MRR [bar]  |  Pass Rate [bar] │
└──────────────────────────────────────────────────────────────────┘
```

---

## Leading vs Lagging Classification

| 지표 | 유형 | 근거 |
| --- | --- | --- |
| Server Recall@K | Leading | Layer 1이 나빠지면 Precision@1이 나빠질 것을 예측 |
| Tool Recall@10 | Leading | Reranker 입력 품질 → Precision@1 예측 |
| Confusion Rate | Leading | confusion 비율이 높아지면 description 품질 문제를 예측 |
| Description Quality Score | Leading | 점수가 낮으면 Selection Rate가 낮을 것을 예측 |
| ECE | Leading | calibration 나빠지면 confidence 분기 오류 예측 |
| Precision@1 | Lagging | 파이프라인 전체 결과의 사후 측정 |
| Pass Rate | Lagging | 실제 태스크 성공의 사후 측정 |
| A/B Selection Rate Lift | Lagging | E4 실험 완료 후에만 측정 가능 |
| Spearman correlation | Lagging | 충분한 데이터 축적 후에만 계산 가능 |
| Regression R² | Lagging | A/B + Spearman 이후 심화 분석 |

---

## Review Cadence

| 주기 | 대상 | 행동 |
| --- | --- | --- |
| **매 실험 (즉시)** | Precision@1, Recall@K, Latency, Confusion Rate | W&B에 자동 기록. 전략 비교 즉시 가능 |
| **주 1회** | NDCG@5, MRR, ECE, Server Error Rate | 실험 배치 종합 비교. 추세 확인 |
| **2주 1회** | Evidence Triangulation (8a/8b/8c), Pass Rate | 데이터 충분히 쌓인 후 측정. Provider 기능 방향 점검 |
| **CTO 멘토링 (매주 화)** | 전체 대시보드 스냅샷 | 진행 상황 보고. 지표 해석에 대한 피드백 수집 |
| **4/26 제출 전** | 전체 지표 최종 스냅샷 | 최종 보고서용 |

---

## Alert Thresholds Summary

| 지표 | 정상 | 주의 | 위험 | 대응 |
| --- | --- | --- | --- | --- |
| Precision@1 | >= 50% | 30-50% | < 30% | 검색 전략 또는 임베딩 모델 재검토 |
| Server Recall@K | >= 90% | 80-90% | < 80% | 서버 임베딩 품질 점검 |
| Tool Recall@10 | >= 85% | 70-85% | < 70% | 임베딩 모델 또는 서버 필터링 점검 |
| Confusion Rate | < 50% | 50-70% | > 70% | Description disambiguation 필요 |
| ECE | < 0.15 | 0.15-0.25 | > 0.25 | Confidence 분기 로직 재검토 |
| Latency p95 | < 2s | 2-5s | > 5s | Reranker 병목 또는 Qdrant 연결 점검 |
| A/B Lift | > 30% | 10-30% | < 10% | Description 차이 불충분 또는 다른 요인 지배 |
| Spearman r_s | > 0.6 | 0.3-0.6 | < 0.3 | SEO 점수 산정 방식 교체 (OQ-1) |
| Regression R² | > 0.4 | 0.2-0.4 | < 0.2 | Quality 하위 요소가 selection을 설명 못함 |

---

## Tooling

| 용도 | 도구 | 이유 |
| --- | --- | --- |
| 실험 결과 추적 | **Weights & Biases** | 실험별 지표 비교, hyperparameter sweep, 시각화 자동 |
| LLM call 추적 | **Langfuse** | Reranker LLM fallback 비용, 응답 시간 모니터링 |
| 대시보드 | **W&B Dashboard** (개발 중), **FastAPI + 간단 HTML** (데모용) | CTO 데모 시 실시간 지표 표시 |
| 실험 코드 | Custom Python harness (`src/evaluation/`) | ToolBench/RAGAS 참고하되 2-Layer + Provider 특수 지표는 직접 구현 |

---

## Ground Truth 레이블이 이 루브릭을 지원하려면 필요한 필드

> 이 요구사항은 #2 Ground Truth 구조 설계의 입력 조건이 된다.

| 필드 | 필요한 지표 | 예시 |
| --- | --- | --- |
| `query` | 모든 지표 | "find papers about transformers" |
| `correct_server_id` | Server Recall@K, MRR, Server Error Rate | "semantic_scholar" |
| `correct_tool_id` | Precision@1, Tool Recall@10, NDCG@5, Confusion Rate | "semantic_scholar/search_papers" |
| `difficulty` | 난이도별 성능 분석 | "easy" / "medium" / "hard" |
| `category` | 도메인별 성능 분석, Taxonomy-gated 전략 평가 | "search" / "code" / "database" |
| `relevance_grade` (optional) | NDCG (graded relevance 필요 시) | 0 (무관) / 1 (부분 관련) / 2 (정답) |
| `manually_verified` | seed set 구분 | true / false |
| `ambiguity` | 쿼리 모호도별 분석 | "low" / "medium" / "high" |

---

## 지표 간 인과 관계 (Metric Tree)

```text
                    Precision@1 (NSM)
                   /        |        \
         Server           Tool         Confusion
         Recall@K      Recall@10        Rate
            |              |              |
         MRR          NDCG@5        Description
            |              |         Quality Score
      Server Error      Latency          |
         Rate              |      Evidence Triangulation
                          ECE      /        |        \
                              A/B Lift   Spearman    R²
                              (8a)       (8b)       (8c)
                                           |
                                       Pass Rate
```

- 위로 갈수록 lagging, 아래로 갈수록 leading
- 왼쪽 브랜치 = 검색 품질 (파이프라인 엔지니어링)
- 가운데 = 시스템 건강
- 오른쪽 브랜치 = Provider 가치 증명 (프로젝트 테제, evidence triangulation)

---

## 다음 단계

이 루브릭을 기반으로:

1. **#2 Ground Truth 구조 설계** — 위 "필요한 필드" 섹션이 입력 조건 → `docs/evaluation/ground-truth-design.md` ✅ (data 디렉토리: `data/ground_truth/`)
2. **#3 실험 설계** — 위 alert threshold + 전략 비교 매트릭스가 실험 목표 → `docs/evaluation/experiment-design.md` ✅
3. **#4 코드 스펙** — 위 "정의" 컬럼이 각 Evaluator 클래스의 스펙 → 구현 계획 업데이트 대기
