# 브레인스토밍 아카이브

> 이 파일은 기획 초기 브레인스토밍 기록을 보존하는 아카이브입니다.
> DP0-DP9 아키텍처 결정, Provider 기능 목록, 통제 변인 설계는 → `docs/design/architecture.md`로 이동되었습니다.

---

# v1: Product Idea Brainstorm (2026-03-16)

> 원본: `docs/discovery/brainstorm-ideas-new.md`

---

## 프로덕트 기회 요약

| 항목 | 내용 |
|------|------|
| 제품 | MCP Discovery & Optimization Platform |
| 타겟 세그먼트 A | LLM/Agent 개발자 — 수천 개 MCP 중 정확한 Tool을 선택해야 하는 사람 |
| 타겟 세그먼트 B | MCP Provider — 자기 서버가 더 많이 선택되길 원하는 개발자/팀 |
| 핵심 기회 | RAG-MCP 논문 증명(13% → 43% 정확도, 50%+ 토큰 절감) × Smithery 공백 |
| 레퍼런스 | Smithery (2,000+ MCP), 공식 MCP Registry (2025.09 출시), RAG-MCP 논문 (arxiv:2505.03275) |

---

## Perspective 1: Product Manager — 5 아이디어

### PM-1. Provider "Selection SEO Score"
MCP Provider에게 "내 Tool이 왜 선택 안 되는지"를 정량적으로 보여주는 점수 시스템.
- Description clarity score, semantic coverage, uniqueness vs. competitors 3축
- BM: Provider가 점수 개선을 위해 프리미엄 분석 구독

### PM-2. Confidence-Based Multi-Tool Disambiguation
단순 Top-1 반환 대신, 확신 낮을 때 LLM에게 "이 2~3개 중 어떤 의도냐" 구조화된 질문을 반환.

### PM-3. 양면 피드백 루프 대시보드
LLM의 실제 tool call 로그 → Provider의 description 개선 → 더 나은 추천 → 더 많은 call

### PM-4. A/B Testing for MCP Descriptions
Provider가 description variant 2개를 등록 → synthetic query set으로 선택률 비교 → 승자 자동 배포.

### PM-5. Federated Index (다중 레지스트리 통합)
Smithery + 공식 MCP Registry + 내부 private registry를 단일 쿼리로 검색.

---

## Perspective 2: Product Designer — 5 아이디어

### D-1. Live Query Sandbox (Provider용)
Provider가 테스트 쿼리를 입력 → 실시간으로 "내 Tool이 선택되는가, 왜 안 되는가"를 시각화.

### D-2. Description Diff & Impact Preview
Provider가 description을 수정할 때 → "이 변경으로 선택률이 얼마나 바뀌는가" 즉시 미리보기.

### D-3. Semantic Similarity Heatmap
내 Tool과 다른 Tool들 간의 의미적 거리를 시각화.

### D-4. Guided Description Onboarding
신규 MCP 등록 시 "좋은 description이란 무엇인가"를 단계별로 안내.

### D-5. Confusion Matrix Visualization
어떤 쿼리에서 내 Tool 대신 다른 Tool이 선택되는지 매트릭스로 표시.

---

## Perspective 3: Software Engineer — 5 아이디어

### E-1. `find_best_tool` as MCP Tool (Self-referential Protocol-native)
추천 시스템 자체를 MCP Tool로 노출 — LLM이 자연스럽게 호출.

### E-2. Hybrid Search: BM25 + Dense + RRF
Sparse (BM25) × Dense (bi-encoder) → Reciprocal Rank Fusion으로 결합.

### E-3. Synthetic Ground Truth Generator
LLM으로 각 Tool description에서 "이 Tool을 쓸 법한 쿼리"를 자동 생성.

### E-4. Incremental Embedding Index (Webhook-triggered)
Provider가 description 업데이트 → webhook → 해당 Tool만 재임베딩 → 인덱스 업데이트.

### E-5. Cross-Encoder with Explainable Score
Reranker가 점수만 반환하는 게 아니라 "왜 이 Tool인가" 설명을 같이 반환.

---

## Top 5 우선순위

| 순위 | 아이디어 | 출처 | 핵심 가정 |
|------|----------|------|-----------|
| #1 | `find_best_tool` as MCP Tool | E-1 | LLM이 MCP Tool로 노출된 추천 시스템을 자발적으로 호출 |
| #2 | Provider Analytics + Confusion Analysis | PM-3 + D-5 | Provider가 선택률 데이터를 보면 description을 개선 |
| #3 | Hybrid BM25 + Dense Search with RRF | E-2 | MCP 쿼리는 의미적/키워드 쿼리 혼재 |
| #4 | Synthetic Ground Truth Generator | E-3 | LLM 생성 synthetic 쿼리가 실제와 유사 |
| #5 | Provider Description SEO Score + A/B | PM-1 + PM-4 | Provider가 점수 개선에 동기부여 |

---
---

# v2: Brainstorm + 아키텍처 결정 (2026-03-17)

> 원본: `docs/discovery/brainstorm-ideas-v2.md`
> v1에 CTO 멘토링 학습을 반영한 버전

## 변경 요약 (v1 → v2)

| 항목 | v1 | v2 |
|------|----|----|
| 아키텍처 결정 | 미결 (DP1~DP9) | DP1·2·6·8·9 확정, DP3 전략 확정, DP4·5 방향 확정 |
| Provider 기능 | Top 5 아이디어 수준 | 전체 기능 목록 확정 (D-1~D-5, PM-1, PM-3, PM-4 통합) |
| 기술 스택 | 미정 | Qdrant Cloud / BGE-M3 / Cohere Rerank 3 / Langfuse / W&B |
| 평가 체계 | 개념 수준 | 베이스라인 6개 지표 + 통제 변인 설계 확정 |
| 임베딩 모델 | voyage-code-2 언급 | voyage-code-2 부적합 판단 (코드 특화 → MCP 설명은 자연어) |

> 아키텍처 결정(DP0-DP9), Provider 기능 목록, 통제 변인 설계, 기술 스택, 논문 참고 목록은
> **`docs/design/architecture.md`**로 이동되었습니다.
