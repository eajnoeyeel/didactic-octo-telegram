# Description Optimizer 비교 검증 TODO

> **Plan:** `docs/superpowers/plans/2026-03-28-description-optimizer-comparison-verification.md`
> **Branch:** `feat/description-optimizer`
> **Skill:** `superpowers:subagent-driven-development` (recommended)
> **Date:** 2026-03-28

## 배경

Description Optimizer가 구현 완료되었고 (10 tasks, 117 tests, 99% coverage), 이제 **실제 MCP tool 데이터에 대해 최적화 전/후를 비교 검증**하는 단계이다.

### 현재 상태
- 소스: `src/description_optimizer/` (analyzer, optimizer, pipeline, quality_gate, models)
- 테스트: `tests/unit/test_description_optimizer/` (52 tests) + `tests/verification/` (65 tests) = 117 PASS
- 데이터: `data/raw/servers.jsonl` — 50 servers, 861 tools
- dry-run 분석 결과: 평균 GEO 0.102, 90%가 0.20 미만 (최적화 전 원본 상태)

### 검증 목표
1. 실제 LLM(GPT-4o-mini)으로 30개 샘플 tool을 최적화하고 before/after GEO 비교
2. 6개 차원별 개선폭 정량 측정
3. Quality Gate가 나쁜 최적화를 걸러내는지 확인
4. 사람이 side-by-side로 원본 vs 최적화본을 비교 리뷰

---

## Tasks

### Task 1: 대표 샘플 선정 스크립트 (API key 불필요)
- [ ] `scripts/run_comparison_verification.py` 생성 — 데이터 로드 + stratified sampling
- [ ] `--phase sample` 실행하여 `data/verification/sample_tools.json` 생성
- [ ] 커밋: `feat(verification): add comparison verification script — Phase 1 sample selection`

### Task 2: 전체 파이프라인 실행 + 결과 저장 (OPENAI_API_KEY 필요)
- [ ] `phase_optimize()` 함수 추가 — 30개 tool 파이프라인 실행
- [ ] `main()` + argparse 연결
- [ ] `--phase optimize` 실행하여 `data/verification/optimization_results.jsonl` 생성
- [ ] 커밋: `feat(verification): add Phase 2 — full pipeline execution on sample`

### Task 3: 차원별 비교 분석 + Side-by-Side 리포트 생성
- [ ] `phase_report()` 함수 + `_write_report()` 함수 작성
- [ ] `--phase report` 실행하여 `data/verification/comparison_report.md` 생성
- [ ] 커밋: `feat(verification): add Phase 3 — comparison report generator`

### Task 4: 비교 검증 자동 Assertion 테스트 (12 tests)
- [ ] `tests/verification/test_comparison_verification.py` 생성
- [ ] 테스트 클래스: OverallQuality, GEOImprovement, DimensionImprovement, SemanticPreservation, QualityGateEffectiveness
- [ ] Phase 2 미실행 시 skip, 실행 후 모두 PASS 확인
- [ ] 커밋: `test(verification): add automated comparison verification assertions`

### Task 5: Heuristic Analyzer 감도(sensitivity) 심화 검증 (12 tests)
- [ ] `tests/verification/test_heuristic_sensitivity.py` 생성
- [ ] 6개 차원 각각에 대해 "신호 추가 시 점수 증가" 검증
- [ ] Progressive ordering 테스트 (tier1 < tier2 < tier3)
- [ ] `uv run pytest tests/verification/test_heuristic_sensitivity.py -v` 모두 PASS
- [ ] 커밋: `test(verification): add heuristic analyzer sensitivity tests (12 tests)`

### Task 6: 전체 통합 실행 + 최종 검증 (OPENAI_API_KEY 필요)
- [ ] Phase 1 (sample) + Phase 2 (optimize) + Phase 3 (report) 순서대로 실행
- [ ] `uv run pytest tests/verification/test_comparison_verification.py -v` PASS 확인
- [ ] `uv run pytest tests/verification/ -v` 전체 ~89 tests PASS 확인
- [ ] 커밋: `feat(verification): add comparison verification results and report`

### Task 7: 사람이 리뷰 (수동)
- [ ] `data/verification/comparison_report.md` Section 3 — side-by-side 비교 읽기
- [ ] 환각(hallucination) 없는지 확인
- [ ] 의미 보존 확인
- [ ] 차원별 개선 확인 (Section 2)
- [ ] Quality Gate 거부 사유 확인 (Section 4)

---

## 실행 커맨드 요약

```bash
# Task 1: 샘플 선정 (API key 불필요)
PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase sample

# Task 2: 최적화 실행 (OPENAI_API_KEY 필요)
PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase optimize

# Task 3: 리포트 생성
PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase report

# Task 4-5: 테스트
uv run pytest tests/verification/ -v

# 전체 한번에
PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase all
```

## 주의사항

- **Task 2, 6은 `.env`에 `OPENAI_API_KEY`가 필요함** (GPT-4o-mini + text-embedding-3-small 사용)
- **예상 비용:** ~$0.10-0.50 (30 tools × GPT-4o-mini + embedding)
- Task 1, 3, 4, 5는 API key 없이 실행 가능
- 상세 계획은 `docs/superpowers/plans/2026-03-28-description-optimizer-comparison-verification.md` 참조
