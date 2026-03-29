# CLAUDE.md — Description Optimizer

> **이 파일은 규칙(conventions, constraints)과 참조 포인터만 둔다.** 상세 컨텍스트는 각 문서에 분리.
> 매 세션마다 전체 로드되므로 prompt bloat 방지를 위해 간결하게 유지할 것.
> 최종 업데이트: 2026-03-29

---

## 메타 규칙

- **CLAUDE.md에는 규칙(conventions, constraints)과 참조 포인터만 기록한다.**
- 상세 정보가 필요하면 해당 파일을 Read tool로 직접 읽는다.
- CLAUDE.md 수정 시 200줄 이하를 유지한다.

---

## 서브프로젝트 한줄 요약

Description Optimizer — Provider가 MCP 서버/도구를 등록할 때 description을 GEO Score 기반으로 진단하고, LLM으로 자동 최적화하여 검색 선택률을 높이는 기능.

**목표**: 최적화된 description 사용 시 Precision@1 +10%p 이상 향상 (vs 원본 description)

**핵심 테제**: "Description 최적화 → 검색 선택률 향상" (Paper A/B/F로 검증됨)

---

## 현재 상태 (2026-03-29)

**Branch:** `feat/description-optimizer` — Phase 2 구현 완료, 396 tests

**Phase 2 변경사항 (2026-03-29):**
- boundary 차원 완전 제거 → fluency 차원으로 교체 (GEO 연구 미지지, 95% 환각 원인)
- RAGAS faithfulness 게이트 추가 (주장별 이진 검증)
- doc2query 쿼리 인식 최적화 프롬프트 (`build_query_aware_prompt`)
- P@1 A/B 검색 평가 스크립트 (`scripts/run_retrieval_ab_eval.py`)

**다음 단계:** ~~A/B 비교 재실행~~ (완료) → ~~P@1 end-to-end 평가~~ (완료, δP@1=-0.069) → GEO-P@1 불일치 근본원인 분석

---

## 상세 컨텍스트 참조

| 파일 | 내용 |
|------|------|
| `docs/analysis/grounded-ab-comparison-report.md` | **A/B 비교 보고서 + 연구 방향** (새 세션 시작점) |
| `docs/analysis/description-optimizer-root-cause-analysis.md` | 근본원인 분석 (Goodhart's Law, 환각 사례) |
| `docs/progress/grounded-optimization-handoff.md` | 구현 완료 내역 (Task 1-10 커밋 + 상세) |
| `docs/superpowers/plans/2026-03-29-description-optimizer-grounded-optimization.md` | 구현 계획서 |
| `docs/research-analysis.md` | 학술적 근거 분석, 논문 비교, 검증 설계 |
| `docs/evaluation-design.md` | 평가 전략 상세 (A/B Test, Quality Gate, Semantic Preservation) |
| 루트 `CLAUDE.md` | 프로젝트 전체 규칙 (상위 참조) |
| 루트 `docs/design/metrics-rubric.md` | GEO Score 6차원 정의 (SOT) |

---

## Architecture

```
Provider → Register MCP Server/Tools
    ↓
Description Optimizer Pipeline
    ↓ Phase 1: Analyze           ↓ Phase 2: Optimize
    GEO Score Diagnosis          LLM Rewriter (grounded/ungrounded)
    (6-dimension heuristic)      (input_schema + sibling tools)
    ↓                            ↓
    Quality Report               optimized_description
                                 search_description (embedding용)
    ↓
    Quality Gate (5-gate: GEO + Similarity + Hallucination + Info Preservation + Faithfulness)
    ↓
    Store: original + optimized + search descriptions
```

### ABC Pattern

- `DescriptionAnalyzer` ABC — GEO Score 분석 (Heuristic / LLM-as-Judge)
- `DescriptionOptimizer` ABC — 재작성 (LLM / Rule-based), `optimize(report, context=None)`
- `QualityGate` — 5-gate 시스템 (GEO 비회귀, 의미 유사도, 환각 탐지, 정보 보존, RAGAS faithfulness)

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

## P@1 A/B 평가 결과 (2026-03-29)

- **Original P@1: 0.5417, Optimized P@1: 0.4722, Delta: -0.0694**
- 36 tools (18 optimized, 18 gate-rejected → 원본 유지)
- Per-tool: 1 improved, 3 degraded, 32 same
- **결론**: GEO 점수 개선이 실제 검색 성능과 불일치 — GEO 프록시 메트릭 신뢰도 재검토 필요
- 상세: `data/verification/retrieval_ab_report.json`

## 미해결 과제

1. ~~**P@1 end-to-end 검증**~~ — 완료. δP@1 = -0.069 (검색 성능 저하 확인)
2. **GEO-P@1 불일치 근본원인 분석**: 최적화된 description이 GEO↑ 하지만 P@1↓인 원인 규명
3. **RAGAS faithfulness 파이프라인 통합**: 현재 gate만 구현됨, 최적화 루프에 check_faithfulness 통합 필요
4. **disambiguation 개선**: regex 대조 문구 → sibling tools 간 임베딩 거리 기반 측정
5. **fluency 측정 고도화**: 현재 휴리스틱(문장 수, 연결어). 향후 LLM-as-Judge(별도 모델) 검토

---

## Key Constraints

- 루트 `CLAUDE.md`의 모든 제약 조건을 상속 (async only, loguru, pytest-asyncio 등)
- **원본 description은 절대 삭제하지 않음** — 항상 보존
- **Semantic Preservation**: cosine similarity >= 0.75 유지
- **Quality Gate**: 5-gate (GEO 비회귀 + 의미 유사도 + 환각 탐지 + 정보 보존 + RAGAS faithfulness)
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

# A/B Comparison (grounded vs ungrounded)
PYTHONPATH=src uv run python scripts/run_grounded_ab_comparison.py
```

---

## 코딩 컨벤션

루트 `CLAUDE.md` 및 `.claude/rules/coding-standards.md` 참조. 추가 규칙:

- 최적화 결과 모델: `OptimizedDescription(BaseModel)` — original, optimized, search, geo_score_before, geo_score_after
- Prompt 템플릿: `src/description_optimizer/optimizer/prompts.py` (grounded/ungrounded 분기)
- 모든 LLM 호출은 `AsyncOpenAI` 사용
