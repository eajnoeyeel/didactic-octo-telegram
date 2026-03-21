# MCP 추천 시스템 평가 지표 — 논문 기반 종합 리서치
> 작성: 2026-03-19 | 목적: 평가 루브릭 설계의 근거 자료

---

## 핵심 구조

```
쿼리 입력
  ↓
[Layer 1] 서버 추천 — find_best_server
  ↓ Top-K 서버
[Layer 2] 툴 추천 — find_best_tool
  ↓ Top-N 툴
Reranker → Confidence 분기 → 결과 반환
```

평가는 세 레이어로 나뉜다: Layer 1 독립 평가, Layer 2 독립 평가, End-to-End 통합 평가.

---

## Layer 1: 서버 추천 평가

### Recall@K (서버 레벨)

**정의**: 정답 서버가 Top-K 결과 안에 포함되는 비율

**왜 Precision이 아니라 Recall인가**: Layer 1의 역할은 "정답을 놓치지 않는 것"이다. Layer 2 Reranker가 K개 중에서 고르기 때문에, K안에 정답이 들어있는지가 핵심. TREC IR 문헌에서 두 단계 시스템의 첫 단계는 항상 Recall로 평가한다.

**논문 근거**: ToolBench/ToolLLM (Qin et al., ICLR 2024) — API Retriever 품질을 Recall@K로 독립 평가. "We train a neural API retriever... and evaluate it with Recall@K."

**권장 K값**: K=3 (서버 50개 이하), K=5 (서버 50개 이상)

### MRR (Mean Reciprocal Rank, 서버 레벨)

**정의**: 정답 서버가 몇 번째로 나왔는지의 역수 평균

```
MRR = (1/|Q|) × Σ (1/rank_i)
```

**Recall@K 대비 강점**: Recall은 "있냐 없냐"만 본다. MRR은 "얼마나 앞에 있냐"를 반영. Sequential 구조에서 상위 서버부터 Tool 검색하면 MRR이 실제 성능을 더 잘 반영.

**논문 근거**: Voorhees (TREC-8 QA Track, 1999). ToolBench, API-Bank 등 모든 tool retrieval 논문이 MRR 또는 NDCG를 reporting.

### Server Classification Error Rate

**정의**: 정답 서버가 Top-K에 포함되지 않는 비율 (= 1 - Recall@K)

**별도 추적 이유**: Layer 2 오류 발생 시 "Layer 1 cutoff 문제인가, Layer 2 Reranker 문제인가" 분리 진단.

---

## Layer 2: 툴 추천 평가

### Precision@1

**정의**: 최종 추천된 툴 #1이 정답인 비율

**논문 근거**: RAG-MCP (arxiv:2505.03275) 핵심 지표. 베이스라인 13.62% → RAG-MCP 43.13%. API-Bank (Li et al., EMNLP 2023)도 동일 방식.

### Recall@K (툴 레벨)

**정의**: Top-K 결과 안에 정답 툴이 있는 비율. Reranker 입력 품질 측정용. K=10 표준.

**논문 근거**: ToolBench/ToolLLM, MCP-Bench (arxiv:2508.20453, 2025).

### NDCG@K (Normalized Discounted Cumulative Gain)

**정의**: 상위에 배치될수록 더 높은 점수를 주는 랭킹 품질 지표.

```
NDCG@K = DCG@K / IDCG@K
DCG@K = Σ rel_i / log₂(i+1)
```

**MRR 대비 강점**: MRR은 첫 번째 정답 위치만 본다. NDCG는 부분적으로 관련 있는 툴에도 점수 부여 가능. Disambiguation 케이스(Top-3 반환)를 평가할 때 특히 유용.

**논문 근거**: TREC IR 표준. ToolBench 계열 공통 보고 지표.

**권장**: Precision@1 + NDCG@5 함께 reporting → single-result와 ranked-list 성능 동시 커버.

### Confusion Rate

**정의**: Precision@1이 틀렸을 때, 그 오답이 정답과 의미적으로 유사한 툴인 비율.

**두 가지 실패 유형**:
- **Confusion failure**: 비슷한 툴을 잘못 골랐다 → Provider에게 disambiguation 개선 유도
- **Miss failure**: 전혀 관련없는 툴 반환 → 검색 전략 자체 개선 필요

**논문 근거**:
- ToolScan/SpecTool (arxiv:2411.13547, 2024) — "Environments with similar APIs tend to confuse the models." 7가지 오류 패턴 중 "similar tool confusion" 별도 분류.
- MetaTool (ICLR 2024) — "tool selection with similar choices" 독립 서브태스크.

**계산**:
```python
confusion_rate = (틀린 케이스 중 정답이 Top-K 안에 있는 비율)
# 정답이 Top-K에 있다 = 시스템이 정답을 알고 있었지만 rank-1을 잘못 줬다 = Confusion
# 정답이 Top-K에 없다 = 시스템이 아예 못 찾았다 = Miss
```

---

## End-to-End 평가

### Pass Rate (태스크 완성률)

**정의**: 쿼리에 대해 툴을 선택하고 실제 실행까지 성공한 비율.

**Precision@1과의 차이**: 올바른 툴을 골랐어도 파라미터를 잘못 채우면 실패.

**논문 근거**: ToolBench/ToolLLM (ICLR 2024) — "Pass Rate: the proportion of successfully completing an instruction." StableToolBench (ACL 2024) — "Solvable Pass Rate"로 개선 (API 상태 문제로 풀 수 없는 태스크 분모에서 제외).

