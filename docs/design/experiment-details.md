# 실험 상세 — E0-E7 Full Specs

> 최종 업데이트: 2026-03-29
> 실험 허브 (요약/방법론): `./experiment-design.md`

---

## E0: 1-Layer vs 2-Layer 아키텍처 검증

> E1의 전제 조건. 2-Layer가 MCP-Zero 308 서버 규모에서 Precision@1을 높이는지 확인.

| 조건 | 아키텍처 | 전략 | 임베딩 | Reranker | Pool |
|------|----------|------|--------|----------|------|
| E0-A | **1-Layer** (Tool 전체 직접 검색) | — | OpenAI text-embedding-3-small | Cohere | MCP-Zero (308) |
| E0-B | **2-Layer** Sequential | Sequential | OpenAI text-embedding-3-small | Cohere | MCP-Zero (308) |
| E0-C | **2-Layer** Parallel (RRF) | Parallel | OpenAI text-embedding-3-small | Cohere | MCP-Zero (308) |

> **임베딩 선택 근거**: E0의 독립 변수는 아키텍처(1-Layer vs 2-Layer)이므로 임베딩은 통제 변인. 현재 구현된 `OpenAIEmbedder`(text-embedding-3-small)를 사용. BGE-M3는 E2에서 비교. MCP-Zero pre-computed `text-embedding-3-large` 벡터는 E2-C 조건에서 활용.

- **측정**: Precision@1, Tool Recall@10, MRR, Latency (p50/p95), Server Classification Error Rate (E0-B만)
- **판정**: E0-B가 E0-A 대비 Precision@1 **+5%p 이상** → 2-Layer 유효 → E1 진행. E0-C는 Phase 7(Parallel 구현) 이후 추가 실행.
- **미달 시**: 2-Layer 복잡성 대비 이득 없음 → E1을 1-Layer 기준 재설계 (CTO 논의)

```bash
# 현재 구현됨:
uv run python scripts/run_e0.py                # Flat + Sequential (Parallel은 Phase 7 이후)

# 계획됨 (run_experiments.py 구현 후):
# python run_experiments.py --experiment E0 --architecture 1layer --pool base
# python run_experiments.py --experiment E0 --strategy sequential --pool base
# python run_experiments.py --experiment E0 --strategy parallel --pool base
```

---

## E1: 검색 전략 비교 (핵심 실험)

> 전제: E0에서 2-Layer 유효성 확인 후 진행.

| 조건 | 전략 | 임베딩 | Reranker | Pool |
|------|------|--------|----------|------|
| E1-A | Sequential | BGE-M3 | Cohere | MCP-Zero (308) |
| E1-B | Parallel (RRF) | BGE-M3 | Cohere | MCP-Zero (308) |
| E1-C | Taxonomy-gated | BGE-M3 | Cohere | MCP-Zero (308) |

- **측정**: Precision@1, Server Recall@K, Tool Recall@10, MRR, NDCG@5, Confusion Rate, Latency (p50/p95/p99)
- **특수 측정 (Sequential만)**: Server Classification Error Rate 별도 로깅

```bash
# 계획됨 (run_experiments.py + Parallel/Taxonomy 구현 후):
# python run_experiments.py --experiment E1 --strategy sequential --pool base
# python run_experiments.py --experiment E1 --strategy parallel --pool base
# python run_experiments.py --experiment E1 --strategy taxonomy --pool base
```

### 결과 보고 형식

| 지표 | Sequential (A) | Parallel (B) | Taxonomy (C) | 최적 |
|------|---------------|-------------|-------------|------|
| Precision@1 | — | — | — | — |
| Server Recall@5 | — | — | — | — |
| Latency p95 | — | — | — | — |
| Confusion Rate | — | — | — | — |

---

## E2: 임베딩 모델 비교

> E1 최적 전략 고정 후 임베딩만 교체.

| 조건 | 전략 | 임베딩 | Reranker | Pool |
|------|------|--------|----------|------|
| E2-A | (E1 최적) | BGE-M3 | Cohere | MCP-Zero (308) |
| E2-B | (E1 최적) | OpenAI text-embedding-3-small | Cohere | MCP-Zero (308) |
| E2-C | (E1 최적) | OpenAI text-embedding-3-large (MCP-Zero 제공, 3072D) | Cohere | MCP-Zero (308) |

