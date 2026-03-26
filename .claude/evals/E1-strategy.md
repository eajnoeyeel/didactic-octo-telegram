# EVAL: E1 — Strategy Comparison (Sequential A vs Parallel B)

> Depends on E0 PASS.
> Grader type: Code (deterministic)

## Success Criteria

- [ ] Sequential (A) Precision@1 measurable on Pool Base (50 servers)
- [ ] Parallel (B) Precision@1 measurable on Pool Base (50 servers)
- [ ] Both strategies use identical GT queries (80 seed set)
- [ ] Server Recall@3, Tool Recall@10, MRR, Confusion Rate, Latency p95 all logged
- [ ] Results in W&B tagged `E1`

## Regression Criteria

- [ ] E0 baseline reproduced within ±2%p (pass^3 = 1.00)
- [ ] Same 80 GT queries used as E0

## Metric Targets

| Metric | Sequential A | Parallel B |
|--------|-------------|------------|
| Precision@1 | > E0 baseline | ≥ Sequential A |
| Server Recall@3 | > 0.50 | > 0.50 |
| Latency p95 | < 2s | < 3s |

> Targets calibrated after E0 run.

## CLI

```bash
uv run python scripts/run_experiments.py --experiment E1 --strategy sequential --pool base
uv run python scripts/run_experiments.py --experiment E1 --strategy parallel --pool base
```

## pass@k

- Capability: pass@1 (deterministic pipelines)
- Regression: pass^3 = 1.00 for E0 baseline reproduction
