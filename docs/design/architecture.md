# Architecture — 결정 사항, 기술 스택, 제약 조건

> 최종 업데이트: 2026-03-22
> 다이어그램: `./architecture-diagrams.md`

---

## 아키텍처 결정 사항 (DP0-DP9)

| DP | 결정 | 상태 | 근거 |
|----|------|------|------|
| **DP0** | 극한의 완성도. 추천+Analytics(극한) > Distribution(높음) > Spec(견고) > OAuth(동작) | 확정 | 채용 연계 프로젝트. CTO 평가 3축: 엔지니어링 판단력, 서버리스/비용 최적화, LLM 통제력 |
| **DP1** | MCP Tool(Bridge) + REST API 이중 노출 | 확정 | LLM → Bridge MCP (`find_best_tool` + `execute_tool`), Provider → REST. MetaMCP 활용 |
| **DP2** | 2-Layer (서버 → Tool) 추천 단위 | 확정 | 서버 수준 capability 판단 + Tool 수준 정밀 매칭 |
| **DP3** | Strategy Pattern — A/B/C 모두 구현 후 실험 결정 | 확정 | 우선순위: A(Sequential) → B(Parallel) → C(Taxonomy-gated) |
| **DP4** | 임베딩: BGE-M3 vs OpenAI text-embedding-3-small | E2 실험 | voyage-code-2 사용 금지 (코드 특화, MCP description은 자연어) |
| **DP5** | Reranker: Cohere Rerank 3 + low-confidence LLM fallback | 방향 확정 | Cohere SOTA, free 1000 req/month. Confidence proxy: rank1-rank2 gap |
| **DP6** | Confidence 분기: gap 기반 (threshold 0.15) | 확정 | calibration 모델 없이 직관적, 구현 단순 |
| **DP7** | 데이터: Smithery 크롤링 + 직접 MCP 연결 하이브리드 | 확정 | 50~100 서버 큐레이션, GT: 수동 seed + LLM synthetic |
| **DP8** | 배포: 로컬 FastAPI → Lambda + API Gateway | 확정 | 개발: Docker Qdrant (`localhost:6333`), 배포: Qdrant Cloud free tier (1GB ~ 40K tools). Bedrock KB $700/월 거부 |
| **DP9** | 평가: 커스텀 하네스 + 11개 지표 | 확정 | Evaluator ABC 플러그인. Position bias 통제: Top-K 랜덤 셔플 |

---

## 기술 스택

| 레이어 | 선택 | 이유 |
|--------|------|------|
| 언어 | Python 3.12 | type hints 필수 |
| 의존성 관리 | uv | |
| 웹 프레임워크 | FastAPI | 로컬 → Lambda 마이그레이션 예정 |
| Vector Store | Qdrant (개발: Docker 로컬, 배포: Cloud free tier) | 1GB 무료, real-time upsert, REST API. 개발 단계에서는 `docker run -p 6333:6333 qdrant/qdrant`로 로컬 실행. AsyncQdrantClient 인터페이스 동일하므로 URL+API key만 전환 |
| 임베딩 | BGE-M3 or OpenAI text-embedding-3-small | E2 실험으로 결정. voyage-code-2 사용 금지 |
| Reranker | Cohere Rerank 3 | SOTA, 무료 1000 req/month |
| LLM Tracing | Langfuse | LLM call + 비용 추적 |
| 실험 추적 | Weights & Biases | |
| 검증 | Pydantic v2 | |
| 테스트 | pytest + pytest-asyncio | |
| 린터 | ruff | |
| 배포 Logging | CloudWatch → aggregation | Provider Analytics 파이프라인 |

---

## 양면 플랫폼 구조

- **LLM 고객**: Bridge 구조. LLM은 우리 MCP만 연결. `find_best_tool(query)` → 추천, `execute_tool(tool_id, params)` → 실행
- **Provider 고객**: Tool 선택 빈도, 경쟁 분석, 개선 가이드 열람
- **Core Pipeline**: 양측 동일 파이프라인 사용. Provider 경로는 로그 기반 분석 추가

> **아키텍처 결정 근거**: LLM은 `find_best_tool`을 자발적으로 호출하지 않음 (이미 연결된 도구를 직접 사용). Bridge 패턴만이 LLM이 단일 진입점을 통해 전체 Provider 카탈로그를 활용하게 한다. 실존 솔루션(MetaMCP, Microsoft MCP Gateway 등) 모두 이 패턴 사용.

### Bridge/Router (DP1)

- LLM은 우리 MCP Server에만 연결, 2개 도구 노출:
  - `find_best_tool(query: str)` → ToolRecommendation (Core Pipeline 실행 → Top-1 or Top-3 + confidence)
  - `execute_tool(tool_id: str, params: dict)` → ToolResult (Provider MCP 프록시, MetaMCP 기반)
- 구현 전략: MetaMCP(metatool-ai/metamcp) base → 정적 라우터를 `find_best_tool()` 벡터 서치로 교체
- 기술 참조: `mcp` (PyPI v1.7.1+), `fastmcp`, MetaMCP, mcp-bridge

### Core Pipeline — 2-Stage Retrieval