- **Primary**: Tool Recall@10
- **Secondary**: Precision@1, Latency, 비용 (API call 수 x 단가)
- **추가**: Cold start time (인덱스 빌드), 인덱스 크기, BGE-M3 sparse 기여도 (Dense-only vs Dense+Sparse)
- **E2-D 참고**: MCP-Zero에서 사전 계산된 text-embedding-3-large 벡터 활용 (재임베딩 불필요, `data/external/mcp-zero/embeddings/`)

---

## E3: Reranker 비교

> E1+E2 결과 고정 후 Reranker만 교체.

| 조건 | 전략 | 임베딩 | Reranker | Pool |
|------|------|--------|----------|------|
| E3-A | (E1 최적) | (E2 최적) | Cohere Rerank 3 단독 | MCP-Zero (308) |
| E3-B | (E1 최적) | (E2 최적) | Cohere + LLM fallback (gap < threshold) | MCP-Zero (308) |
| E3-C | (E1 최적) | (E2 최적) | LLM-as-Judge 단독 | MCP-Zero (308) |

- **측정**: Precision@1 향상폭 (vs no-reranker baseline), Latency 증가, 비용
- **Confidence 분기 최적화 (E3-B 세부)**:
  - threshold 후보: [0.05, 0.10, 0.15, 0.20, 0.25]
  - 각 threshold에서 LLM fallback 발동 비율, Precision@1, ECE 측정
  - "비용 대비 정확도 향상"이 최적인 threshold 선택

---

## E4: Description 품질 → 선택률 인과 관계 (테제 검증)

> **이 프로젝트에서 가장 중요한 실험.**
> 외부 검증: Description Smells 논문 (arxiv:2602.18914)이 description 품질 → 선택률 인과 관계를 사전 검증 (+11.6% 개선, p<0.001). 우리의 차별점: smell 유무 비교가 아닌 GEO 기법을 통한 체계적 개선 방법론 제시.

### Version A / B 작성 기준 (GEO 기반)

Version A는 Smithery의 평균적인 원본 description 수준으로 작성 (너무 나쁘게 만들어 lift를 과대 측정하는 것 방지).
Version B는 GEO 논문 상위 3기법을 적용하여 작성:

| GEO 기법 | MCP Description 적용 | 예시 |
|----------|---------------------|------|
| Statistics Addition | 커버리지/성능 수치 포함 | "Supports 50+ file formats, processes up to 10MB" |
| Fluency Optimization | 첫 문장에 핵심 기능, 구조적 문장 | "Converts PDF to searchable text. Supports OCR for scanned documents." |
| Cite Sources | 지원 표준/프로토콜 명시 | "Implements RSS 2.0 and Atom 1.0 feed parsing" |

> **E7과의 연결**: E7이 먼저 완료된 경우, E7에서 검증된 채점 방식으로 Version A/B의 점수 차이를 정량화하여 E4 보고서에 포함.

### 4-1. A/B Selection Rate Lift (Primary — Causal)

| 조건 | Pool 구성 | Description 버전 |
|------|----------|-----------------|
| E4-A | Base Pool + 자체 서버 Version A (Poor) | Smithery 원본 수준 |
| E4-B | Base Pool + 자체 서버 Version B (Good) | GEO 기법 적용 |

- 동일 쿼리셋을 두 Pool에 각각 실행
- `lift = (precision_B - precision_A) / precision_A * 100%`
- 자체 MCP 서버 쿼리만 필터링하여 lift 계산
- 통계 검정: McNemar's test (이진 결과), p < 0.05, Cohen's d 보고

### 4-2. Spearman Correlation (Secondary — Correlational)

```python
# 모든 Tool에 대해 (geo_score, selection_rate) 쌍 수집
quality_scores = [geo_score(tool) for tool in all_tools]
selection_rates = [precision_per_tool(tool) for tool in all_tools]
r_s, p_value = scipy.stats.spearmanr(quality_scores, selection_rates)
# 목표: r_s > 0.6, p < 0.05
```

### 4-3. Regression R-squared (Supplementary — Explanatory)