**현실적 접근**: 직접 만드는 MCP 서버(mcp-arxiv 등)에 대해서만 Pass Rate 측정, 나머지는 Precision@1 대체.

### Latency (p50 / p95 / p99)

측정 포인트:
- Layer 1 임베딩 + 검색: ms
- Layer 2 툴 검색: ms
- Reranker: ms (Cohere API latency 포함)
- 전체 pipeline: ms

**p95/p99를 봐야 하는 이유**: 평균은 tail latency를 숨긴다. JSPLIT (arxiv:2510.14537) — latency를 핵심 metric으로 보고.

---

## Provider 분석용 특수 지표

### Description Quality ↔ Selection Rate Spearman 상관계수

**정의**: 툴의 description 품질 점수와 Precision@1 간의 Spearman 상관계수

```
r_s = Spearman(SEO_score_i, Precision@1_i) ∀ i ∈ Tools
```

**핵심 테제 검증 지표**: "description을 잘 쓰면 더 많이 선택된다"의 수치적 증명. 상관계수가 높고 p < 0.05이면 Provider Analytics 기능 전체의 근거.

**ToolTweak이 역방향으로 이미 증명**: ToolTweak (arxiv:2510.02554, 2025) — "adversaries can systematically increase selection rates from ~20% to 81% by iteratively manipulating tool names and descriptions." description이 선택률에 강하게 영향을 미침은 이미 증명됨.

### ECE (Expected Calibration Error)

**정의**: confidence 점수가 실제 정확도를 얼마나 잘 반영하는가.

```
ECE = Σ (|B_m|/n) × |acc(B_m) - conf(B_m)|
```

**논문 근거**: Naeini et al., "Obtaining Well Calibrated Probabilities Using Bayesian Binning into Quantiles," AAAI 2015.

**중요성**: ECE가 낮아야 gap-based confidence 분기(DP6)가 의미있다.

---

## 전체 지표 체계 요약

| 레이어 | 지표 | 논문 근거 | 측정 목적 |
|--------|------|-----------|-----------|
| Layer 1 | Recall@K (K=3,5) | ToolBench/ToolLLM (ICLR 2024) | 정답 서버가 후보에 있는가 |
| Layer 1 | MRR | TREC-8 (Voorhees 1999) | 정답 서버의 순위 품질 |
| Layer 1 | Server Error Rate | 직접 정의 | Layer 1 실패율 독립 추적 |
| Layer 2 | Precision@1 | RAG-MCP (2505.03275), API-Bank (EMNLP 2023) | 최종 추천 정확도 |
| Layer 2 | Recall@K (K=10) | ToolBench/ToolLLM, MCP-Bench (2508.20453) | Reranker 입력 품질 |
| Layer 2 | NDCG@5 | TREC IR, ToolBench | 순위 전체 품질 |
| Layer 2 | Confusion Rate | ToolScan (2411.13547), MetaTool (ICLR 2024) | 유사 툴 혼동 vs 완전 미스 분리 |
| E2E | Pass Rate | ToolBench (ICLR 2024), StableToolBench (ACL 2024) | 실제 태스크 성공률 |
| E2E | Latency p50/p95/p99 | JSPLIT (2510.14537) | 응답 속도 |
| Provider | Spearman(quality, selection) | ToolTweak (2510.02554) 역방향 근거 | 핵심 테제 검증 |
| Provider | ECE | Naeini et al. (AAAI 2015) | Confidence 신뢰성 |

---

## 참고 논문 목록

| 논문 | ID | 기여 |
|------|------|------|
| ToolLLM/ToolBench | ICLR 2024, arxiv:2307.16789 | Pass Rate, Win Rate, API Retriever Recall@K |
| RAG-MCP | arxiv:2505.03275 | MCP Tool Selection 43% vs 13%, Precision@1 |
| API-Bank | EMNLP 2023 | API call accuracy 벤치마크 |
| StableToolBench | ACL 2024 | Solvable Pass Rate 개선 |
| MetaTool | ICLR 2024, arxiv:2310.03128 | Similar tool confusion 서브태스크 |
| ToolScan/SpecTool | arxiv:2411.13547 | 7가지 Tool-use 오류 패턴 분류 |
| JSPLIT | arxiv:2510.14537 | Taxonomy-gated retrieval, latency 절감 |
| MCP-Bench | arxiv:2508.20453 | MCP 특화 벤치마크 |
| τ-bench | arxiv:2406.12045 | Tool-Agent-User 상호작용 벤치마크, pass^k |
| ToolTweak | arxiv:2510.02554 | Description 조작 → 선택률 20%→81% |
| ToolFlood | arxiv:2603.13950 | Semantic covering attack on tool selection |
| Calibration/ECE | Naeini et al. AAAI 2015 | Expected Calibration Error |
| TREC-8 QA | Voorhees 1999 | MRR 원류 |

---

## 다음 단계

이 리서치를 기반으로:
1. **평가 루브릭 문서** — 각 지표의 공식적 정의, 측정 방법, 합격 기준 설정
2. **Ground Truth 구조** — 레이블 형식이 위 지표를 모두 계산 가능하도록 설계
3. **실험 설계** — 통제 변인 × 전략 × 지표 실험 매트릭스
4. **코드 스펙** — Evaluator 클래스 인터페이스 갱신
