# EVAL: E0 — 1-Layer vs 2-Layer Architecture Validation

> Gate experiment. E1+ does not proceed unless E0 passes.
> Grader type: Code (deterministic)

## Success Criteria

- [ ] `src/pipeline/flat.py` (1-Layer) executes without error — **implemented**
- [ ] `src/pipeline/sequential.py` (2-Layer Sequential) executes without error — **implemented**
- [ ] `src/pipeline/parallel.py` (2-Layer Parallel) executes without error — **Phase 7 구현 후 실행**
- [ ] Precision@1 measured on MCP-Atlas per-step ~150-240 + self seed 80 GT queries (~230-320 total, all single-step)
- [ ] Results logged to W&B run tagged `E0`

> **Note**: `run_e0.py`는 현재 Flat + Sequential만 실행. Parallel은 Phase 7(hybrid.py + parallel.py) 구현 후 추가.

## Judgment Gate

```
2-Layer valid if:
  Sequential_P@1 - FlatLayer_P@1 >= +5%p

→ PASS: proceed to E1
→ FAIL: investigate pipeline (check OQ-4 server classification errors)
```

> **Note**: Parallel(E0-C)은 Phase 7 구현 후 추가 측정. Sequential(E0-B) 단독으로 gate 판정 가능. Parallel 결과는 보충 데이터로 E1에서 활용.

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
uv run python scripts/run_e0.py                           # 현재: Flat + Sequential
# uv run python scripts/run_experiments.py --experiment E0  # Phase 10 이후 (Parallel 포함)
```

## pass@k

- Capability: pass@1 (single deterministic run per strategy)
- Gate decision: deterministic threshold, not probabilistic

## Artifacts

- `.claude/evals/E0-baseline.log` — run history
- `docs/experiments/E0-report.md` — release snapshot (post-run)
