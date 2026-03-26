# EVAL: E4 — Description Quality A/B (Core Thesis Validation)

> Most important experiment. Must pass for CTO demo.
> Grader type: Code (McNemar's test) + Model (GEO score validation)
> Depends on E1 best strategy selected.

## Success Criteria

- [ ] Version A pool constructed (Smithery original descriptions)
- [ ] Version B pool constructed (GEO 기법 적용: Statistics Addition, Fluency Optimization, Cite Sources)
- [ ] Identical query set run against both pools
- [ ] Lift = (P@1_B - P@1_A) / P@1_A × 100% computed
- [ ] McNemar's test p-value computed
- [ ] Spearman(geo_score, selection_rate) computed across all Pool tools
- [ ] OLS regression R² computed (6 GEO dimensions → selection_rate)

## Evidence Triangulation Gate

Pass if ≥ 2 of 3:
```
1. A/B Lift > 30%                    (causal)
2. Spearman r_s > 0.6, p < 0.05     (correlational)
3. OLS R² > 0.4                      (explanatory)
```

McNemar's test: p < 0.05 required independently.

## Regression Criteria

- [ ] Best strategy from E1 reproduces E1 Precision@1 within ±2%p (pass^3 = 1.00)
- [ ] Same 80 GT queries used

## Metric Targets

| Metric | Target |
|--------|--------|
| A/B Lift | > 30% |
| McNemar p-value | < 0.05 |
| Spearman r_s | > 0.6 |
| OLS R² | > 0.4 |

## Human Grader (OQ-3 dependency)

Version B descriptions require manual review before experiment:
```
[HUMAN REVIEW REQUIRED]
Change: Version B descriptions for mcp-arxiv, mcp-calculator, mcp-korean-news
Reason: GEO 기법 적용 품질 확인 — not too polished, not too poor
Risk: HIGH — over-optimizing Version B inflates lift artificially
```

## CLI

```bash
uv run python scripts/run_experiments.py --experiment E4 --pool description-quality
```

## pass@k

- Capability: pass@1 (single run, deterministic metrics)
- Evidence gate: ≥ 2/3 triangulation criteria met
