# 실험 설계 — MCP Discovery Platform

> 작성: 2026-03-19
> 입력 조건: `docs/evaluation/metrics-rubric.md`, `docs/evaluation/ground-truth-design.md`, `docs/discovery/open-questions.md`
> 목적: 통제 변인 × 전략 × 지표를 조합한 실험 매트릭스와 자동화 요건 정의

---

## 1. 실험 목적

이 프로젝트의 실험은 세 가지 질문에 답하기 위해 설계된다:

1. **어떤 검색 전략이 최적인가?** — Sequential vs Parallel vs Taxonomy-gated
2. **어떤 임베딩 모델이 최적인가?** — BGE-M3 vs OpenAI text-embedding-3-small vs Voyage voyage-3
3. **description 품질이 선택률에 인과적 영향을 미치는가?** — 프로젝트 핵심 테제

---

## 2. 통제 변인 설계

### 독립 변인 (Manipulated Variables)

| 변인 | 수준 | 설명 |
|------|------|------|
| **검색 전략** | Sequential (A), Parallel (B), Taxonomy-gated (C) | `PipelineStrategy` 구현체 교체 |
| **임베딩 모델** | BGE-M3, OpenAI text-embedding-3-small, Voyage voyage-3 | 인덱스 빌드 시 교체 |
| **Reranker** | Cohere Rerank 3 단독, Cohere + LLM fallback, LLM-as-Judge 단독 | Reranker 구현체 교체 |
| **Description 품질** | Version A (Poor), Version B (Good) | 자체 MCP 서버 A/B pair |
| **Tool Pool 크기** | 5, 20, 50, 100 서버 | `build_index.py --pool-size` |
| **Tool Pool 유사도** | Low, Base, High similarity | Pool 정의 파일 교체 |

### 종속 변인 (Measured Variables)

루브릭의 11개 지표 전부. 실험 유형에 따라 primary metric이 다름:

| 실험 유형 | Primary Metric | Secondary Metrics |
|-----------|---------------|-------------------|
| 전략 비교 | Precision@1 | Recall@K, Latency p95, Confusion Rate |
| 임베딩 비교 | Tool Recall@10 | Precision@1, Latency, cold start time |
| Reranker 비교 | Precision@1 향상폭 | Latency 증가폭, 비용 |
| Description A/B | Selection Rate Lift | Spearman r, Regression R² |
| Pool 스케일 | Precision@1 저하율 | Latency 증가율, Confusion Rate |

### 통제 변인 (Controlled Variables)

한 실험에서 하나의 독립변인만 변경. 나머지는 고정:

| 변인 | 고정값 (기본) |
|------|-------------|
| Ground Truth | seed_set.jsonl + synthetic.jsonl (동일 셋) |
| Query 순서 | 동일 (Position bias는 별도 실험) |
| Reranker Top-K | K=10 (Reranker 비교 실험 제외) |
| Confidence 임계값 | gap > 0.15 (Confidence 실험 제외) |
| 실행 환경 | 동일 머신, 동일 Python 3.12 환경 |

---

## 3. 실험 매트릭스

### Experiment 1: 검색 전략 비교 (핵심 실험)

| 조건 | 전략 | 임베딩 | Reranker | Pool |
|------|------|--------|----------|------|
| E1-A | Sequential | BGE-M3 | Cohere | Base (50) |
| E1-B | Parallel (RRF) | BGE-M3 | Cohere | Base (50) |
| E1-C | Taxonomy-gated | BGE-M3 | Cohere | Base (50) |

**측정**: Precision@1, Server Recall@K, Tool Recall@10, MRR, NDCG@5, Confusion Rate, Latency (p50/p95/p99)

**특수 측정 (Sequential만)**: Server Classification Error Rate — Layer 1에서 정답 서버가 빠진 비율 별도 로깅

**CLI**:
```bash
python run_experiments.py --experiment E1 --strategy sequential --pool base
python run_experiments.py --experiment E1 --strategy parallel --pool base
python run_experiments.py --experiment E1 --strategy taxonomy --pool base
```

---

### Experiment 2: 임베딩 모델 비교

| 조건 | 전략 | 임베딩 | Reranker | Pool |
|------|------|--------|----------|------|
| E2-A | (E1 최적) | BGE-M3 | Cohere | Base (50) |
| E2-B | (E1 최적) | OpenAI text-embedding-3-small | Cohere | Base (50) |
| E2-C | (E1 최적) | Voyage voyage-3 | Cohere | Base (50) |

