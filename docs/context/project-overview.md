# 프로젝트 개요

## 목표

MCP Gateway + Analytics Platform — **양면 플랫폼**

- **LLM 고객**: Bridge 구조 — 우리 MCP만 연결하면 전체 Provider 카탈로그 자동 라우팅. `find_best_tool(query)` → 최적 Tool 추천, `execute_tool(tool_id, params)` → Provider MCP 프록시 실행.
- **Provider 고객**: 자기 Tool이 왜 선택 안 되는지를 보여주는 Analytics 대시보드 + GEO 점수 + 개선 가이드

## 핵심 아키텍처

**Bridge/Router**: LLM ↔ Our MCP Bridge ↔ Provider MCPs (MetaMCP 기반)
- 2-stage retrieval pipeline: **Embedding → Vector Search → Reranker → Confidence 분기**
- 3가지 검색 전략 (Sequential, Parallel, Taxonomy-gated)이 공통 `PipelineStrategy` 인터페이스 뒤에 구현됨
- 동일 평가 하네스로 비교 실험 후 최적 전략 결정
- 상세: `docs/design/architecture.md`

## North Star Metric

**Precision@1 >= 50%** (Pool 50, mixed domain)
- 스트레치: >= 65% (Pool 100, high similarity)
- Alert: < 30% → 전략/임베딩 재검토

## 핵심 테제 (Evidence Triangulation)

**"Description 품질이 높을수록 Tool 선택률이 높아진다"**
- Primary: A/B Selection Rate Lift > 30%, p < 0.05 (McNemar's test)
- Secondary: Spearman r > 0.6, p < 0.05 (quality ↔ selection rate)
- Supplementary: OLS Regression R² > 0.4 (하위 요소별 기여도)
- 3개 중 2개 이상 통과 → 테제 지지

## 타임라인

- **4/26 최종 제출** | CTO 멘토링: 매주 화요일 (첫 세션 3/25)
- Week 1 (3/20): Phase 0-4 — 기반 + 데이터 + Ground Truth
- Week 2 (3/27): Phase 5-8 — 평가 하네스 + Reranker + API + E1
- Week 3 (4/3): Phase 9-11 — Analytics + 실험 러너 + E2/E3
- Week 4 (4/10): E4 (테제 검증) + E5/E6
- Week 5 (4/17): 보고서 + Provider Analytics 데모

## 기술 스택

> 상세: `docs/design/architecture.md` §9
