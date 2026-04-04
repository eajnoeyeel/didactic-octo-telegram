# E0 Experiment Report — 1-Layer vs 2-Layer Architecture Validation

> **Date**: 2026-04-04 (재실행, GT 재구축 반영)
> **W&B**: https://wandb.ai/leeyj0304-42/mcp-discovery/runs/ej5ieqhb

---

## 실험 설정

| 항목 | 값 |
|------|-----|
| Pool | MCP-Zero 292 servers (GT-first ordering) |
| GT | seed_set (80) + mcp_atlas (328) = 408 total, 338 pool-covered |
| Embedding | text-embedding-3-large (3072-dim, MCP-Zero pre-computed) |
| Reranker | Cohere rerank-v3.5 (10 RPM) |
| top_k | 10 |
| Strategies | FlatStrategy, SequentialStrategy, ParallelStrategy |

## 결과

| Metric | Flat (1-Layer) | Sequential (2-Layer) | Parallel (2-Layer) |
|--------|:-:|:-:|:-:|
| **Precision@1** | **0.302** | 0.249 | 0.296 |
| Recall@10 | 0.527 | 0.352 | **0.533** |
| Server Recall@K | **0.654** | 0.396 | 0.642 |
| MRR | 0.376 | 0.284 | **0.378** |
| NDCG@5 | 0.400 | 0.299 | **0.404** |
| Confusion Rate | 0.322 | **0.138** | 0.336 |
| ECE | 0.102 | **0.085** | 0.104 |
| Latency p50 (ms) | 6007.8 | 6007.5 | 6006.0 |

- n_queries: 338, n_failed: 0

## Gate Decision

```
Sequential_P@1 (0.249) - Flat_P@1 (0.302) = -5.3%p  → FAIL (threshold: +5%p)
Parallel_P@1  (0.296) - Flat_P@1 (0.302) = -0.6%p  → FAIL (threshold: +5%p)
```

**2-Layer는 현재 설정에서 1-Layer 대비 개선되지 않음.**

## 분석

### Sequential이 낮은 이유
Server-level 검색(Layer 1)이 hard gate로 작동하여 정답 서버를 놓치면 복구 불가. Server Recall@K가 0.396으로 Flat(0.654)의 60% 수준 — Layer 1에서 40%의 정답 서버가 탈락.

### Parallel이 Flat과 비슷한 이유
RRF fusion이 Sequential의 server gate 손실을 보완하지만, Flat의 직접 tool 검색과 큰 차이 없음. 검색 공간이 2,797 tools로 충분히 작아 server 사전 필터링의 이점이 제한적.

### Confusion Rate 해석
Sequential의 낮은 Confusion(0.138)은 "서버를 못 찾아 결과 자체가 적음"의 부산물이지, 정밀도 개선이 아님.

### 이전 실행(n=194) 대비 변화

| Metric | Run 1 (n=194) | Run 2 (n=338) | 원인 |
|--------|:-:|:-:|------|
| P@1 (Flat) | 0.361 | 0.302 | GT 균형화 (airtable 34%→12%) |
| Recall (Flat) | 0.649 | 0.527 | 새 서버의 harder 쿼리 추가 |
| Confusion (Flat) | 0.452 | 0.322 | 서버 분포 균등화로 혼동 감소 |

수치 하락은 GT 편향 제거의 결과. 이전 수치는 airtable 과집중으로 과대평가됐음.

## 후속 실험

- **E2 (Embedding)**: 직접 임베딩 시 모델 비교 가능 (현재는 MCP-Zero pre-computed 고정)
- **E4 (Description Quality)**: 핵심 테제 검증 — enriched description으로 P@1 개선 여부
- Sequential 개선: Layer 1 top_k 증가 or soft gate(score threshold) 도입 고려

## Artifacts

- `data/results/e0_result.json` — raw metrics JSON
- `.claude/evals/E0-baseline.log` — run history (Run 1 + Run 2)
- W&B project: `mcp-discovery`
