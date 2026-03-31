# EVAL: E7 — GEO Score Method Comparison

> OQ-1 resolution experiment. Determines scoring method for Description Quality Score.
> Grader type: Code (deterministic) + Human (agreement validation)

## Success Criteria

- [ ] Heuristic scorer (`src/analytics/geo_score.py`) produces GEO 6D scores for all Pool tools
- [ ] LLM scorer (GPT-4o-mini, 3-judge ensemble) produces GEO 6D scores for all Pool tools
- [ ] Description Smells 4D scorer produces Accuracy/Functionality/Completeness/Conciseness scores
- [ ] Spearman(score, selection_rate) computed for all 3 methods
- [ ] Human agreement measured on 20-30 description sample
- [ ] Results logged to W&B run tagged `E7`

## Judgment Gate

```text
Method selection:
  Both r_s >= 0.7          → Heuristic (cheaper, deterministic)
  LLM >= 0.7, heur < 0.5  → LLM
  LLM >= 0.7, heur 0.5-0.7→ Hybrid (heuristic + LLM on low-confidence)
  Both < 0.5               → Re-evaluate rubric dimensions
```

## Regression Criteria

- [ ] E4 baseline results reproducible (same GT, same pipeline)

## Metric Targets (pre-experiment, calibrate after)

| Method | Spearman target | Human agreement target | Notes |
|---|---|---|---|
| E7-A Heuristic (GEO 6D) | r_s > 0.6 | > 0.6 | Free, deterministic |
| E7-B LLM (GEO 6D) | r_s > 0.7 | > 0.7 | ~$0.03/30 tools |
| E7-C Smells 4D | r_s > 0.6 | — | External rubric baseline |

## Cross-Validation with E4

- E7 scoring method applied to E4 Version A/B descriptions
- Verify that Version B (GEO-applied) scores higher than Version A under chosen method
- If not, scoring method lacks construct validity

## CLI

```bash
# 계획됨 (Phase 9+ 구현 후):
# uv run python scripts/run_experiments.py --experiment E7 --scorer heuristic
# uv run python scripts/run_experiments.py --experiment E7 --scorer llm
# uv run python scripts/run_experiments.py --experiment E7 --scorer smells
```

## pass@k

- Capability: pass@3 >= 0.90 (scorer reproducibility across runs)
- Human agreement: single evaluation (not probabilistic)

## Artifacts

- `.claude/evals/E7-geo-scoring.log` — run history
- `docs/experiments/E7-report.md` — release snapshot (post-run)
