# EVAL: E1 — Strategy Comparison (Sequential A vs Parallel B)

> Depends on E0 PASS.
> Grader type: Code (deterministic)
> Note: E1-C (Taxonomy-gated)는 Phase 13 gate 이후 추가 예정. 현재 eval은 구현 가능한 A/B만 포함.

## Success Criteria

- [ ] Sequential (A) Precision@1 measurable on Pool MCP-Zero (308 servers)
- [ ] Parallel (B) Precision@1 measurable on Pool MCP-Zero (308 servers)
- [ ] Both strategies use identical GT queries (MCP-Atlas per-step ~150-240 + self seed 80 = ~230-320 total, all single-step)
- [ ] Server Recall@5, Tool Recall@10, MRR, Confusion Rate, Latency p95 all logged
- [ ] Results in W&B tagged `E1`

## Regression Criteria

- [ ] E0 baseline reproduced within ±2%p (pass^3 = 1.00)
- [ ] Same ~230-320 GT queries used as E0 (MCP-Atlas per-step + self seed 80)

## Metric Targets

| Metric | Sequential A | Parallel B |
|--------|-------------|------------|
| Precision@1 | > E0 baseline | ≥ Sequential A |
| Server Recall@5 | > 0.50 | > 0.50 |
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
