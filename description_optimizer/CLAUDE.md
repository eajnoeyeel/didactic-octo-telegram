# CLAUDE.md — Description Optimizer

> **이 파일은 규칙(conventions, constraints)과 참조 포인터만 둔다.** 상세 컨텍스트는 각 문서에 분리.
> 매 세션마다 전체 로드되므로 prompt bloat 방지를 위해 간결하게 유지할 것.
> 최종 업데이트: 2026-03-30

---

## 메타 규칙

- **CLAUDE.md에는 규칙(conventions, constraints)과 참조 포인터만 기록한다.**
- 상세 정보가 필요하면 해당 파일을 Read tool로 직접 읽는다.
- CLAUDE.md 수정 시 200줄 이하를 유지한다.

---

## 서브프로젝트 한줄 요약

Description Optimizer — Provider가 MCP 서버/도구를 등록할 때 원본 description을 retrieval-oriented text로 최적화하여 RAG 검색 품질을 높이는 기능.

**목표**: 최적화된 `retrieval_description` 사용 시 RAG 검색의 `Recall@K` / `MRR` 향상 (vs 원본 description)

**핵심 테제**: "Description 최적화 → 검색 선택률 향상" (Paper A/B/F로 검증됨)

---

## 현재 상태 (2026-03-30)

**Branch:** `feat/description-optimizer`

**핵심 변경사항 (2026-03-30):**
- canonical retrieval field를 `retrieval_description`으로 전환
- GEO 기반 skip 제거, GEO는 diagnostic-only로 강등
- Quality Gate의 active 기준을 retrieval text 보존/유사도/환각/오염 방지로 재정렬
- retrieval A/B 평가 스크립트가 `retrieval_description`을 우선 사용하고 `Recall@K`를 1차 지표로 기록
- `mcp_zero` 기반 오프라인 검증 완료: filtered GT 178 queries / 32 tools / 10 servers
- latest query-level result: `P@1 0.2753 → 0.3427`, `Recall@10 0.6517 → 0.6629`, `MRR 0.4136 → 0.4439`
- current bottleneck: GT tools 32개 중 optimizer `success`는 7개, 25개는 gate reject

**다음 단계:** gate reject 25건 유형화 → similarity threshold/contamination 기준 재조정 → long-tail rank regression 제어

---

## 상세 컨텍스트 참조

| 파일 | 내용 |
|------|------|
| `data/verification/mcp_zero_gt_filtered.jsonl` | MCP-Zero pool 교집합 GT (178 queries, 32 tools) |
| `data/verification/mcp_zero_gt_optimized_descriptions.jsonl` | MCP-Zero GT 도구 최적화 결과 (7 success, 25 rejected) |
| `data/verification/mcp_zero_retrieval_ab_report.json` | tool-average retrieval A/B 결과 |
| `data/verification/mcp_zero_query_level_eval.json` | **query-level primary evaluation** — `Recall@10`, `MRR`, `P@1`, bootstrap CI |
| `docs/analysis/description-optimizer-mcp-zero-validation-20260330.md` | 최신 MCP-Zero 검증 보고서 |
| `data/verification/retrieval_ab_report.json` | historical retrieval A/B 결과 (pre-refactor artifact) |
| `data/verification/gt_optimized_descriptions.jsonl` | historical GT 최적화 결과 (18 success, 18 rejected) |
| `docs/analysis/grounded-ab-comparison-report.md` | A/B 비교 보고서 + 연구 방향 |
| `docs/analysis/description-optimizer-root-cause-analysis.md` | historical regression 근본원인 분석 |
| `docs/progress/grounded-optimization-handoff.md` | 구현 완료 내역 (Task 1-10 커밋 + 상세) |
| `docs/superpowers/plans/2026-03-29-description-optimizer-grounded-optimization.md` | 구현 계획서 |
| `description_optimizer/docs/research-analysis.md` | 학술적 근거 분석 + 최신 empirical validation |
| `description_optimizer/docs/evaluation-design.md` | 평가 전략 상세 (A/B Test, Quality Gate, significance) |
| 루트 `CLAUDE.md` | 프로젝트 전체 규칙 (상위 참조) |
| 루트 `docs/design/metrics-rubric.md` | GEO Score 6차원 정의 (SOT) |

---

## Architecture

```
Provider → Register MCP Server/Tools
    ↓
Description Optimizer Pipeline
    ↓ Phase 1: Analyze           ↓ Phase 2: Optimize
    GEO diagnostic only          LLM Rewriter (grounded/query-aware)
    (optional quality report)    (schema + target-only retrieval text)
    ↓                            ↓
    Quality Report               optimized_description
                                 retrieval_description (embedding용 canonical text)
    ↓
    Quality Gate (Similarity + Hallucination + Info Preservation + Contamination)
    ↓
    Store: original + retrieval descriptions
```

### ABC Pattern