**E1 결과에 의존**: E1에서 최적 전략이 결정된 후 그 전략을 고정하고 임베딩만 교체.

**측정**: Tool Recall@10 (primary), Precision@1, Latency, 비용 (API call 수 × 단가)

**추가 측정**:
- Cold start time: 인덱스 빌드 시간
- 인덱스 크기: 디스크 용량
- BGE-M3의 sparse 컴포넌트 기여도 (Dense-only vs Dense+Sparse 비교)

---

### Experiment 3: Reranker 비교

| 조건 | 전략 | 임베딩 | Reranker | Pool |
|------|------|--------|----------|------|
| E3-A | (E1 최적) | (E2 최적) | Cohere Rerank 3 단독 | Base (50) |
| E3-B | (E1 최적) | (E2 최적) | Cohere + LLM fallback (gap < threshold) | Base (50) |
| E3-C | (E1 최적) | (E2 최적) | LLM-as-Judge 단독 | Base (50) |

**측정**: Precision@1 향상폭 (vs no-reranker baseline), Latency 증가, 비용

**Confidence 분기 최적화 (E3-B 세부)**:
```
threshold 후보: [0.05, 0.10, 0.15, 0.20, 0.25]
각 threshold에서 → LLM fallback 발동 비율, Precision@1, ECE 측정
→ "비용 대비 정확도 향상"이 최적인 threshold 선택
```

---

### Experiment 4: Description 품질 → 선택률 인과 관계 (테제 검증)

**이 프로젝트에서 가장 중요한 실험.**

#### 4-1. A/B Selection Rate Lift (Primary Evidence — Causal)

| 조건 | Pool 구성 | Description 버전 |
|------|----------|-----------------|
| E4-A | Base Pool + 자체 서버 Version A (Poor) | Poor descriptions |
| E4-B | Base Pool + 자체 서버 Version B (Good) | Good descriptions |

- **동일 쿼리셋**을 두 Pool에 각각 실행
- `lift = (precision_B - precision_A) / precision_A × 100%`
- **자체 MCP 서버 쿼리만 필터링**하여 lift 계산 (다른 서버 쿼리는 양쪽 동일이므로 noise)

**통계 검정**:
- Paired t-test 또는 McNemar's test (이진 결과이므로)
- 유의수준: p < 0.05
- Effect size: Cohen's d 보고

#### 4-2. Spearman Correlation (Secondary Evidence — Correlational)

```python
# 모든 Tool에 대해 (quality_score, selection_rate) 쌍 수집
quality_scores = [seo_score(tool) for tool in all_tools]
selection_rates = [precision_per_tool(tool) for tool in all_tools]

r_s, p_value = scipy.stats.spearmanr(quality_scores, selection_rates)
# 목표: r_s > 0.6, p < 0.05
```

- A/B 쌍뿐 아니라 Pool 전체 Tool에서 관측적 상관관계 확인
- A/B가 인과를 보여주고, Spearman이 일반성을 보여줌

#### 4-3. Regression R² (Supplementary Evidence — Explanatory)

```python
import statsmodels.api as sm

# Description 품질 하위 요소별 기여도 분석
X = df[['specificity_score', 'disambiguation_score', 'parameter_coverage_score', 'negative_instruction_score']]
y = df['selection_rate']

model = sm.OLS(y, sm.add_constant(X)).fit()
# R²: quality가 selection_rate 분산의 몇 %를 설명하는가
# 각 계수의 p-value: 어떤 quality 요소가 가장 중요한가
```

- "description quality가 selection rate 분산의 X%를 설명한다"
- 하위 요소별 기여도 → Provider에게 "구체적으로 무엇을 고치면 좋은지" 안내 가능

#### 증거 삼각검증 (Evidence Triangulation) 요약

| 증거 유형 | 메서드 | 질문 | 목표 |
|-----------|--------|------|------|
| Primary (Causal) | A/B Lift | "Good description이 실제로 선택률을 높이는가?" | lift > 30%, p < 0.05 |
| Secondary (Correlational) | Spearman r | "전체 Tool에서 품질과 선택률이 상관있는가?" | r > 0.6, p < 0.05 |
| Supplementary (Explanatory) | Regression R² | "어떤 품질 요소가 가장 중요한가?" | R² > 0.4 |

---

### Experiment 5: Pool 스케일 실험

| 조건 | Pool 크기 | Pool 유형 |
|------|----------|----------|
| E5-A | 5 서버 | Base subset |
| E5-B | 20 서버 | Base subset |
| E5-C | 50 서버 | Base Pool |
| E5-D | 100 서버 | Expanded Pool |

