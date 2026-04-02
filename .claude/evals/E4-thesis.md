# EVAL: E4 — Description Quality A/B (Core Thesis Validation)

> Most important experiment. Must pass for CTO demo.
> Grader type: Code (McNemar's test) + Model (GEO score validation)
> Depends on E1 best strategy selected.
> External validation: Description Smells 논문 (arxiv:2602.18914) — description 품질 → 선택률 인과 관계 사전 검증 (+11.6%, p<0.001). 우리 차별점: smell 유무 비교가 아닌 GEO 기법을 통한 체계적 개선 방법론 제시.

## Success Criteria

- [ ] Version A pool constructed (Smithery original descriptions)
- [ ] Version B pool constructed (GEO 기법 적용: Statistics Addition, Fluency Optimization, Cite Sources)
  - ✅ stats (Statistics Addition): 수치/커버리지/성능 데이터 추가
  - ✅ precision (Cite Sources/Technical Terms): 표준/API/프로토콜 정확도
  - ✅ clarity (Fluency Optimization): 첫 문장 구조 명확화
  - ⬜ disambiguation: Version B에서 의도적으로 미개선 (독립 변수 격리)
  - ⬜ parameter_coverage: Version B에서 미개선
  - ⬜ boundary: Version B에서 미개선
- [ ] Identical query set run against both pools
- [ ] Lift = (P@1_B - P@1_A) / P@1_A × 100% computed
- [ ] McNemar's test p-value computed
- [ ] Spearman(geo_score, selection_rate) computed across all Pool tools
- [ ] OLS regression R² computed (6 GEO dimensions → selection_rate)
- [ ] Description Smells 4D scores computed for comparison (Accuracy/Functionality/Completeness/Conciseness)

## Evidence Triangulation Gate

Per `docs/design/metrics-rubric.md` §Evidence Triangulation:

```
Criteria:
  1. A/B Lift > 30%, McNemar p < 0.05  (causal — Primary)
  2. Spearman r_s > 0.6, p < 0.05     (correlational)
  3. OLS R² > 0.4                      (explanatory)

Judgment (metrics-rubric.md §Evidence Triangulation):
  3개 모두 통과  → 강한 증거
  Primary + 1개  → 보통 증거
  Primary만 통과 → 약한 증거
  Primary 미통과 → 테제 기각
```

## Regression Criteria

- [ ] Best strategy from E1 reproduces E1 Precision@1 within ±2%p (pass^3 = 1.00)
- [ ] Same 474개 총 GT (194개 pool covered, all single-step) used

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
# 계획됨 (`scripts/run_experiments.py` 구현 후):
# uv run python scripts/run_experiments.py --experiment E4 --pool description-quality
```

## pass@k

- Capability: pass@1 (single run, deterministic metrics)
- Evidence gate: Primary required + ≥ 1/2 remaining for moderate evidence