- **Strategy A (Sequential)**: Server Index → filtered Tool Search
- **Strategy B (Parallel)**: Server Index + Tool Index 병렬 → RRF Score Fusion
- **Strategy C (Taxonomy-gated)**: Intent Classifier → Category Sub-Index (CTO 확인 후 구현, JSPLIT 근거)
- 두 경로 모두 동일 Reranker + Confidence Branching(gap > 0.15) 사용
- 모든 전략은 `PipelineStrategy` ABC 구현, 동일 평가 하네스로 비교

### 검색 전략 구현 우선순위

1. Sequential (A) — 직관적, 서버 분석 가능. 단점: Layer 1 누락 시 복구 불가
2. Parallel (B) — Layer 1 실패에 강건. 단점: 검색 범위 넓음, Latency 증가
3. Taxonomy-gated (C) — 검색 범위 축소, 정밀도 향상. 단점: 분류 오류 시 전체 실패

---

## Provider Side — 기능 목록

### 필수 4기능 (DP0 확정)

| 기능 | 깊이 | 설명 |
|------|------|------|
| **Distribution** | 높음 | MCP 서버 배포/설치 가이드, 버전 관리, 레지스트리 연동 |
| **Analytics** | 극한 | 선택 빈도, 쿼리 인텐트 분포, Confusion Matrix, 경쟁 분석 |
| **Spec Compliance** | 견고 | MCP 스펙 준수 여부 자동 검사, 개선 가이드 |
| **OAuth UI** | 동작 | Provider 인증, 대시보드 접근 제어 |

### Analytics 심화 기능

| 코드 | 기능 | 설명 |
|------|------|------|
| D-1 | Live Query Sandbox | 테스트 쿼리 → 실시간 선택 여부 + 경쟁 Tool 시각화 |
| D-2 | Description Diff & Impact Preview | description 수정 전 "선택률 변화 예측" 미리보기 |
| D-3 | Semantic Similarity Heatmap | Tool 간 의미적 거리 시각화 |
| D-4 | Guided Description Onboarding | 신규 등록 wizard: 단계별 가이드 + 실시간 점수 |
| D-5 | Confusion Matrix Visualization | 어떤 쿼리에서 어떤 경쟁 Tool에게 지는지 매트릭스 |
| PM-1 | Selection SEO Score | Specificity / Disambiguation / Coverage 3축 점수 |
| PM-4 | A/B Testing for Descriptions | variant A vs B synthetic 쿼리 대결 → 승자 자동 배포 |
| PM-3 | Feedback Loop Dashboard | 로그 집계 → description 개선 권고 → 효과 추적 |

---

## 통제 변인 설계 (실험 루브릭)

### 변인 1: Tool Pool (조작 변인)

| 하위 변인 | 값 범위 | 목적 |
|-----------|---------|------|
| Pool Size | 5 / 20 / 50 / 100 | 스케일 효과 측정 |
| Similarity Density | Low / Medium / High | 혼동 가능성 영향 측정 |
| Domain Distribution | Single / Mixed | 도메인 다양성 효과 |
| Distractor Ratio | 0% / 20% / 50% | 관련 없는 Tool 비율 영향 |

### 변인 2: Description 품질 (핵심 독립 변인)

| 품질 차원 | 설명 |
|-----------|------|
| **Specificity** | 구체적 use case vs 모호한 일반 설명 |
| **Disambiguation** | 유사 Tool과의 차이점 명시 여부 |
| **Parameter description** | 입력 파라미터 상세 설명 여부 |
| **Negative instructions** | "이 Tool은 X에 쓰면 안 됨" 명시 여부 |

### 변인 3: Query 특성 (조작 변인)

| 하위 변인 | 값 범위 |
|-----------|---------|
| Ambiguity | Low / Medium / High |
| Complexity | Simple / Multi-step |
| Domain match | In-domain / Cross-domain |
| Phrasing variation | Formal / Natural / Abbreviated |

### 변인 4: Model 특성 (외부 변인)

- 임베딩 모델 종류, Reranker 종류 → DP4/DP5 실험에서 별도 처리

---

## 논문 참고 목록

| 논문 | 기여 | 적용 |
|------|------|------|
| RAG-MCP (arxiv:2505.03275) | Tool 선택 43% vs 13% | Primary baseline |
| JSPLIT (arxiv:2510.14537) | Taxonomy-gated retrieval | DP3-C 전략 |
| ToolLLM (Qin et al., ICLR 2024) | 16,464 real APIs | Scale 참고 |
| ToolTweak (arxiv:2510.02554) | Description 수정 → 20%→81% lift | 핵심 테제 근거 |
| ToolScan (arxiv:2411.13547) | 7 error patterns | Confusion Rate |
| StableToolBench (Guo et al., ACL 2024) | 안정적 Tool 평가 | 평가 설계 |
| API-Bank (Li et al., EMNLP 2023) | 3축 평가 분해 | GT 설계 |
| Calibration/ECE (Naeini et al., AAAI 2015) | Confidence 신뢰도 | DP9 지표 |
| Quality Matters (arxiv:2409.16341) | Synthetic GT 리스크 | GT 생성 주의점 |
| MRR (TREC-8 QA, Voorhees 1999) | 순위 기반 정확도 | 확장 지표 |
