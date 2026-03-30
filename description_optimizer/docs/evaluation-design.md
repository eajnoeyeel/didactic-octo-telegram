# Description Optimizer — Evaluation Design

> 최종 업데이트: 2026-03-30

---

## 평가 목표

Description Optimizer가 실제 RAG retrieval 품질을 향상시키는지 검증.

## 평가 5단계

### Stage 1: Unit-level Quality (Task 1-5에서 완료)
- 모든 컴포넌트 단위 테스트 통과
- GEO Score 계산 정확성
- Quality Gate 작동 검증

### Stage 2: Diagnostic Delta
- GEO Score는 diagnostic-only로 기록
- Retrieval 개선과의 상관 여부만 관찰
- 성공/실패 판정에는 사용하지 않음

### Stage 3: Retrieval Text Safety
- Cosine similarity(original, retrieval_description) >= 0.85
- Hallucinated parameter 없음
- sibling contamination 없음
- LLM-as-Judge 의미 보존 검증 (future)

### Stage 4: Offline A/B Test (Primary)
- Control: 원본 description으로 embedding search
- Treatment: `retrieval_description`으로 embedding search
- 동일 Ground Truth 사용
- `mcp_zero`처럼 raw pool에 라벨이 없으면 `seed_set + mcp_atlas`에서 pool 교집합 GT를 별도 생성
- Primary readout: query-level `Recall@K`
- Secondary: query-level `MRR`
- Diagnostic: query-level `P@1`, tool-average breakdown

### Stage 5: Statistical Significance
- paired bootstrap CI (`Recall@K`, `MRR`, `P@1`)
- discordant pair exact binomial test (`top1`, `topK`)
- 유의수준: p < 0.05
- 최소 효과 크기: Recall@K non-negative + MRR positive

---

## 최신 검증 상태 (2026-03-30, MCP-Zero)

### Evaluation Set

- Tool pool: `data/raw/mcp_zero_servers.jsonl`
- Filtered GT: `data/verification/mcp_zero_gt_filtered.jsonl`
- Queries: `178`
- Correct tools: `32`
- Servers: `10`

### Optimization Coverage

- Optimized GT tools: `32`
- `success`: `7`
- `gate_rejected`: `25`
- Success tool이 실제로 영향 줄 수 있는 queries: `61/178`

### Primary Query-Level Result

| 지표 | Original | Optimized | Delta |
|------|----------|-----------|-------|
| `P@1` | `0.2753` | `0.3427` | `+0.0674` |
| `Recall@10` | `0.6517` | `0.6629` | `+0.0112` |
| `MRR` | `0.4136` | `0.4439` | `+0.0304` |

### Significance

- `delta P@1` 95% CI: `[+0.0281, +0.1067]`
- `delta Recall@10` 95% CI: `[-0.0112, +0.0393]`
- `delta MRR` 95% CI: `[+0.0069, +0.0529]`
- exact binomial `p` for top-1 discordant pairs: `0.0018`

### Current Interpretation

- retrieval-aligned refactor는 `top-1`과 `MRR` 개선을 보였다.
- `Recall@10`은 소폭 상승했지만 아직 강한 통계적 확신은 부족하다.
- 현재 최대 병목은 retrieval objective 자체보다 `gate_rejected 25/32`로 나타난 gate throughput이다.

## 성공 기준

| 지표 | 목표 | 방법 |
|------|------|------|
| Recall@K delta | > 0 | A/B test |
| MRR delta | > 0 | A/B test |
| Retrieval preservation | >= 0.85 cosine | Embedding similarity |
| No regression | top-1 win > top-1 loss, long-tail degraded 사례 추적 | Query-level regression verification |
