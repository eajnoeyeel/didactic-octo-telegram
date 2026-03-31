# Description Optimizer — Development History

> 최종 업데이트: 2026-03-31
> 상태: 정리 완료, 재개 보류

---

## 1. 현재 상태

`description_optimizer`는 브랜치에서 구현과 실험까지 진행했지만, 현재 프로젝트 우선순위에서는 **최종 backlog**로 이동했다. 코드는 남기고, future resume에 필요한 문서와 데이터만 추려 두었다.

보류 이유는 세 가지다.

1. `retrieval_description` 중심 refactor가 부분 개선은 보였지만, 남은 문제는 단순 prompt 반복보다 `gate throughput`과 long-tail regression 제어에 가깝다.
2. core pipeline의 Phase 6-13, E0-E3, E5-E6가 아직 남아 있어 description optimization을 계속 파면 전체 프로젝트 진행이 뒤틀린다.
3. branch-side 실험 문서와 generated artifact가 많아져서, 재개 전에 source-of-truth를 먼저 정리할 필요가 있었다.

---

## 2. 구현 범위 요약

현재 코드베이스에 남겨 둔 핵심 구현은 아래다.

- `src/description_optimizer/models.py`
  - `OptimizationContext`
  - optimization result models
- `src/description_optimizer/optimizer/prompts.py`
  - grounded / ungrounded prompt builders
- `src/description_optimizer/optimizer/llm_optimizer.py`
  - LLM rewrite path
- `src/description_optimizer/pipeline.py`
  - `run_with_tool()`, `run_batch_with_tools()`
- `src/description_optimizer/quality_gate.py`
  - similarity, hallucination, info preservation, faithfulness, contamination checks
- `scripts/optimize_gt_tools.py`
- `scripts/run_grounded_ab_comparison.py`
- `scripts/run_retrieval_ab_eval.py`

---

## 3. 실험 연표

| 날짜 | 단계 | 남긴 것 | 핵심 결론 |
|------|------|---------|-----------|
| 2026-03-28 | 30-tool sample comparison scaffold | `sample_tools.json`, `optimization_results.jsonl`, `grounded_optimization_results.jsonl` | 원본 description만으로는 환각과 정보 손실이 잦아 grounded context가 필요함 |
| 2026-03-29 | Grounded optimization 구현 | `OptimizationContext`, grounded prompt, hallucination/info-preservation gate | schema + sibling context는 환각 억제에 효과가 있었음 |
| 2026-03-29 | Grounded vs ungrounded A/B | `docs/analysis/grounded-ab-comparison-report.md` | GEO 기준으로는 grounded가 우세했지만, 이것만으로 retrieval 개선을 보장하지 못함 |
| 2026-03-29 | Historical retrieval regression 확인 | `gt_optimized_descriptions.jsonl`, `retrieval_ab_report.json` | `optimized_description`를 그대로 임베딩하면 `P@1`이 하락할 수 있음 |
| 2026-03-30 | Root cause analysis | `docs/analysis/description-optimizer-root-cause-analysis.md` | 문제는 GEO 자체보다 retrieval 경로 불일치, 보상 왜곡, sibling contamination |
| 2026-03-30 | Retrieval-aligned refactor + MCP-Zero validation | `mcp_zero_gt_filtered.jsonl`, `mcp_zero_gt_optimized_descriptions.jsonl`, `mcp_zero_query_level_eval.json`, `mcp_zero_retrieval_ab_report.json` | `retrieval_description` 중심 refactor는 query-level `P@1`, `MRR`을 개선했지만 gate reject가 25/32로 높음 |
| 2026-03-31 | 문서/데이터 정리 + backlog 이동 | 이 문서, 루트 계획 업데이트, superseded artifact 삭제 | feature는 보존하되 현재 로드맵에서는 마지막 backlog로 고정 |

---

## 4. 현재 해석

### 최신 유효 결론

- `retrieval_description`을 canonical retrieval text로 쓰는 방향은 맞다.
- latest MCP-Zero query-level 결과는 아래와 같다.
  - `P@1`: `0.2753 -> 0.3427`
  - `Recall@10`: `0.6517 -> 0.6629`
  - `MRR`: `0.4136 -> 0.4439`
- 다음 병목은 GEO 점수 상승 여부가 아니라:
  - `gate_rejected 25/32`
  - 일부 domain에서의 long-tail rank regression

### 반복하면 안 되는 접근

- `optimized_description`를 다시 임베딩 canonical text로 삼기
- GEO score를 hard gate로 되돌리기
- sibling tool name을 직접 나열하는 disambiguation 실험 반복
- 새로운 prompt variation을 먼저 만들고 나중에 gate reject 원인을 해석하기

---

## 5. 현재 남겨 둔 source-of-truth

### 재개 시 먼저 읽을 것

1. `description_optimizer/CLAUDE.md`
2. `description_optimizer/docs/development-history.md`
3. `docs/analysis/description-optimizer-mcp-zero-validation-20260330.md`
4. `docs/analysis/description-optimizer-root-cause-analysis.md`
5. `docs/superpowers/plans/2026-03-31-description-optimizer-resume-backlog.md`

### 유지한 핵심 데이터

| 파일 | 이유 |
|------|------|
| `data/verification/sample_tools.json` | grounded vs ungrounded 비교의 재현 입력 |
| `data/verification/optimization_results.jsonl` | ungrounded sample 결과 |
| `data/verification/grounded_optimization_results.jsonl` | grounded sample 결과 |
| `data/verification/gt_optimized_descriptions.jsonl` | historical regression artifact |
| `data/verification/retrieval_ab_report.json` | historical retrieval regression report |
| `data/verification/mcp_zero_gt_filtered.jsonl` | latest evaluation set |
| `data/verification/mcp_zero_gt_optimized_descriptions.jsonl` | latest optimization output |
| `data/verification/mcp_zero_query_level_eval.json` | latest primary metrics |
| `data/verification/mcp_zero_retrieval_ab_report.json` | latest diagnostic metrics |

### 이번 정리에서 제거한 것

- `TODO.md`
- `docs/analysis/description-optimizer-doc-change-plan.md`
- `docs/progress/grounded-optimization-handoff.md`
- `description_optimizer/docs/progress.md`
- `data/verification/comparison_report.md`
- `data/verification/gt_optimized_descriptions_v2.jsonl`
- `data/verification/retrieval_3way_ab_report.json`
- `data/verification/retrieval_3way_ab_gt_report.json`
- `data/verification/retrieval_3way_ab_gt_report_v2.json`

삭제 기준은 "현재 source-of-truth가 아니고, 남겨 둔 raw/result artifact에서 재생성 가능하거나 intermediate attempt에 불과한가"였다.

---

## 6. 재개 순서

재개 시에는 아래 순서를 고정한다.

1. `gate_rejected 25/32`를 유형별로 정리한다.
2. similarity threshold와 contamination rule의 민감도를 재검증한다.
3. prompt rule 변경은 그 다음에 최소 범위로만 한다.
4. MCP-Zero GT subset에 다시 optimize/eval을 돌린다.
5. long-tail regression이 남아 있으면 그때 disambiguation 설계를 다시 다룬다.

재개용 상세 작업 체크리스트는 `docs/superpowers/plans/2026-03-31-description-optimizer-resume-backlog.md`에 정리했다.
