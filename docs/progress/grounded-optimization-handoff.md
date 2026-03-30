# Grounded Optimization — 세션 핸드오프 문서

> **Date:** 2026-03-29
> **Branch:** `feat/description-optimizer`
> **Plan:** `docs/superpowers/plans/2026-03-29-description-optimizer-grounded-optimization.md`

---

## 완료된 작업

### Task 1: Add OptimizationContext Model (DONE)
- **Commit:** `b0879c5`
- `src/description_optimizer/models.py` — `OptimizationContext` 클래스 추가
  - Fields: `tool_id`, `original_description`, `input_schema: dict | None`, `sibling_tools: list[dict]`
  - Computed field: `parameter_names` (schema에서 property keys 추출)
- `tests/unit/test_description_optimizer/test_grounded_prompts.py` — 4개 테스트 생성
- Spec Review: PASS

### Task 2: Rewrite Prompts for Grounded Optimization (DONE)
- **Commit:** 직후 커밋 (Task 1 다음)
- `src/description_optimizer/optimizer/prompts.py` 변경:
  - `SYSTEM_PROMPT` → anti-hallucination 버전으로 교체 (AUGMENT, NEVER invent 규칙)
  - `build_grounded_prompt()` 함수 추가 (input_schema + sibling_tools + anti-hallucination)
  - `_build_grounded_guidance()` 헬퍼 추가
  - `build_optimization_prompt()` — backward compatibility 유지 (미변경)
  - `import json` 추가
- `tests/unit/test_description_optimizer/test_grounded_prompts.py` — 5개 테스트 추가 (총 9개)
- Spec Review: PASS

---

## 완료된 작업 (Task 3-10)

### Task 3: Extend Optimizer ABC and LLM Optimizer to Accept Context (DONE)
- **Commit:** `56c7817`
- `base.py` — `optimize()` 시그니처에 `context: OptimizationContext | None = None` 추가
- `llm_optimizer.py` — context 있으면 `build_grounded_prompt`, 없으면 `build_optimization_prompt`
- 테스트 2개 추가 (9/9 pass)

### Task 4: Update Pipeline to Accept MCPTool and Build Context (DONE)
- **Commit:** `8b26a70`
- `pipeline.py` — `run_with_tool()`, `run_batch_with_tools()`, `_run_internal()` 추가
- 기존 `run()` → `_run_internal()` 위임으로 리팩토링
- 테스트 2개 추가 (12/12 pass)

### Task 5: Add Hallucination Detection Gate (DONE)
- **Commit:** `8b5564a`
- `quality_gate.py` — `check_hallucinated_params()` 추가
- Backtick 파라미터 추출 → input_schema 교차 검증
- 테스트 4개 추가 (12/12 pass)

### Task 6: Add Information Preservation Gate (DONE)
- **Commit:** `f5fcbae`
- `quality_gate.py` — `check_info_preservation()` 추가
- 숫자/통계 + 기술 용어 보존 검증
- 테스트 4개 추가 (16/16 pass)

### Task 7: Integrate New Gates into Pipeline (DONE)
- **Commit:** `46ac752`
- `FullGateResult`에 `hallucination_result`, `info_preservation_result` 추가
- `evaluate()` 확장 (input_schema, optimized_text, original_text)
- Pipeline에서 context 기반 gate 파라미터 전달
- 테스트 1개 추가 (74/74 pass)

### Task 8: Update Scripts for Grounded Optimization (DONE)
- **Commit:** `b206c58`
- `optimize_descriptions.py` — MCPTool + `run_batch_with_tools()` 사용
- `run_comparison_verification.py` — `input_schema` 포함 로딩 + `run_with_tool()`

### Task 9: Tool Selection A/B Evaluation Script (DONE)
- **Commit:** `052247a`
- `scripts/run_selection_eval.py` 생성
- `tests/evaluation/test_selection_eval.py` 생성 (2/2 pass)

### Task 10: Run Full Test Suite and Fix Regressions (DONE)
- **Commit:** `234dbd3` (formatting)
- 389 tests pass (integration 제외), 92% coverage
- Ruff lint + format clean

---

## 의존관계

```
Task 1 ✅ → Task 2 ✅ → Task 3 → Task 4 → Task 7 → Task 8 → Task 9 → Task 10
                                    Task 5 → Task 7
                                    Task 6 → Task 7
```

**모든 태스크 완료 (2026-03-29)**

---

## 핵심 컨텍스트

- **근본 문제:** LLM이 input_schema 없이 파라미터/제한사항 환각, 전체 재작성으로 기존 정보 파괴
- **해결 방향:** Grounded optimization (실제 데이터 기반) + Augmentation (보존+추가) + 환각 탐지 Gate
- **데이터:** `data/raw/servers.jsonl` — 861개 tool 전부 `input_schema` 보유 (Smithery 크롤링, 100% authentic)
- **North Star:** 최적화된 설명이 실제 tool selection accuracy (Precision@1)를 향상시키는가?

---

## A/B 비교 결과 — fluency 기반 재실행 (2026-03-29)

30개 tool 대상 Grounded vs Ungrounded 비교 완료 (boundary→fluency 차원 교체 후 fresh re-run).
**상세 보고서: `docs/analysis/grounded-ab-comparison-report.md`**

| 지표 | Ungrounded | Grounded | 비고 |
|------|-----------|----------|------|
| 성공률 | 17/30 (57%) | **21/30 (70%)** | Grounded가 더 많은 tool 최적화 |
| 평균 GEO 향상 | +0.1603 | **+0.1861** | **Grounded가 수치에서도 승리** |
| Gate 거부 | 13건 | **9건** | Grounded가 더 적은 품질 위반 |
| Per-tool 승부 | 3승 | **11승** (1 tie) | **Grounded 압도적** |
| 차원별 승부 | 1승 | **5승** | clarity, param_cov, fluency, stats, precision |

**결론:** boundary 차원 제거로 GEO-level Goodhart 완화. 이전 ungrounded의 GEO 우위(+0.0372)가 역전되어 grounded가 +0.0258로 승리. Per-tool도 8:12→11:3으로 완전 역전. 후속 P@1 A/B에서 GEO 향상이 retrieval 향상으로 이어지지 않음 확인 (δP@1 = -0.069). 근본원인: `docs/analysis/description-optimizer-root-cause-analysis.md`

### 다음 단계

1. ~~**P@1 end-to-end 검증**~~ — 완료 (δP@1 = -0.069)
2. ~~**근본원인 분석**~~ — 완료 (2026-03-30)
3. **Retrieval 경로 재정렬** — `search_description`을 실제 임베딩/평가 경로에 연결
4. **3-way A/B 평가** — original vs optimized vs search
5. **GEO diagnostic 전환 + disambiguation 재설계**
6. **RAGAS faithfulness 파이프라인 통합**
