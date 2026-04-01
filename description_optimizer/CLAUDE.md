# CLAUDE.md — Description Optimizer

> 규칙과 참조 포인터만 둔다. 상세 컨텍스트는 별도 문서로 분리.
> 최종 업데이트: 2026-03-31

---

## 메타 규칙

- 이 파일은 요약 + source-of-truth 포인터만 유지한다.
- 구현 상세, 실험 내역, historical artifact는 해당 문서를 직접 읽는다.
- 루트 `CLAUDE.md`와 `.codex/AGENTS.md`의 제약을 상속한다.

---

## 서브프로젝트 한줄 요약

Description Optimizer는 MCP tool description을 retrieval-oriented text로 재작성해 검색 품질을 높이려는 실험 모듈이다.

---

## 현재 상태

- **브랜치:** `feat/description-optimizer`
- **상태:** 2026-03-31 기준 정리 완료, **재개 보류**
- **로드맵 위치:** `mcp_optimizer` 전체 계획에서는 **최종 backlog**
- **현재 결론:** `retrieval_description` 중심 전환은 유효했지만, 다음 병목은 prompt 추가 반복이 아니라 `gate throughput`과 long-tail regression 제어다.

---

## 먼저 읽을 문서

| 파일 | 용도 |
|------|------|
| `description_optimizer/docs/development-history.md` | 구현/실험 연표, 현재 결론, 남긴/삭제한 artifact, 재개 순서 |
| `docs/analysis/description-optimizer-mcp-zero-validation-20260330.md` | 최신 MCP-Zero retrieval validation |
| `docs/analysis/description-optimizer-root-cause-analysis.md` | historical regression 근본원인 분석 |
| `description_optimizer/docs/evaluation-design.md` | 보존된 평가 설계 |
| `description_optimizer/docs/research-analysis.md` | 학술 근거 + empirical validation 요약 |
| `description_optimizer/docs/research-phase2-synthesis.md` | grounded/retrieval-aligned 설계 근거 |
| `docs/superpowers/plans/2026-03-31-description-optimizer-resume-backlog.md` | 재개용 작업 계획 |

---

## 현재 코드 경계

- 구현 모듈: `src/description_optimizer/`
- 핵심 파일:
  - `models.py` — `OptimizationContext`, 결과 모델
  - `optimizer/prompts.py` — grounded/ungrounded prompt builder
  - `optimizer/llm_optimizer.py` — LLM rewrite
  - `pipeline.py` — `run_with_tool()`, `run_batch_with_tools()`
  - `quality_gate.py` — similarity, hallucination, info preservation, faithfulness, contamination
- 실행 스크립트:
  - `scripts/optimize_gt_tools.py`
  - `scripts/run_grounded_ab_comparison.py`
  - `scripts/run_retrieval_ab_eval.py`

---

## 재개 원칙

- `optimized_description`를 canonical retrieval text로 되돌리지 않는다.
- GEO는 hard gate가 아니라 diagnostic signal로만 취급한다.
- sibling name 기반 disambiguation을 그대로 반복하지 않는다.
- 새로운 prompt 수정 전에 `gate_rejected` 유형과 long-tail regression부터 정리한다.
- 재개는 루트 계획상 post-core backlog에서만 진행한다.

---

## 주요 데이터 artifact

| 파일 | 의미 |
|------|------|
| `data/verification/mcp_zero_gt_filtered.jsonl` | MCP-Zero pool 교집합 GT |
| `data/verification/mcp_zero_gt_optimized_descriptions.jsonl` | 최신 GT tool optimization 결과 |
| `data/verification/mcp_zero_query_level_eval.json` | query-level primary metrics |
| `data/verification/mcp_zero_retrieval_ab_report.json` | tool-average diagnostic metrics |
| `data/verification/gt_optimized_descriptions.jsonl` | historical regression artifact |
| `data/verification/retrieval_ab_report.json` | historical retrieval A/B artifact |

---

## 자주 쓰는 명령

```bash
uv run pytest tests/unit/test_description_optimizer/ -v
uv run pytest tests/verification/ -v
uv run ruff check src/ tests/
PYTHONPATH=src uv run python scripts/optimize_gt_tools.py
PYTHONPATH=src uv run python scripts/run_retrieval_ab_eval.py \
  --tools data/raw/mcp_zero_servers.jsonl \
  --ground-truth data/verification/mcp_zero_gt_filtered.jsonl \
  --optimized data/verification/mcp_zero_gt_optimized_descriptions.jsonl \
  --top-k 10 \
  --output data/verification/mcp_zero_retrieval_ab_report.json
```
