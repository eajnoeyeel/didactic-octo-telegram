# 후순위 기능 + Phase 13 (Gated)

> Core pipeline 안정화 후 구현. CTO 멘토링(3/25) 확인 후 진행.

---

## Deferred Features (Out of Scope for This Plan)

These features are confirmed requirements but deferred to a follow-up plan after the core pipeline is stable:

| Feature | Rationale for deferral |
|---------|------------------------|
| **Distribution** (MCP server registration, install page) | Requires UI/frontend layer. Implement after backend analytics API is stable. |
| **Spec Compliance** (MCP protocol validation, quality gate) | Needs MCP spec parsing. Implement after data collection pipeline is built. |
| **OAuth UI** (auth modal for credentialed servers) | Requires frontend + auth flow. Lowest priority per DP0 depth allocation. |
| **Live Query Sandbox** (D-1, real-time "does my tool get selected?") | Depends on working search endpoint (Phase 8). Build as provider dashboard feature after Phase 9. |
| **Description Diff & Impact Preview** (D-2) | Requires A/B test infra (Phase 9) + UI. Post-core. |
| **Guided Description Onboarding** (D-4) | Requires SEO scorer (Phase 9) + UI wizard. Post-core. |
| **Feedback Loop Dashboard** (PM-3) | Requires aggregator (Phase 9) + UI. Post-core. |
| **Strategy C: Taxonomy-gated** | Pending CTO mentoring confirmation (2026-03-25). `taxonomy_gated.py` stub file is in the structure map; implementation task added as Phase 13 (gated). |
| **MCP Tool Server** (`find_best_tool` as MCP protocol Tool) | DP1 confirmed dual-exposure (REST + MCP). REST implemented in Phase 8. MCP Tool server is Phase 13 (after REST is stable). |

All features above WILL be implemented. This plan produces the core pipeline + Provider Analytics backend. UI and additional features ship in the next plan iteration.

---

## Phase 13: Gated Features (Post-Core, After CTO Mentoring 2026-03-25)

> **Gate**: Do NOT start this phase until (a) Phases 0–12 are passing, AND (b) CTO mentoring on 2026-03-25 has confirmed Strategy C viability and MCP Tool server design.

### Task 13.1: Strategy C — Taxonomy-gated Search (stub)

**Files:**
- Create: `src/pipeline/taxonomy_gated.py`

```python
# TODO: Implement after CTO confirmation on 2026-03-25.
# Strategy C: Classify query intent → category, then search within category (JSPLIT method).
# Reference: JSPLIT paper.
# Gate: Confirm this adds value at ~1,000 tools scale before building.

from src.pipeline.strategy import PipelineStrategy
from src.models import FindBestToolRequest, FindBestToolResponse

class TaxonomyGatedStrategy(PipelineStrategy):
    name = "taxonomy_gated"

    async def execute(self, request: FindBestToolRequest) -> FindBestToolResponse:
        raise NotImplementedError("Strategy C pending CTO confirmation (2026-03-25)")
```

### Task 13.2: MCP Tool Server (DP1 second exposure)

**Files:**
- Create: `src/api/mcp_server.py`

**Goal**: Expose `find_best_tool` as an actual MCP Tool so LLMs can call it via the MCP protocol natively (not just REST). This is the "protocol-native" DP1 decision.

```python
# TODO: Implement using mcp Python SDK (pip install mcp).
# Expose find_best_tool(query: str, top_k: int = 3) as an MCP Tool.
# Wire to the same SequentialStrategy used by the REST endpoint.
# Reference: RAG-MCP paper (arxiv:2505.03275) — same approach.

# Minimal structure:
# from mcp.server import Server
# from mcp.server.stdio import stdio_server
# server = Server("mcp-discovery")
# @server.tool("find_best_tool")
# async def find_best_tool(query: str, top_k: int = 3) -> dict: ...
```

### Task 13.3: A/B Test with Real Qdrant Payload Swap