```python
import statsmodels.api as sm
X = df[['clarity_score', 'disambiguation_score',
        'parameter_coverage_score', 'boundary_score',
        'stats_score', 'precision_score']]
y = df['selection_rate']
model = sm.OLS(y, sm.add_constant(X)).fit()
# R²: quality가 selection_rate 분산의 몇 %를 설명하는가
# 각 계수의 p-value: 어떤 quality 요소가 가장 중요한가
```

### Evidence Triangulation 요약

| 증거 유형 | 메서드 | 목표 |
|-----------|--------|------|
| Primary (Causal) | A/B Lift | lift > 30%, p < 0.05 |
| Secondary (Correlational) | Spearman r | r > 0.6, p < 0.05 |
| Supplementary (Explanatory) | Regression R-squared | R-squared > 0.4 |

---

## E5: Pool 스케일 실험

| 조건 | Pool 크기 | Pool 유형 |
|------|----------|----------|
| E5-A | 5 서버 | Base subset |
| E5-B | 20 서버 | Base subset |
| E5-C | 50 서버 | Base Pool |
| E5-D | 100 서버 | Expanded Pool |
| E5-E | 200 서버 | MCP-Zero subset |
| E5-F | 308 서버 | MCP-Zero 전체 |

- **측정**: Pool 크기별 Precision@1 저하 곡선, Latency 증가율, Confusion Rate 증가율
- **가설**: Pool 커지면 유사 Tool 증가 → Confusion Rate 상승, Precision@1 하락. 저하 속도는 전략에 따라 다름

---

## E6: Pool 유사도 실험

> MCPAgentBench (arxiv:2512.24565) distractor 접근법 참고: 정답 tool + 비슷한 distractor tool 혼합으로 체계적 ambiguity 평가.

| 조건 | Pool 유형 | 목적 |
|------|----------|------|
| E6-Low | Low Similarity Pool | Confusion Rate 최저 베이스라인 |
| E6-Base | Base Pool | 일반적 조건 |
| E6-High | High Similarity Pool (MCP-Zero에서 유사 서버 선별) | Confusion Rate 스트레스 테스트 |

- **Primary**: Confusion Rate 변화
- **Secondary**: Precision@1, NDCG@5

---

## E7: GEO 점수 방식 비교 (OQ-1 해결)

| 조건 | 점수 방식 |
|------|----------|
| E7-A | 정규식 휴리스틱 (`geo_score.py`) — GEO 6D |
| E7-B | LLM-based (GPT-4o-mini, 1-5점) — GEO 6D |
| E7-C | Description Smells 4D (Accuracy/Functionality/Completeness/Conciseness) — 외부 루브릭 |

- **측정**:
  - Spearman(geo_score, selection_rate) — 어느 방식이 selection_rate와 더 상관 있는가
  - Human agreement — 20~30개 description에 대해 사람 직접 채점과의 상관
  - 비용 + 재현성

> E4의 Version B는 GEO 기법으로 작성되므로, E7에서 검증된 GEO Score 채점 방식이 Version B에 실제로 높은 점수를 부여하는지 교차 확인 가능.

---

## 실험 자동화 — CLI 인터페이스 (계획)

> `scripts/run_experiments.py`는 아직 미구현. 현재는 `scripts/run_e0.py`만 사용 가능.

```bash
# 계획된 CLI (Phase 10 이후):
# python run_experiments.py --experiment E1 --strategy sequential --embedding bge-m3 --reranker cohere --pool base --ground-truth data/ground_truth/seed_set.jsonl
# python run_experiments.py --experiment E1 --all-conditions          # 전체 매트릭스
# python run_experiments.py --experiment E1 --strategy sequential --difficulty hard  # 특정 난이도
```

## 실험 출력 형식

- `experiment_id`: `"E1-A-20260320-143022"` (실험-조건-날짜-시간)
- `config`: strategy, embedding, reranker, pool, pool_size, ground_truth, n_queries
- `metrics`: precision_at_1, server_recall_at_k, tool_recall_at_10, confusion_rate, latency_ms
- `breakdown`: by_difficulty, by_category
- W&B 통합: `wandb.init(project="mcp-discovery")` → `wandb.log(metrics)` → 난이도별 분해 + confusion_matrix