**측정**: Pool 크기 증가에 따른 Precision@1 저하 곡선, Latency 증가율, Confusion Rate 증가율

**가설**: Pool이 커지면 유사 Tool이 더 많아져 Confusion Rate가 올라가고 Precision@1이 떨어질 것. 그 저하 속도가 전략에 따라 다를 것.

---

### Experiment 6: Pool 유사도 실험

| 조건 | Pool 유형 | 목적 |
|------|----------|------|
| E6-Low | Low Similarity Pool | Confusion Rate 최저 베이스라인 |
| E6-Base | Base Pool | 일반적 조건 |
| E6-High | High Similarity Pool | Confusion Rate 스트레스 테스트 |

**측정**: Confusion Rate 변화 (primary), Precision@1, NDCG@5

---

### Experiment 7: SEO 점수 방식 비교 (OQ-1 해결)

| 조건 | 점수 방식 |
|------|----------|
| E7-A | 정규식 휴리스틱 (`seo_score.py` 현재) |
| E7-B | LLM-based (GPT-4o-mini, 1-5점) |

**측정**:
- Spearman(score, selection_rate) — 어느 방식의 score가 selection_rate와 더 상관있는가
- Human agreement — 20~30개 description에 대해 사람이 직접 매긴 점수와의 상관
- 비용 + 재현성

---

## 4. 실험 실행 순서 (의존관계)

```
Phase 0: Ground Truth 구축 (seed set + Pool 정의)
    ↓
Phase 1: E1 (전략 비교) — 최적 전략 결정
    ↓
Phase 2: E2 (임베딩 비교) — E1 결과의 최적 전략 고정
    ↓
Phase 3: E3 (Reranker 비교) — E1+E2 결과 고정
    ↓
Phase 4 (병렬):
    ├── E4 (Description A/B) — 테제 검증, E1+E2+E3 최적 설정 사용
    ├── E5 (Pool 스케일) — 최적 설정으로 스케일 테스트
    └── E6 (Pool 유사도) — Confusion Rate 심화 분석

Phase 5 (OQ-1 해결 후):
    └── E7 (SEO 점수 비교) — E4 결과와 함께 분석
```

**Phase 1-3은 순차적**: 각 실험의 최적 결과가 다음 실험의 고정값이 되므로.
**Phase 4는 병렬 가능**: E4, E5, E6은 서로 독립.

---

## 5. 실험 자동화 요건

### CLI 인터페이스

```bash
# 기본 사용
python run_experiments.py \
    --experiment E1 \
    --strategy sequential \
    --embedding bge-m3 \
    --reranker cohere \
    --pool base \
    --ground-truth data/ground_truth/seed_set.jsonl

# 전체 매트릭스 실행
python run_experiments.py --experiment E1 --all-conditions

# 특정 난이도만
python run_experiments.py --experiment E1 --strategy sequential --difficulty hard
```

### 출력 형식

```json
{
    "experiment_id": "E1-A-20260320-143022",
    "config": {
        "strategy": "sequential",
        "embedding": "bge-m3",
        "reranker": "cohere",
        "pool": "base",
        "pool_size": 50,
        "ground_truth": "seed_set.jsonl",
        "n_queries": 80
    },
    "metrics": {
        "precision_at_1": 0.5125,
        "server_recall_at_k": {"k": 3, "value": 0.9125},
        "tool_recall_at_10": 0.8625,
        "mrr": 0.8234,
        "ndcg_at_5": 0.7456,
        "confusion_rate": 0.4231,
        "server_error_rate": 0.0875,
        "ece": 0.1234,
        "latency_ms": {"p50": 234, "p95": 1456, "p99": 2345}
    },
    "breakdown": {
        "by_difficulty": {
            "easy": {"precision_at_1": 0.75, "n": 32},
            "medium": {"precision_at_1": 0.44, "n": 32},
            "hard": {"precision_at_1": 0.19, "n": 16}
        },
        "by_category": {
            "search": {"precision_at_1": 0.60, "n": 10},
            "code": {"precision_at_1": 0.50, "n": 10}
        }
    },
    "per_query_results": [
        {
            "query_id": "gt-search-001",
            "correct": true,
            "rank_of_correct": 1,
            "confidence": 0.89,
            "latency_ms": 234,
            "top_5": ["semantic_scholar/search_papers", "mcp_arxiv/search_arxiv", ...]
        }
    ]
}
```

### W&B 통합

