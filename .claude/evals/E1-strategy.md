# EVAL: E1 — Strategy Comparison (Sequential A vs Parallel B)

> Depends on E0 PASS.
> Grader type: Code (deterministic)
> Note: E1-C (Taxonomy-gated)는 Phase 13 gate 이후 추가 예정. 현재 eval은 구현 가능한 A/B만 포함.

## Success Criteria

- [ ] Sequential (A) Precision@1 measurable on Pool MCP-Zero (292 servers)
- [ ] Parallel (B) Precision@1 measurable on Pool MCP-Zero (292 servers)
- [ ] Both strategies use identical GT queries (474개 총, 194개 pool covered, all single-step)
- [ ] Server Recall@5, Tool Recall@10, MRR, Confusion Rate, Latency p95 all logged
- [ ] Results in W&B tagged `E1`

## Regression Criteria

**회귀 검증**: E0 exact 조건 (text-embedding-3-large 3072D, base_pool.json[:292], GT 194개)을
E1 프레임워크 내에서 재실행. E0 documented 값 (Flat=0.356, Sequential=0.325, Parallel=0.376) 대비
±2%p 이내여야 함. 이는 파이프라인 재현성 검증이며, E1 BGE-M3 결과를 E0 text-embedding-3-large
결과와 직접 비교하는 것이 아님.

- [ ] E0 baseline reproduced within ±2%p (pass^3 = 1.00)
- [ ] Same 474개 총 GT (194개 pool covered) used as E0

## Metric Targets

| Metric | Sequential A | Parallel B |
|--------|-------------|------------|
| Precision@1 | > E0 baseline | ≥ Sequential A |
| Server Recall@5 | >= 0.90 | >= 0.90 |
| Latency p95 | < 2s | < 3s |

> Targets calibrated after E0 run. K=5 per metrics-rubric.md (서버 50개 이상 → K=5).

## CLI

```bash
# 계획됨 (`scripts/run_experiments.py` + Parallel 전략 구현 후):
# uv run python scripts/run_experiments.py --experiment E1 --strategy sequential --pool base
# uv run python scripts/run_experiments.py --experiment E1 --strategy parallel --pool base
```

## pass@k

- Capability: pass@1 (deterministic pipelines)
- Regression: pass^3 = 1.00 for E0 baseline reproduction
