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

## 남은 작업 (Task 3-10)

### Task 3: Extend Optimizer ABC and LLM Optimizer to Accept Context (PENDING)
- `src/description_optimizer/optimizer/base.py` — `optimize()` 시그니처에 `context: OptimizationContext | None = None` 추가
- `src/description_optimizer/optimizer/llm_optimizer.py` — context 있으면 `build_grounded_prompt` 사용, 없으면 기존 `build_optimization_prompt` 사용
- `tests/unit/test_description_optimizer/test_llm_optimizer.py` — context-aware 테스트 추가

### Task 4: Update Pipeline to Accept MCPTool and Build Context (PENDING)
- `src/description_optimizer/pipeline.py` — `run_with_tool(tool: MCPTool, sibling_tools)` 메서드 추가
- `_run_internal()` 로 공통 로직 추출, `run()` (legacy) + `run_with_tool()` (grounded) 분리
- `run_batch_with_tools()` 추가

### Task 5: Add Hallucination Detection Gate (PENDING)
- `src/description_optimizer/quality_gate.py` — `check_hallucinated_params(optimized, input_schema)` 추가
- Backtick으로 감싼 파라미터 추출 → input_schema properties와 교차 검증

### Task 6: Add Information Preservation Gate (PENDING)
- `src/description_optimizer/quality_gate.py` — `check_info_preservation(original, optimized)` 추가
- 원본의 숫자/통계 + 기술 용어가 최적화본에 보존되었는지 검증

### Task 7: Integrate New Gates into Pipeline (PENDING)
- `FullGateResult`에 `hallucination_result`, `info_preservation_result` 추가
- `evaluate()` 메서드 확장 (input_schema, optimized_text, original_text 파라미터 추가)
- Pipeline `_run_internal()`에서 gate 호출 시 새 파라미터 전달

### Task 8: Update Scripts for Grounded Optimization (PENDING)
- `scripts/optimize_descriptions.py` — `MCPTool` 객체 로딩 + `run_batch_with_tools()` 사용
- `scripts/run_comparison_verification.py` — `input_schema` 포함하여 로딩

### Task 9: Tool Selection A/B Evaluation Script (PENDING)
- `scripts/run_selection_eval.py` — 원본 vs 최적화 설명으로 Precision@1 비교
- `tests/evaluation/test_selection_eval.py` — 평가 로직 테스트

### Task 10: Run Full Test Suite and Fix Regressions (PENDING)
- 전체 테스트 실행 + 커버리지 확인 + lint 정리

---

## 의존관계

```
Task 1 ✅ → Task 2 ✅ → Task 3 → Task 4 → Task 7 → Task 8 → Task 9 → Task 10
                                    Task 5 → Task 7
                                    Task 6 → Task 7
```

**다음 세션 시작점: Task 3**

---

## 재개 방법

다음 세션에서 아래 명령으로 시작:

```
Plan `docs/superpowers/plans/2026-03-29-description-optimizer-grounded-optimization.md`의
Task 3부터 Subagent-Driven Development로 계속 진행해줘.
Task 1, 2는 완료됨. 핸드오프 문서: `docs/progress/grounded-optimization-handoff.md`
```

---

## 핵심 컨텍스트

- **근본 문제:** LLM이 input_schema 없이 파라미터/제한사항 환각, 전체 재작성으로 기존 정보 파괴
- **해결 방향:** Grounded optimization (실제 데이터 기반) + Augmentation (보존+추가) + 환각 탐지 Gate
- **데이터:** `data/raw/servers.jsonl` — 861개 tool 전부 `input_schema` 보유 (Smithery 크롤링, 100% authentic)
- **North Star:** 최적화된 설명이 실제 tool selection accuracy (Precision@1)를 향상시키는가?
