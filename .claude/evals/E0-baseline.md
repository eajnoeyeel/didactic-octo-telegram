# EVAL: E0 — 1-Layer vs 2-Layer Architecture Validation

> Gate experiment. E1+ does not proceed unless E0 passes.
> Grader type: Code (deterministic)

## Success Criteria

- [ ] `src/pipeline/flat.py` (1-Layer) executes without error
- [ ] `src/pipeline/sequential.py` (2-Layer Sequential) executes without error
- [ ] `src/pipeline/parallel.py` (2-Layer Parallel) executes without error
- [ ] Precision@1 measured for all three on the same 80 seed GT queries
- [ ] Results logged to W&B run tagged `E0`

## Judgment Gate

```
2-Layer valid if:
  max(Sequential_P@1, Parallel_P@1) - FlatLayer_P@1 >= +5%p

→ PASS: proceed to E1
→ FAIL: investigate pipeline (check OQ-4 server classification errors)
```

## Regression Criteria

N/A — this is the baseline. Results become the regression floor for E1-E6.

## Metric Targets (pre-experiment, calibrate after)

| Strategy | Precision@1 target | Notes |
|----------|--------------------|-------|
| 1-Layer (flat) | — | baseline measurement |
| 2-Layer Sequential | > flat + 5%p | OQ-5 gate |
| 2-Layer Parallel | > flat + 5%p | OQ-5 gate |

## CLI

```bash
uv run python scripts/run_experiments.py --experiment E0
```

## pass@k

- Capability: pass@1 (single deterministic run per strategy)
- Gate decision: deterministic threshold, not probabilistic

## Artifacts

- `.claude/evals/E0-baseline.log` — run history
- `docs/experiments/E0-report.md` — release snapshot (post-run)
