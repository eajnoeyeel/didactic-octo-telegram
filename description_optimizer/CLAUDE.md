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

Description Optimizer — Provider가 MCP 서버/도구를 등록할 때 description을 진단하고, LLM으로 자동 최적화하여 retrieval 정확도(P@1)를 높이는 기능. GEO Score는 진단 보조 지표로 사용.

**목표**: 최적화된 description 사용 시 Precision@1 +10%p 이상 향상 (vs 원본 description)

**핵심 테제**: "Description 최적화 → 검색 선택률 향상" (Paper A/B/F로 검증됨)

---

## 현재 상태 (2026-03-30)

**Branch:** `feat/description-optimizer` — Phase 2 구현 완료, GEO-P@1 불일치 근본원인 분석 완료

**핵심 발견 (2026-03-30):**
- P@1 A/B 결과: Original 0.5417 → Optimized 0.4722 (δP@1 = -0.069)
- 근본원인: (1) 평가/검색 경로가 `search_description`이 아닌 `optimized_description`을 사용, (2) GEO 휴리스틱이 retrieval에 불리한 패턴 보상, (3) disambiguation이 sibling 오염으로 작동
- 상세: `docs/analysis/description-optimizer-root-cause-analysis.md`

**다음 단계:** retrieval 경로를 `search_description` 기준으로 재정렬 → 3-way A/B 평가 (original vs optimized vs search) → GEO를 diagnostic metric으로 격하

---

## 상세 컨텍스트 참조

| 파일 | 내용 |
|------|------|
| `data/verification/retrieval_ab_report.json` | **P@1 A/B 평가 결과** — per-tool breakdown 포함 (새 세션 시작점) |
| `data/verification/gt_optimized_descriptions.jsonl` | GT 도구 최적화 결과 (18 success, 18 rejected) |
| `docs/analysis/grounded-ab-comparison-report.md` | A/B 비교 보고서 + 연구 방향 |
| `docs/analysis/description-optimizer-root-cause-analysis.md` | **근본원인 분석 SOT** (2026-03-30) — 평가/검색 경로 불일치, GEO 보상 왜곡, disambiguation 오염 |
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
    Quality Gate (4-gate: Similarity + Hallucination + Info Preservation + Faithfulness)
    GEO Score → diagnostic metric only (gate에서 제외)
    ↓
    Store: original + optimized + search descriptions
```

### ABC Pattern

- `DescriptionAnalyzer` ABC — GEO Score 분석 (Heuristic / LLM-as-Judge)
- `DescriptionOptimizer` ABC — 재작성 (LLM / Rule-based), `optimize(report, context=None)`
- `QualityGate` — 4-gate 시스템 (의미 유사도, 환각 탐지, 정보 보존, RAGAS faithfulness). GEO Score는 diagnostic metric으로만 사용.

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
- **근본원인**: (1) 평가가 search_description이 아닌 optimized_description을 임베딩, (2) GEO 휴리스틱이 길이 팽창/sibling 오염을 보상, (3) disambiguation이 분리가 아닌 오염으로 작동. 상세: `docs/analysis/description-optimizer-root-cause-analysis.md`
- 상세: `data/verification/retrieval_ab_report.json`

## 미해결 과제 (우선순위순)

1. ~~**P@1 end-to-end 검증**~~ — 완료. δP@1 = -0.069
2. ~~**GEO-P@1 불일치 근본원인 분석**~~ — 완료 (2026-03-30). `docs/analysis/description-optimizer-root-cause-analysis.md`
3. **[최우선] Retrieval 경로 재정렬** — `search_description`을 실제 임베딩/평가 경로에 연결
   - 평가: original vs optimized_description vs search_description 3-way A/B
   - retrieval 전용 텍스트(`search_description`)가 실제 P@1을 개선하는지 검증
4. **GEO를 diagnostic metric으로 전환** — hard gate에서 제외, 진단 보조로만 사용
5. **disambiguation 재설계** — sibling 이름 나열 → target-only qualifier 중심
6. **RAGAS faithfulness 파이프라인 통합**: 현재 gate만 구현됨, 최적화 루프에 통합 필요

---

## Key Constraints

- 루트 `CLAUDE.md`의 모든 제약 조건을 상속 (async only, loguru, pytest-asyncio 등)
- **원본 description은 절대 삭제하지 않음** — 항상 보존
- **Semantic Preservation**: cosine similarity >= 0.75 유지
- **Quality Gate**: 4-gate (의미 유사도 + 환각 탐지 + 정보 보존 + RAGAS faithfulness). GEO는 diagnostic metric (gate 아님).
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

# P@1 A/B 평가 (원본 vs 최적화 embedding 검색)
PYTHONPATH=src uv run python scripts/run_retrieval_ab_eval.py \
    --tools data/raw/servers.jsonl \
    --ground-truth data/ground_truth/seed_set.jsonl \
    --optimized data/verification/gt_optimized_descriptions.jsonl \
    --output data/verification/retrieval_ab_report.json
```

---

## 코딩 컨벤션

루트 `CLAUDE.md` 및 `.claude/rules/coding-standards.md` 참조. 추가 규칙:

- 최적화 결과 모델: `OptimizedDescription(BaseModel)` — original, optimized, search, geo_score_before, geo_score_after
- Prompt 템플릿: `src/description_optimizer/optimizer/prompts.py` (grounded/ungrounded 분기)
- 모든 LLM 호출은 `AsyncOpenAI` 사용
