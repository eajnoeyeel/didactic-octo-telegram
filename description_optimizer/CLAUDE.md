# CLAUDE.md — Description Optimizer

> **이 파일은 규칙(conventions, constraints)과 참조 포인터만 둔다.** 상세 컨텍스트는 각 문서에 분리.
> 매 세션마다 전체 로드되므로 prompt bloat 방지를 위해 간결하게 유지할 것.
> 최종 업데이트: 2026-03-28

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

## 상세 컨텍스트 참조

| 파일 | 내용 |
|------|------|
| `docs/research-analysis.md` | 학술적 근거 분석, 논문 비교, 검증 설계 |
| `docs/evaluation-design.md` | 평가 전략 상세 (A/B Test, Quality Gate, Semantic Preservation) |
| 루트 `CLAUDE.md` | 프로젝트 전체 규칙 (상위 참조) |
| 루트 `docs/design/metrics-rubric.md` | GEO Score 6차원 정의 (SOT) |
| 루트 `docs/research/description-quality-scoring.md` | GEO Score 리서치 요약 |

---

## Architecture

```
Provider → Register MCP Server/Tools
    ↓
Description Optimizer Pipeline
    ↓ Phase 1: Analyze           ↓ Phase 2: Optimize
    GEO Score Diagnosis          LLM Rewriter
    (6-dimension scoring)        (dimension-aware prompt)
    ↓                            ↓
    Quality Report               optimized_description
                                 search_description (embedding용)
    ↓
    Quality Gate (no degradation check)
    ↓
    Store: original + optimized + search descriptions
```

### ABC Pattern

- `DescriptionAnalyzer` ABC — GEO Score 분석 (Heuristic / LLM-as-Judge)
- `DescriptionOptimizer` ABC — 재작성 (LLM / Rule-based)
- `QualityGate` — 최적화 전후 품질 비교, 의미 보존 검증

---

## Key Constraints

- 루트 `CLAUDE.md`의 모든 제약 조건을 상속 (async only, loguru, pytest-asyncio 등)
- **원본 description은 절대 삭제하지 않음** — 항상 보존
- **Semantic Preservation**: cosine similarity >= 0.85 유지
- **Quality Gate**: 최적화 후 GEO Score >= 최적화 전 GEO Score
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
```

---

## 코딩 컨벤션

루트 `CLAUDE.md` 및 `.claude/rules/coding-standards.md` 참조. 추가 규칙:

- 최적화 결과 모델: `OptimizedDescription(BaseModel)` — original, optimized, search, geo_score_before, geo_score_after
- Prompt 템플릿: `src/description_optimizer/prompts/` 하위에 분리 저장
- 모든 LLM 호출은 `AsyncOpenAI` 사용
