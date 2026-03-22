# MCP 추천 시스템 평가 지표 — 논문 기반 종합 리서치

> 작성: 2026-03-19 | 최종 업데이트: 2026-03-22
> 목적: 평가 루브릭 설계의 근거 자료

---

## 핵심 구조

```
쿼리 → [Layer 1] 서버 추천 → Top-K → [Layer 2] 툴 추천 → Reranker → Confidence 분기 → 결과
```

평가: Layer 1 독립, Layer 2 독립, End-to-End 통합의 세 레이어.

---

## Layer 1: 서버 추천 평가

### Recall@K (서버 레벨)
- **정의**: 정답 서버가 Top-K 안에 포함되는 비율
- **이유**: Layer 1은 "정답을 놓치지 않는 것"이 핵심. TREC IR 문헌에서 2단계 시스템의 첫 단계는 Recall로 평가
- **근거**: ToolBench/ToolLLM (ICLR 2024) — API Retriever를 Recall@K로 평가
- **권장 K**: K=3 (서버 50개 이하), K=5 (50개 이상)

### MRR (Mean Reciprocal Rank)
- **정의**: 정답 서버 순위의 역수 평균 — `MRR = (1/|Q|) x Sum(1/rank_i)`
- **Recall 대비 강점**: "얼마나 앞에 있냐"를 반영. Sequential에서 상위부터 검색하므로 실제 성능 반영
- **근거**: Voorhees (TREC-8 QA Track, 1999). ToolBench 계열 공통

### Server Classification Error Rate
- **정의**: 1 - Recall@K. Layer 1 실패율
- **추적 이유**: Layer 2 오류 시 "Layer 1 cutoff vs Layer 2 Reranker" 분리 진단

---

## Layer 2: 툴 추천 평가

### Precision@1
- **정의**: 최종 추천 툴 #1이 정답인 비율
- **근거**: RAG-MCP (2505.03275) 핵심 지표 (13.62% → 43.13%). API-Bank (EMNLP 2023) 동일

### Recall@K (툴 레벨)
- **정의**: Top-K에 정답 툴 포함 비율. Reranker 입력 품질 측정. K=10
- **근거**: ToolBench/ToolLLM, MCP-Bench (2508.20453)

### NDCG@K
- **정의**: 상위 배치일수록 높은 점수를 주는 랭킹 품질 지표
- `NDCG@K = DCG@K / IDCG@K`, `DCG@K = Sum(rel_i / log2(i+1))`
- **MRR 대비 강점**: 부분 관련 툴에도 점수 부여. Disambiguation 케이스(Top-3 반환)에 유용
- **근거**: TREC IR 표준. ToolBench 계열 공통
- **권장**: Precision@1 + NDCG@5 함께 보고

### Confusion Rate
- **정의**: Precision@1 오답 중 정답이 Top-K 안에 있는 비율
- **두 실패 유형**:
  - Confusion: 비슷한 툴 잘못 선택 → Provider에게 disambiguation 개선 유도
  - Miss: 전혀 관련 없는 툴 → 검색 전략 자체 개선
- **근거**: ToolScan/SpecTool (2411.13547) — "similar tool confusion" 별도 분류. MetaTool (ICLR 2024)

---

## End-to-End 평가

### Pass Rate (태스크 완성률)
- **정의**: 툴 선택 + 실행 성공 비율. 올바른 툴이어도 파라미터 오류 시 실패
- **근거**: ToolBench/ToolLLM (ICLR 2024), StableToolBench (ACL 2024) — Solvable Pass Rate
- **현실적 접근**: 자체 MCP 서버만 Pass Rate, 나머지 Precision@1

### Latency (p50 / p95 / p99)
- 측정: Layer 1 임베딩+검색, Layer 2 툴 검색, Reranker, 전체 pipeline (ms)
- **이유**: 평균은 tail latency를 숨김
- **근거**: JSPLIT (2510.14537) — latency 핵심 metric

---

