# Description Optimizer — 진행 현황

> 최종 업데이트: 2026-03-30
> 브랜치: `feat/description-optimizer`

---

## 현재 상태

| 항목 | 상태 |
|------|------|
| 구현 상태 | retrieval-aligned refactor 반영 완료 |
| canonical field | `retrieval_description` |
| GEO 역할 | diagnostic-only |
| 최신 검증 | MCP-Zero filtered GT 기준 offline validation 완료 |
| targeted verification | `230 passed` |
| lint 상태 | changed-file `ruff check` PASS |

---

## 이번 단계에서 완료된 일

### 1. Retrieval-aligned refactor

- `MCPTool`에 `retrieval_description` 추가
- indexing/search path가 `retrieval_description -> description` 순으로 텍스트 선택
- GEO 기반 skip 제거
- Quality Gate를 retrieval-safe checks 중심으로 재정렬
- evaluation/reporting이 `Recall@K`, `MRR`, `P@1`을 기록하도록 정리

### 2. MCP-Zero 검증용 artifact 생성

- filtered GT 생성:
  - `data/verification/mcp_zero_gt_filtered.jsonl`
  - `178 queries / 32 tools / 10 servers`
- GT tool optimization 결과 생성:
  - `data/verification/mcp_zero_gt_optimized_descriptions.jsonl`
  - `7 success / 25 gate_rejected`

### 3. 최신 성능 검증

Primary query-level readout:

| Metric | Original | Optimized | Delta |
|--------|----------|-----------|-------|
| `P@1` | `0.2753` | `0.3427` | `+0.0674` |
| `Recall@10` | `0.6517` | `0.6629` | `+0.0112` |
| `MRR` | `0.4136` | `0.4439` | `+0.0304` |

보강 해석:
- top-1 discordant pairs: `13 win / 1 loss`
- `delta P@1` 95% CI: `[+0.0281, +0.1067]`
- `delta MRR` 95% CI: `[+0.0069, +0.0529]`
- `delta Recall@10` 95% CI: `[-0.0112, +0.0393]`

---

## 현재 해석

1. retrieval-aligned 방향 전환 자체는 유효했다.
2. 개선은 주로 top-1 / top-few ranking에서 관찰된다.
3. 전체 효과가 제한적인 이유는 optimizer 성능보다 `gate_rejected 25/32`가 더 큰 병목이기 때문이다.
4. 일부 long-tail query에서는 rank가 악화되어 추가 회귀 통제가 필요하다.

---

## 다음 우선순위

1. gate reject 25건을 유형별로 분해한다.
2. similarity threshold `0.75`의 민감도를 재검증한다.
3. long-tail regression이 큰 `exa`, `calculator` 계열 쿼리를 별도 분석한다.
4. `Recall@10` 개선을 더 안정적으로 만들 수 있는 prompt/gate 조합을 찾는다.

---

## 핵심 참조 문서

| 문서 | 용도 |
|------|------|
| `description_optimizer/CLAUDE.md` | 서브프로젝트 운영 요약 |
| `description_optimizer/docs/evaluation-design.md` | 평가 기준 및 최신 결과 |
| `description_optimizer/docs/research-analysis.md` | 학술 근거 + empirical validation |
| `docs/analysis/description-optimizer-mcp-zero-validation-20260330.md` | 최신 MCP-Zero 검증 보고서 |
| `docs/analysis/description-optimizer-root-cause-analysis.md` | historical regression 분석 |