- `DescriptionAnalyzer` ABC — GEO Score 분석 (Heuristic / LLM-as-Judge)
- `DescriptionOptimizer` ABC — 재작성 (LLM / Rule-based), `optimize(report, context=None)`
- `QualityGate` — retrieval text 안전성 검증 (의미 유사도, 환각 탐지, 정보 보존, sibling contamination)

### Grounded Optimization (신규, 2026-03-29)

- `OptimizationContext` — input_schema + sibling_tools 전달
- `build_grounded_prompt()` — schema 기반 프롬프트 + anti-hallucination 규칙
- `pipeline.run_with_tool(MCPTool, sibling_tools)` — grounded 최적화 진입점
- `check_hallucinated_params()` — backtick 파라미터 vs schema 교차 검증
- `check_info_preservation()` — 숫자/통계 + 기술 용어 보존 검증

---

## Phase 2 개선 사항 (2026-03-29)

- **boundary→fluency 차원 교체**: GEO 연구에서 boundary 미지지 확인. fluency(문장 구조, 연결어, 다양성)로 교체.
- **RAGAS faithfulness 게이트**: `check_faithfulness(claims)` — 주장 추출→이진 검증 패턴
- **doc2query 쿼리 인식 프롬프트**: `build_query_aware_prompt(context, relevant_queries)` — 검색 의도 기반 최적화
- **P@1 A/B 평가**: `scripts/run_retrieval_ab_eval.py` — 원본 vs 최적화 인메모리 검색 비교
- **리서치 종합**: `description_optimizer/docs/research-phase2-synthesis.md`

## Retrieval 검증 결과

### Latest MCP-Zero Validation (2026-03-30)

- dataset: `mcp_zero` pool + filtered GT `178 queries / 32 tools / 10 servers`
- optimizer coverage: `7 success / 25 gate_rejected`
- query-level primary metrics:
  - `P@1`: `0.2753 → 0.3427` (`+0.0674`)
  - `Recall@10`: `0.6517 → 0.6629` (`+0.0112`)
  - `MRR`: `0.4136 → 0.4439` (`+0.0304`)
- 해석: top-1 / top-few retrieval은 개선됐지만, gate reject가 많아 전체 효과가 제한적이며 long-tail rank는 아직 불안정

### Historical Regression (2026-03-29)

- `optimized_description` 임베딩 기준 `P@1`이 하락했던 historical artifact
- 현재 canonical input은 `retrieval_description`
- 상세: `data/verification/retrieval_ab_report.json`, `docs/analysis/description-optimizer-root-cause-analysis.md`

## 미해결 과제 (우선순위순)

1. gate tuning 이후 `retrieval_description` artifact 재생성 및 재평가
2. gate reject 25건의 similarity threshold 민감도 분석
3. long-tail rank regression이 큰 쿼리(`exa`, `calculator`) 회귀 분석
4. query-aware prompt와 target-only disambiguation 추가 실험
5. GEO diagnostic 리포트와 retrieval metric 상관 재측정

---

## Key Constraints

- 루트 `CLAUDE.md`의 모든 제약 조건을 상속 (async only, loguru, pytest-asyncio 등)
- **원본 description은 절대 삭제하지 않음** — 항상 보존
- **Semantic Preservation**: cosine similarity >= 0.75 유지
- **Quality Gate**: retrieval-safe checks only. GEO 하락은 reject 사유가 아님.
- **비용 제약**: GPT-4o-mini 사용, tool당 ~$0.001
- **기존 파이프라인 호환**: `MCPTool.description`은 변경하지 않고 별도 필드 추가

---

## Commands

```bash
# Tests
uv run pytest tests/unit/test_description_optimizer/ -v
uv run pytest tests/ --cov=src -v

# Lint
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# A/B Comparison (grounded vs ungrounded GEO)
PYTHONPATH=src uv run python scripts/run_grounded_ab_comparison.py

# GT 도구 최적화 (grounded)
PYTHONPATH=src uv run python scripts/optimize_gt_tools.py

# Retrieval A/B 평가 (원본 vs retrieval_description embedding 검색)
PYTHONPATH=src uv run python scripts/run_retrieval_ab_eval.py \
    --tools data/raw/mcp_zero_servers.jsonl \
    --ground-truth data/verification/mcp_zero_gt_filtered.jsonl \
    --optimized data/verification/mcp_zero_gt_optimized_descriptions.jsonl \
    --top-k 10 \
    --output data/verification/mcp_zero_retrieval_ab_report.json
```

---

## 코딩 컨벤션

루트 `CLAUDE.md` 및 `.claude/rules/coding-standards.md` 참조. 추가 규칙:

- 최적화 결과 모델: `OptimizedDescription(BaseModel)` — original, optimized, retrieval, geo_score_before, geo_score_after
- Prompt 템플릿: `src/description_optimizer/optimizer/prompts.py` (grounded/ungrounded 분기)
- 모든 LLM 호출은 `AsyncOpenAI` 사용