**Files:**
- Modify: `src/analytics/ab_test.py`

Replace the placeholder `ABTestRunner` with the full implementation:
1. Upsert variant B description to Qdrant (`store.upsert_tools([modified_tool], [re_embedded_vector], collection)`)
2. Run evaluation arm B against the live index
3. Upsert original description back (restore)
4. Return delta

---

## Design Discussion Log (2026-03-19)

> 구현 전 논의 사항. 이 결정들이 왜 내려졌는지 추적하기 위해 기록.

### Sequential 2-Layer 구현 버그 및 두 전략 비교 실험

**논의 내용**: Sequential 전략의 현재 구현(`sequential.py`)은 서버 인덱스를 거치지 않고 툴 인덱스를 바로 검색한다. 진짜 2-Layer라면:

```
True Sequential 2-Layer:
  1. 서버 인덱스 검색 → Top-3 서버
  2. 각 서버 내 툴 인덱스 필터링 검색 (server_id_filter)
  3. 후보 합산 → Reranker
```

**발견된 트레이드오프**:
- Sequential의 리스크: Layer 1에서 서버 분류 오류 → 정답 툴이 후보에서 완전히 제외됨
- Parallel(B)은 이 리스크 없음: 서버/툴 동시 검색 후 RRF 합산

**결정**: 두 방식 모두 올바르게 구현 후 동일 Ground Truth로 비교 실험. `sequential.py`를 올바른 2-Layer 구조로 수정 필요 (현재 플랜의 코드는 Layer 1이 빠진 상태). 서버 분류 오류율을 별도 지표로 측정.

**참고 파일**: `mentoring/open-questions.md` — OQ-2, OQ-4

### SEO 점수 방식 미결

정규식 휴리스틱 방식의 한계 확인. 논문 리서치 후 LLM-based 방식과 비교 실험 예정. 핵심 테제(Spearman 상관계수)의 유효성이 SEO 점수 품질에 달려 있음. `mentoring/open-questions.md` — OQ-1 참고.

### Provider 실증용 자체 MCP 서버 필요

Smithery 데이터만으로는 A/B 테스트 / 피드백 루프 데모 불가 (description 수정 권한 없음). 최소 3개 자체 MCP 서버 구축 예정. `mentoring/open-questions.md` — OQ-3 참고.

---

## Open Questions (Resolve Before Implementation)

| # | Question | Action |
|---|----------|--------|
| 1 | BGE-M3 vs OpenAI embedder? | Run Phase 2 with both, compare Recall@10. Decide before Phase 3. |
| 2 | voyage-code-2? | **Do not use** — MCP descriptions are natural language, not code. |
| 3 | Taxonomy-gated (Strategy C) worth implementing at 1K tools scale? | Ask CTO mentoring 2026-03-25. Build A+B first. |
| 4 | Ground truth seed set size? | Ask CTO mentoring. Start with 50 manually verified. |
| 5 | Cross-Encoder alone sufficient for 5-week project? | Ask CTO mentoring. Start with Cohere Rerank 3 only. |

---

## CTO Mentoring Alignment (2026-03-25)

See `mentoring/cto-questions.md` for 7 questions. Key direction confirmations needed:
1. Strategy Pattern + all 3 strategies → compare experiment (confirm scale viability of C)
2. Cross-Encoder + LLM fallback → confirm for 5-week timeline
3. Ground truth approach → confirm 50 manual seed set minimum
4. 6 evaluation metrics → confirm completeness
5. Gap-based confidence proxy → confirm simplicity is acceptable

---

## Execution Notes

- Start from Phase 0 and execute sequentially within each phase.
- Each phase is independently committable and testable.
- Phases 0–7 = Core Pipeline (Sub-plan A). Phases 8–11 = Provider + Analytics (Sub-plan D).
- If running with subagents: one subagent per phase, two-stage review after each.
- All API keys in `.env` (copy `.env.example`). Never commit `.env`.