## Provider 분석용 특수 지표

### Spearman(Description Quality, Selection Rate)
- `r_s = Spearman(DQS_i, Precision@1_i)` for all tools
- 핵심 테제 검증: "description을 잘 쓰면 더 많이 선택된다"
- **근거**: ToolTweak (2510.02554) — description 조작으로 선택률 20% → 81%

### ECE (Expected Calibration Error)
- `ECE = Sum(|B_m|/n) x |acc(B_m) - conf(B_m)|`
- Confidence 점수가 실제 정확도를 반영하는지 측정. Gap-based 분기(DP6)의 유효성 전제
- **근거**: Naeini et al. (AAAI 2015)

---

## 전체 지표 체계

| 레이어 | 지표 | 논문 근거 | 목적 |
|--------|------|-----------|------|
| L1 | Recall@K | ToolBench/ToolLLM (ICLR 2024) | 정답 서버 포함 여부 |
| L1 | MRR | TREC-8 (Voorhees 1999) | 순위 품질 |
| L1 | Server Error Rate | 직접 정의 | Layer 1 실패율 |
| L2 | Precision@1 | RAG-MCP, API-Bank (EMNLP 2023) | 최종 추천 정확도 |
| L2 | Recall@K (K=10) | ToolBench, MCP-Bench | Reranker 입력 품질 |
| L2 | NDCG@5 | TREC IR, ToolBench | 순위 전체 품질 |
| L2 | Confusion Rate | ToolScan, MetaTool (ICLR 2024) | 유사 툴 혼동 분리 |
| E2E | Pass Rate | ToolBench, StableToolBench (ACL 2024) | 태스크 성공률 |
| E2E | Latency p50/p95/p99 | JSPLIT | 응답 속도 |
| Provider | Spearman | ToolTweak 역방향 근거 | 핵심 테제 검증 |
| Provider | ECE | Naeini et al. (AAAI 2015) | Confidence 신뢰성 |

---

## 다음 단계

1. 평가 루브릭 — 각 지표의 정의, 측정 방법, 합격 기준
2. Ground Truth — 위 지표 모두 계산 가능한 레이블 형식
3. 실험 설계 — 통제 변인 x 전략 x 지표 매트릭스
4. Evaluator 클래스 인터페이스 갱신

---

## 관련 papers

| 논문 (약칭) | 파일 |
|-------------|------|
| ToolTweak | [`../papers/tooltweak-analysis-ko.md`](../papers/tooltweak-analysis-ko.md) |
| JSPLIT | [`../papers/jsplit-analysis-ko.md`](../papers/jsplit-analysis-ko.md) |
| MCP-Bench | [`../papers/mcp-bench-analysis-ko.md`](../papers/mcp-bench-analysis-ko.md) |
| ToolScan/SpecTool | [`../papers/toolscan-analysis-ko.md`](../papers/toolscan-analysis-ko.md) |
| ToolFlood | [`../papers/toolflood-analysis-ko.md`](../papers/toolflood-analysis-ko.md) |
| TREC-8 QA | [`../papers/trec-8-qa-analysis-ko.md`](../papers/trec-8-qa-analysis-ko.md) |
| Naeini ECE | [`../papers/naeini-ece-analysis-ko.md`](../papers/naeini-ece-analysis-ko.md) |
| MetaTool | [`../papers/metatool-analysis-ko.md`](../papers/metatool-analysis-ko.md) |
| ToolLLM/ToolBench | [`../papers/toolllm-analysis-ko.md`](../papers/toolllm-analysis-ko.md) |
| RAG-MCP | [`../papers/rag-mcp-analysis-ko.md`](../papers/rag-mcp-analysis-ko.md) |
| StableToolBench | [`../papers/stabletoolbench-analysis-ko.md`](../papers/stabletoolbench-analysis-ko.md) |
| API-Bank | [`../papers/api-bank-analysis-ko.md`](../papers/api-bank-analysis-ko.md) |