```python
import wandb

def log_experiment(result: ExperimentResult):
    wandb.init(
        project="mcp-discovery",
        name=result.experiment_id,
        config=result.config,
    )
    wandb.log(result.metrics)

    # 난이도별 분해
    for diff, stats in result.breakdown["by_difficulty"].items():
        wandb.log({f"precision_at_1/{diff}": stats["precision_at_1"]})

    # Confusion Matrix (per-query heatmap)
    wandb.log({"confusion_matrix": wandb.plot.confusion_matrix(...)})

    wandb.finish()
```

---

## 6. 결과 보고 형식

### E1: 전략 비교 결과

| 지표 | Sequential (A) | Parallel (B) | Taxonomy (C) | 최적 |
|------|---------------|-------------|-------------|------|
| Precision@1 | 48.7% | 52.5% | 51.2% | **B** |
| Server Recall@3 | 87.5% | 93.8% | 91.2% | **B** |
| Latency p95 | 1,234ms | 1,678ms | 1,456ms | **A** |
| Confusion Rate | 45.2% | 38.7% | 41.3% | **B** |


### 최종 보고서 구조 (4/26 제출)

1. **Abstract**: 핵심 결과 한 문단
2. **실험 설정**: Pool 구성, Ground Truth 통계, 하드웨어 스펙
3. **E1-E3 결과**: 최적 파이프라인 결정 과정 + 수치
4. **E4 결과**: 테제 검증 (evidence triangulation 3개 지표)
5. **E5-E6 결과**: 스케일 및 robustness 분석
6. **Discussion**: 한계, 위협 요인, 향후 연구
7. **Provider Analytics 데모**: E4 결과를 기반으로 한 대시보드 스크린샷

---

## 7. 위협 요인 (Threats to Validity)

### Internal Validity
- **Ground Truth 편향**: seed set 작성자가 실험 설계자와 동일 → 무의식적으로 특정 전략에 유리한 쿼리 작성 가능
  - **완화**: LLM synthetic 쿼리 병행, seed set 작성 시 전략 구현을 보지 않음
- **A/B Description 차이 크기**: Version A를 너무 나쁘게 만들면 lift가 과대 측정
  - **완화**: Version A도 실제 Smithery에서 볼 수 있는 수준의 description으로 설정

### External Validity
- **Pool 규모**: 실제 MCP 생태계(수천 서버)와 실험 Pool(50-100서버)의 규모 차이
  - **완화**: E5 스케일 실험으로 추세 분석
- **쿼리 분포**: 실제 사용자 쿼리와 실험 쿼리의 분포 차이
  - **완화**: 난이도/모호도 분포를 의도적으로 다양화

### Construct Validity
- **SEO 점수의 validity (OQ-1)**: 점수 자체가 "품질"을 잘 반영하는지 미검증
  - **완화**: E7 실험에서 human agreement 측정
- **Precision@1의 한계**: multi-correct 케이스에서 하나만 정답으로 인정
  - **완화**: NDCG@5 병행, alternative_tools 활용

---

## 8. 타임라인

| 주차 | 기간 | 실험 | 산출물 |
|------|------|------|--------|
| Week 1 | 3/20 - 3/26 | 프로젝트 기반 구축 (Phase 0) + Ground Truth seed set 작성 시작 | 프로젝트 스켈레톤, seed_set.jsonl 작성 시작 |
| Week 2 | 3/27 - 4/2 | 데이터 수집 + 임베딩 + 핵심 파이프라인 (Phase 1-3) + seed set 완성 | seed_set.jsonl (80개), 검색 파이프라인 동작 |
| Week 3 | 4/3 - 4/9 | E1 (전략 비교) + E2 (임베딩) + E3 (Reranker) | 최적 파이프라인 확정 |
| Week 4 | 4/10 - 4/16 | E4 (테제 검증) + E5 + E6 + Provider Analytics 백엔드 | evidence triangulation 결과 |
| Week 5 | 4/17 - 4/25 | 보고서 작성 + Provider Analytics 데모 + 마무리 | 최종 제출물 |

---

## 9. 다음 단계

1. **코드 스펙 업데이트**: 이 실험 설계를 기반으로 `run_experiments.py`, `ExperimentConfig`, `ExperimentResult` 클래스 정의
2. **Ground Truth 작성 시작**: seed_set.jsonl 80개 수동 작성
3. **Pool 정의**: Smithery 크롤링 후 4종 Pool 정의 파일 작성
4. **자체 MCP 서버 구축**: mcp-arxiv, mcp-calculator, mcp-korean-news × 2 versions
