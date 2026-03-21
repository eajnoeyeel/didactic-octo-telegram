# MCP Discovery Platform — Brainstorm & Architecture Decisions
> 최초 작성: 2026-03-16 (v1) | 아키텍처 결정 반영: 2026-03-17 (v2) | 통합 정리: 2026-03-19
> 이 문서는 브레인스토밍 아이디어와 아키텍처 결정 사항을 단일 문서로 통합한 것입니다.
> 평가 지표 상세: `docs/evaluation/metrics-rubric.md` | Ground Truth 설계: `docs/evaluation/ground-truth-design.md` | 실험 설계: `docs/evaluation/experiment-design.md`

---

## 아키텍처 결정 사항

### DP0 — 범위 및 방향
- **프로젝트 성격**: 인포뱅크 채용 연계 독립 프로젝트 (42Seoul). 평가자: 강진범 CTO (iLab). 제출 마감: 2026-04-26.
- **CTO 평가 3축**: 엔지니어링 판단력 (트레이드오프 설명 가능), 서버리스/비용 최적화 (Lambda), LLM 통제력 (코드 리뷰 때 설명 가능)
- **완성도 목표**: 극한의 완성도 — 4/26 제출까지 끌어올릴 수 있는 최대치
- **깊이 배분**: 추천 + Analytics (극한) > Distribution (높음) > Spec Compliance (견고) > OAuth UI (동작)
- **레퍼런스**: Smithery (https://smithery.ai) — MCP 오픈 마켓플레이스, 2,880개+ MCP 등록

### DP1 — 확정: 노출 방식
- **결정**: MCP Tool (`find_best_tool`) + REST API 이중 노출
- **이유**: LLM 고객은 MCP Tool로 프로토콜-네이티브 호출, Provider 대시보드는 REST로 직접 접근

### DP2 — 확정: 추천 단위
- **결정**: 2-Layer (서버 → Tool)
- **이유**: 서버 수준의 capability 판단 + Tool 수준의 정밀 매칭. Provider Analytics를 서버/Tool 양 단위로 제공 가능.

### DP3 — 확정: 검색 전략 (전략 자체가 결정)
- **결정**: Strategy Pattern 도입 — `PipelineStrategy` 인터페이스로 세 전략 모두 구현, 동일 평가 하네스로 비교 실험 후 결정
  - **A (Sequential 2-Layer)**: 서버 인덱스 → Tool 인덱스. 구현 단순, 직관적. 먼저 구현.
  - **B (Parallel Dual-Index)**: 서버/Tool 병렬 검색 → 통합 Reranker. Provider 분석에 유리.
  - **C (Taxonomy-gated)**: 인텐트 분류 → 카테고리 내 검색 (JSPLIT 방식). 논문 근거 있음.
- **우선순위**: A 먼저 → B → C 순서로 확장
- **현재 예상**: ~1,000 tools 규모에서 Hybrid가 Dense 대비 키워드 매칭 우위 예상

### DP4 — 검토 중: 임베딩 모델
- **유력 후보**:
  - **BGE-M3** (BAAI): Dense + Sparse + Multi-vector 단일 모델. 별도 BM25 불필요. 오픈소스.
  - **OpenAI text-embedding-3-small**: API 호출, 모델 로딩 없음. Lambda cold start 문제 없음. 비용 발생.
  - **Voyage AI voyage-3** (general-purpose): natural language에 적합. voyage-code-2는 **코드 특화 → MCP 설명(자연어)에는 부적합할 수 있음**.
  - **Jina AI v3**: 멀티링크, 장문 지원.
- **미결**: 실험으로 결정. voyage-code-2는 MCP metadata/description이 자연어 위주이므로 general-purpose 모델이 더 적합할 가능성 높음.

### DP5 — 방향 확정, 실험 필요: Reranker
- **결정**: Cross-Encoder 기본 + Confidence 낮을 때 LLM fallback
  - **Cross-Encoder**: Cohere Rerank 3 (SOTA, free 1000 req/month) 우선 검토
  - **Confidence proxy**: rank-1 - rank-2 점수 gap (별도 calibration 모델 없이 동적 분기)
  - **LLM fallback 조건**: gap이 임계값 이하일 때 (비슷비슷한 Top-2)
- **CTO 멘토링에서 확인 예정**: Cross-Encoder만으로 5주 프로젝트에서 충분한지

### DP6 — 확정: Confidence 분기 로직
- **결정**: 동적 분기 — gap 기반 Confidence proxy
  - gap 큼 (분명히 1위) → Top-1 반환
  - gap 작음 (비슷비슷) → Top-3 + disambiguation hint 반환
- **이유**: Temperature Scaling 등 calibration 모델 없이 직관적으로 설명 가능, 구현 단순

### DP7 — 방향 확정: 데이터 소스
- **결정**: Smithery 크롤링 + 직접 연결 하이브리드
- **Ground Truth 전략**: LLM synthetic 생성 + 50-100개 수동 seed set 검수
  - 처음 50~100개 수동 검수로 생성 품질 기준 확립
  - 이후 자동 생성 쿼리가 그 기준을 충족하는지 검증 단계 삽입
  - "Quality Matters" 논문 (arxiv:2409.16341) 리스크 참고
- **목표 규모**: 50~100개 MCP 서버 큐레이션으로 시작 (데이터 수집 최우선)

### DP8 — 확정: 배포 아키텍처
- **결정**: 로컬 FastAPI 먼저 → Lambda + API Gateway 마이그레이션
- **Vector Store**: Qdrant Cloud free tier
  - 1GB = ~40K tools 수용 가능 (Smithery 전체 커버)
  - 비용: $0 (free tier)
  - 스케일업: Qdrant managed plan (10만+ tools 마이그레이션 용이, upsert API 동일)
  - Bedrock Knowledge Bases는 최소 $700/월 → 거부
- **Logging**: Lambda → CloudWatch → aggregation → Provider 대시보드
- **Tracing**: Langfuse (LLM call tracing + cost tracking)
- **Experiment tracking**: Weights & Biases

### DP9 — 확정: 평가 방법론
- **결정**: 오프라인 벤치마크 + 커스텀 평가 하네스 직접 작성
- **지표 체계** (11개, `docs/evaluation/metrics-rubric.md` 참조):
  - **North Star**: Precision@1
  - **Input Metrics** (4): Server Recall@K, Tool Recall@10, Confusion Rate, Description Quality Score
  - **Health Metrics** (3): ECE, Latency p50/p95/p99, Server Classification Error Rate
  - **Evidence Triangulation** (3): A/B Selection Rate Lift (causal), Spearman r (correlational), Regression R² (explanatory)
  - **Secondary**: NDCG@5, MRR, Pass Rate
- **핵심 테제 검증**: Description Quality ↔ Selection Rate — evidence triangulation 3중 증거로 인과 관계 입증. 비타협.
- **하네스 설계**: `evaluate(strategy, test_queries, ground_truth) → metrics`. `Evaluator` 추상 클래스로 지표 플러그인 방식.
- **Position bias 통제**: 평가 시 Top-K 목록 매 쿼리마다 랜덤 섞기 → 위치 효과 평균화

---

## Provider Side — 전체 기능 목록

> 구현은 단계적으로 진행. 핵심 파이프라인 + Analytics 백엔드 우선, UI/추가 기능은 후속 계획에서 구현. (상세: 구현 계획 `docs/superpowers/plans/2026-03-18-mcp-discovery-platform.md` 참조)

### 필수 4기능 (DP0 확정)
| 기능 | 깊이 | 설명 |
|------|------|------|
| **Distribution** | 높음 | MCP 서버 배포/설치 가이드, 버전 관리, 레지스트리 연동 |
| **Analytics** | 극한 | 선택 빈도, 쿼리 인텐트 분포, Confusion Matrix, 경쟁 분석 |
| **Spec Compliance** | 견고 | MCP 스펙 준수 여부 자동 검사, 개선 가이드 |
| **OAuth UI** | 동작 | Provider 인증, 대시보드 접근 제어 |

### Analytics 심화 기능
| 기능 | 출처 | 설명 |
|------|------|------|
| **Live Query Sandbox** | D-1 | 테스트 쿼리 입력 → 실시간 선택 여부 + 경쟁 Tool 나란히 시각화 |
| **Description Diff & Impact Preview** | D-2 | description 수정 전 "선택률 변화 예측" 즉시 미리보기 |
| **Semantic Similarity Heatmap** | D-3 | Tool 간 의미적 거리 시각화 ("X와 91% 유사 — 차별화 필요") |
| **Guided Description Onboarding** | D-4 | 신규 등록 wizard: 단계별 가이드 + 실시간 점수 |
| **Confusion Matrix Visualization** | D-5 | 어떤 쿼리에서 어떤 경쟁 Tool에게 지는지 매트릭스 표시 |
| **Selection SEO Score** | PM-1 | Specificity · Disambiguation · Semantic Coverage 3축 점수 |
| **A/B Testing for Descriptions** | PM-4 | variant A vs B synthetic 쿼리 대결 → 승자 자동 배포 |
| **Feedback Loop Dashboard** | PM-3 | 로그 집계 → description 개선 권고 → 개선 효과 추적 |

---

## 통제 변인 설계 (실험 루브릭)

### 변인 1: Tool Pool (조작 변인)
| 하위 변인 | 값 범위 | 목적 |
|-----------|---------|------|
| Pool Size | 5 / 20 / 50 / 100 | 스케일 효과 측정 |
| Similarity Density | Low / Medium / High | 혼동 가능성 영향 측정 |
| Domain Distribution | Single / Mixed | 도메인 다양성 효과 |
| Distractor Ratio | 0% / 20% / 50% | 관련 없는 Tool 비율 영향 |

### 변인 2: Description 품질 (핵심 독립 변인) ★
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

### 변인 4: Model 특성 (외부 변인, 낮은 우선순위)
임베딩 모델 종류, Reranker 종류 → DP4/DP5 실험에서 별도 처리

---

## 기술 스택 (현재 선택)

| 레이어 | 선택 | 이유 |
|--------|------|------|
| Vector Store | Qdrant Cloud free tier | 1GB 무료, real-time upsert, REST API, 마이그레이션 용이 |
| 임베딩 | BGE-M3 or OpenAI text-embedding-3-small | BGE-M3: Dense+Sparse 통합, OpenAI: Lambda cold start 없음 |
| Reranker | Cohere Rerank 3 | SOTA, 무료 1000 req/month |
| LLM Tracing | Langfuse | LLM call 추적 + 비용 추적 |
| Experiment | Weights & Biases | 실험 결과 추적 |
| 배포 | 로컬 FastAPI → Lambda + API Gateway | 단계적 마이그레이션 |
| Logging | CloudWatch → aggregation → 대시보드 | Provider Analytics 파이프라인 |

---

## 논문 참고 목록

| 논문 | 기여 | 적용 |
|------|------|------|
| RAG-MCP (arxiv:2505.03275) | Tool 선택 43% vs 13%, 50%+ token 절감 | 핵심 근거 |
| JSPLIT (arxiv:2510.14537) | Taxonomy-gated retrieval, latency 절감 | DP3-C 전략 |
| RAGAS (Es et al., EACL 2024) | RAG 평가 프레임워크 | 평가 하네스 참고 |
| ToolBench/ToolLLM (Qin et al., ICLR 2024) | Tool 사용 벤치마크 | 평가 데이터셋 설계 참고 |
| StableToolBench (Guo et al., ACL 2024) | 안정적 Tool 평가 | 평가 설계 참고 |
| API-Bank (Li et al., EMNLP 2023) | API 선택 벤치마크 | Ground truth 설계 참고 |
| Confusion Rate (arxiv:2601.16280, 2026) | Tool 혼동 측정 지표 | DP9 지표 |
| Calibration/ECE (Naeini et al., AAAI 2015) | Confidence 신뢰도 측정 | DP9 지표 |
| Quality Matters (arxiv:2409.16341) | Synthetic GT 품질 리스크 | Ground truth 생성 주의점 |
| MRR (TREC-8 QA, Voorhees 1999) | 순위 기반 정확도 지표 | Layer 1 서버 순위 평가 |
| ToolTweak (arxiv:2510.02554) | Description 조작 → 선택률 20%→81% | 핵심 테제 역방향 근거 |
| ToolScan/SpecTool (arxiv:2411.13547) | 7가지 Tool-use 오류 패턴 | Confusion Rate 설계 근거 |
| MetaTool (ICLR 2024) | Similar tool confusion 서브태스크 | Confusion Rate 설계 근거 |
| MCP-Bench (arxiv:2508.20453) | MCP 특화 벤치마크 | Tool Recall@K 근거 |
| τ-bench (arxiv:2406.12045) | Tool-Agent-User 상호작용 벤치마크 | Pass Rate 설계 참고 |
| ToolFlood (arxiv:2603.13950) | Semantic covering attack on tool selection | 보안/강건성 관점 |

---

## Appendix: 원본 브레인스토밍 아이디어 (2026-03-16)

> 아래는 초기 브레인스토밍에서 나온 15개 아이디어입니다. PM-1, D-1 등의 코드는 위 Provider 기능 목록에서 참조됩니다.

### Product Manager 관점
| 코드 | 아이디어 | 설명 |
|------|----------|------|
| PM-1 | Provider "Selection SEO Score" | Description clarity, semantic coverage, uniqueness 3축 점수 |
| PM-2 | Confidence-Based Multi-Tool Disambiguation | 확신 낮을 때 2~3개 후보 + 구조화된 질문 반환 |
| PM-3 | 양면 피드백 루프 대시보드 | LLM tool call 로그 → Provider description 개선 → 더 나은 추천 |
| PM-4 | A/B Testing for MCP Descriptions | Description variant 비교 → 승자 자동 배포 |
| PM-5 | Federated Index | 다중 레지스트리(Smithery + 공식 + private) 통합 검색 |

### Product Designer 관점
| 코드 | 아이디어 | 설명 |
|------|----------|------|
| D-1 | Live Query Sandbox | Provider가 테스트 쿼리 입력 → 실시간 선택 여부 시각화 |
| D-2 | Description Diff & Impact Preview | Description 수정 전 선택률 변화 예측 미리보기 |
| D-3 | Semantic Similarity Heatmap | Tool 간 의미적 거리 시각화 |
| D-4 | Guided Description Onboarding | 신규 등록 wizard: 단계별 가이드 + 실시간 점수 |
| D-5 | Confusion Matrix Visualization | 어떤 쿼리에서 어떤 경쟁 Tool에게 지는지 매트릭스 |

### Software Engineer 관점
| 코드 | 아이디어 | 설명 |
|------|----------|------|
| E-1 | `find_best_tool` as MCP Tool | 추천 시스템 자체를 MCP Tool로 노출 (프로토콜-네이티브) |
| E-2 | Hybrid BM25 + Dense + RRF | Sparse × Dense → RRF 결합 |
| E-3 | Synthetic Ground Truth Generator | LLM으로 Tool description에서 쿼리 자동 생성 |
| E-4 | Incremental Embedding Index | Description 업데이트 → webhook → 해당 Tool만 재임베딩 |
| E-5 | Cross-Encoder with Explainable Score | Reranker가 "왜 이 Tool인가" 설명도 반환 |
