# MCP Discovery — MLP Service Design

> **Version**: 0.2 (2026-04-04)
> **Status**: Draft — Pre-mortem 반영
> **Scope**: MLP (Minimum Lovable Product), 마감 4/6
> **Companion**: `mlp/docs/pre-mortem.md` — 상세 리스크 분석

---

## 1. Product Overview

### 한줄 요약

**MCP Discovery** — MCP 도구 검색 엔진 + Provider 검색 최적화 플랫폼.
LLM 클라이언트에게는 최적의 도구를 찾아주고, Provider에게는 "왜 내 도구가 선택되지 않는지"를 알려준다.

쉽게 말해, **"MCP 검색 엔진이 얹힌 Smithery + Provider용 검색 최적화 서비스"**.

### Core Thesis

> "Higher description quality → higher tool selection rate"

GEO Score로 측정 → 개선 가이드 제공 → selection rate 향상 검증.
- MLP: 오프라인 retrieval 성능 / 내부 selection simulation 검증
- Phase 2: 실제 트래픽 기반 online selection uplift 검증

### 양면 고객

| 고객 | 핵심 가치 | 인터페이스 |
|------|----------|-----------|
| **LLM Client** (개발자/에이전트) | 가변 풀에서 최적 도구를 1개로 좁혀준다 | Bridge MCP Server, REST Search API |
| **MCP Provider** (도구 제공자) | 내 도구가 왜 선택 안 되는지, 어떻게 개선하는지 알려준다 | Provider Dashboard (GEO Score, 진단 리포트) |

### 참조 서비스

| 서비스 | 참조 범위 |
|--------|----------|
| **Smithery** | MCP 레지스트리 (서버/도구 목록, 검색, 상세 페이지) |
| **MetaMCP** | MCP 프록시/라우터 (도구 실행 중계) |
| **ToolRank** | 도구 품질 점수 (정적 4D 점수 → 우리는 라이브 6D GEO Score) |

### 경쟁 포지션

현재 시장에서 **multi-stage retrieval + provider analytics를 결합한 제품은 없음**.
- ToolRank: 정적 점수만, retrieval 엔진 없음
- Smithery: 레지스트리 + 관리형 연결, 품질 분석 없음
- MetaMCP: 프록시/라우터, 검색/분석 없음
- 공식 MCP Registry: 메타데이터 저장소, 하위 aggregator용 (우리 같은 플랫폼이 소비)

차별화: Description Smells 논문이 입증한 인과관계(+11.6% uplift, p<0.001)를 **제품화**.

---

## 2. MLP Scope / Phase 2 Scope

### MLP (4/6 마감)

| 기능 | 범위 | 구현 방식 |
|------|------|----------|
| **Registry UI** | 서버/도구 목록, 상세 페이지, 검색 | Lovable + Supabase |
| **Semantic Search API** | 2-Stage Retrieval (Embedding → Rerank → Confidence) | Lambda + shared/ core 모듈 |
| **Bridge MCP Server** | `find_best_tool(query)` → SearchResult | Lambda + `awslabs.mcp-lambda-handler` |
| **REST Search API** | 동일 검색 기능을 REST로 노출 | Lambda + API Gateway |
| **Proxy (제한적)** | 사전 등록 hosted MCP 3-5개만 실행 지원 | Lambda thin pass-through |
| **Provider Dashboard** | GEO Score 6D 진단, 검색 시뮬레이션, 경쟁 비교 | Lovable + Supabase (사전 계산 데이터) |
| **Async Indexing** | 등록 → EventBridge → 임베딩 → Qdrant | EventBridge + Lambda |
| **Lexical Fallback** | 임베딩 미완료 도구도 검색 가능 | Supabase full-text search (tsvector) |
| **초기 데이터** | MCP-Zero Pool 292 서버 import | 사전 임베딩 + Supabase/Qdrant seed |

### MLP에서 하지 않는 것

| 기능 | 이유 | Phase |
|------|------|-------|
| Self-hosted MCP 프록시 | registration/health check/auth 복잡도 | Phase 2 |
| 실시간 실행 로그 기반 Analytics | 트래픽 없음 | Phase 2 |
| Provider description 직접 수정 UI | 진단 리포트 우선 | Phase 2 |
| A/B Testing for Descriptions | 시뮬레이션 검증 먼저 | Phase 2 |
| Popularity 기반 랭킹 | Matthew effect / cold-start 왜곡 / 핵심 테제 오염 방지 | 의도적 배제 |
| Online selection uplift 검증 | 실제 트래픽 필요 | Phase 2 |
| Parallel Strategy 프로덕션 적용 | 실험 트랙에서 검증 후 | Phase 2 (feature flag) |
| Toolset Projection | 전체 풀 검색이 MLP 기본 | Phase 2 |

### Composite Score 구조 (MLP scaffold)

```
final_score = relevance_score + quality_score + boost_score
```

| 컴포넌트 | MLP | Phase 2 |
|----------|-----|---------|
| `relevance_score` | Reranker score (활성) | 동일 |
| `quality_score` | 0.0 (scaffold) | GEO Score 기반 가중치 |
| `boost_score` | 0.0 (scaffold) | 유료 부스트 |
| `is_boosted` | 항상 False | True일 때 클라이언트에 투명성 라벨 표시 |

클라이언트는 `include_boosted=false` 파라미터로 부스트 결과 제외 가능 (Phase 2).

### Phase 2 확장 포인트: Toolset Projection

전체 카탈로그가 아니라 쿼리/세션/컨텍스트에 맞는 tool subset만 투영:
- 세션 내 이전 도구 사용 히스토리
- 클라이언트가 선언한 capability 범위
- 도메인/카테고리 컨텍스트
- Provider health status (timeout/5xx 제외)

MLP: 전체 풀 대상 검색. Phase 2: `PipelineStrategy.search(query, top_k, pool_filter)` 파라미터 추가.

---

## 3. Functional Requirements

### FR1. Tool Search (LLM Client)

- 자연어 쿼리 → top-K SearchResult 반환 (기본 top-1, 옵션 top-3)
- 각 결과에 `score_breakdown` (relevance / quality=0.0 / boost=0.0), `reason`, `input_schema` 포함
- Confidence branching: gap > 0.15이면 top-1 확정, 아니면 top-3 + confidence 표시
- Lexical fallback: 임베딩 미완료 도구도 tsvector 매칭으로 검색 가능
- **결과 캐싱**: 동일 쿼리 해시에 대해 TTL 5분 인메모리 캐시 (warm Lambda 인스턴스 내). 외부 API 호출 절감 + rate limit 보호
- **Degraded mode**: Qdrant 장애 시 Supabase full-text search로 전체 fallback (reranking 스킵, lexical 결과만 반환)

### FR2. Bridge MCP Server (LLM Client)

- Streamable HTTP transport (`awslabs.mcp-lambda-handler`)
- `find_best_tool(query)` → SearchResult
- `execute_tool(tool_id, params)` → 실행 결과 (hosted MCP 한정)
- Stateless (세션 관리 없음, Lambda request-response 모델)

### FR3. REST Search API (Consumer / Dashboard)

- `POST /api/search` → 동일 검색 로직, JSON 응답
- `POST /api/execute` → 도구 실행 (hosted MCP 한정)
- Bridge MCP와 동일한 내부 서비스 레이어 공유

### FR4. Tool Execution Proxy (제한적)

- 사전 등록 hosted MCP 서버 3-5개에 대해 `execute_tool` 동작
- thin pass-through: params 전달 → 결과 반환 → 실행 로그 저장
- 미등록 서버: 에러 + "이 서버는 아직 실행을 지원하지 않습니다"

### FR5. Server/Tool Registry (Provider)

- Provider가 MCP 서버 등록: URL, name, description, tools 목록
- 등록 즉시 Supabase에 메타데이터 저장 → lexical 검색 가능 (tsvector)
- EventBridge → Index Lambda → 임베딩 생성 → Qdrant upsert → semantic 검색 활성화
- 초기 데이터: MCP-Zero Pool 292 서버 사전 import
- **Description 검증 (anti-gaming)**:
  - 등록 시 description 길이 제한 (max 2,000자)
  - prompt injection 패턴 탐지: 숨겨진 지시문, 특수 토큰, 시스템 프롬프트 유사 패턴 필터링
  - 기존 도구와 코사인 유사도 > 0.95일 경우 중복 플래그
- **등록 rate limiting**: IP당 10 req/hour, 계정당 50 서버/day

### FR6. Registry UI (Lovable)

- 서버/도구 목록 브라우징 (카테고리, 태그 필터)
- 검색창: 자연어 쿼리 → Search API → 결과 표시
- 도구 상세: description, input_schema, GEO Score, 소속 서버

### FR7. Provider Dashboard (Lovable)

- **GEO Score 진단 리포트**: 6D 점수 (Clarity, Disambiguation, Parameter Coverage, Boundary, Stats, Precision) + 항목별 개선 제안
- **검색 시뮬레이션**: "이 쿼리를 했을 때 내 도구는 몇 위인가?" (오프라인)
- **경쟁 도구 비교**: 동일 카테고리 내 유사 도구와의 GEO Score 비교
- 사전 계산 데이터 기반 (실시간 트래픽 Analytics 아님)

### FR8. Provider Metadata 수정 범위

- **수정 가능** (GEO 최적화 대상): description, use-case examples, tags
- **수정 불가** (관측 사실): tool_name, input_schema, execution metrics
- MLP: 수정 UI 없음. 진단 리포트만 제공, Provider가 자체 서버에서 수정 후 재등록

---

## 4. Non-Functional Requirements & Constraints

### 4.1 비기능 요구사항

| 항목 | 요구 | 근거 |
|------|------|------|
| Search Latency | p95 < 3초 | Lambda warm ~300ms + Qdrant ~10ms + Cohere ~100ms. SnapStart + warming ping |
| Freshness | 등록 즉시 lexical 검색 가능, semantic 30초 이내 | Supabase tsvector 즉시 + EventBridge async indexing |
| Indexing Consistency | 실패 시 partial state 없음 | Idempotent upsert (uuid5) + index_status 필드 |
| Availability | Lambda SLA (99.95%) + degraded mode | Qdrant 장애 시 Supabase fallback |
| Cost | 월 $10 이하 | Free tier 최대 활용 (아래 비용표 참조) |
| **Security** | API 접근 제어 + 비용 보호 | API Key + throttle + WAF |
| **Observability** | 장애 시 5분 내 원인 파악 | X-Ray + 구조화 로깅 + 대시보드 |

### 4.2 보안 & 비용 보호

| 항목 | 설계 |
|------|------|
| **API Gateway Throttle** | Search: 100 req/s, Register: 10 req/s, Execute: 50 req/s (SAM 템플릿에 포함) |
| **API Key** | 공개 엔드포인트 없음. Usage Plan + API Key 필수 (Lovable은 프론트엔드 전용 키 사용) |
| **WAF** | AWS WAF rate-based rule: IP당 100 req/5min. 봇/DDoS 차단 |
| **Supabase Key 분리** | `anon` key만 Lovable 프론트엔드에 노출. `service_role` key는 Lambda 환경변수에만 |
| **Execute Proxy 검증** | `execute_tool` 호출 시 input_schema 기반 파라미터 validation. 미등록 서버 차단 |
| **Description Sanitization** | 등록 시 prompt injection 패턴 탐지, 길이 제한, 중복 유사도 검사 (FR5 참조) |

### 4.3 제약사항

| 제약 | 내용 |
|------|------|
| AWS 필수 | CTO 요구. Lambda + API Gateway + EventBridge |
| 비용 | Qdrant Cloud free (1GB), Cohere 유료, OpenAI 임베딩 최소 사용 |
| Vendor lock-in 회피 | ABC 패턴으로 구현체 교체 가능. 요구사항은 capability 기준 |
| Ranking 순수성 | Popularity/usage count를 ranking에 반영하지 않음 (MLP). Analytics 수집만 |
| 오프라인/온라인 분리 | MLP의 quality score 검증은 오프라인. 온라인 uplift는 Phase 2 |
| 기존 코드 재사용 | shared/ core 모듈은 실험 코드와 동일 |
| 프록시 실행 로그 | 수집하되 MLP에서는 Analytics 중심. ranking feedback에 사용하지 않음. 단, timeout/5xx는 Phase 2에서 quality gate penalty 가능 |
| **Anti-enshittification 원칙** | Sponsored 결과는 항상 라벨 표시 + 최소 relevance 게이트 충족 필수 + organic 순위 불간섭 (Phase 2 광고 도입 시 적용) |

### 4.3 비용 추정 (MLP 월간)

| 서비스 | Free Tier | 예상 사용량 | 비용 |
|--------|-----------|------------|------|
| Lambda | 1M req/mo, 400K GB-s | ~10K req | $0 |
| API Gateway | 1M req/mo | ~10K req | $0 |
| EventBridge | 커스텀 이벤트 $1/1M | ~1K events | $0 |
| CloudWatch | warming ping | 5분 간격 | $0 |
| Qdrant Cloud | 1GB free | ~25MB (2.5%) | $0 |
| Supabase | 500MB, 50K MAU | ~3K rows | $0 |
| Cohere Rerank | 유료 플랜 | 실험 + 프로덕션 | 유료 (기존) |
| OpenAI Embedding | 종량제 | 초기 batch ~1.4M tokens | ~$0.03 |
| Lovable | Starter | 개발 기간 | $20/mo |
| **Total** | | | **~$20/mo + Cohere** |

---

## 5. System Architecture

### 5.1 전체 구조

```
┌──────────────────────────────────────────────────────────────┐
│                      Lovable Frontend                        │
│  ┌───────────┐  ┌────────────┐  ┌──────────────────────────┐ │
│  │ Registry  │  │ Search UI  │  │ Provider Dashboard       │ │
│  │ (browse)  │  │ (query)    │  │ (GEO Score, 진단, 비교)  │ │
│  └─────┬─────┘  └─────┬──────┘  └───────────┬──────────────┘ │
└────────┼──────────────┼──────────────────────┼───────────────┘
         │              │                      │
         ▼              ▼                      ▼
  Supabase 직접     API Gateway            Supabase 직접
  (목록/필터/Auth)      │                  (GEO/분석 쿼리)
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
     ┌─────────┐  ┌──────────┐  ┌──────────┐
     │ Search  │  │ Execute  │  │ Register │
     │ Lambda  │  │ Lambda   │  │ Lambda   │
     └────┬────┘  └────┬─────┘  └────┬─────┘
          │             │             │
          ▼             │             ▼
   shared/ core         │        Supabase INSERT
   ┌────────────┐       │        + EventBridge 이벤트
   │ pipeline   │       │             │
   │ embedding  │       │             ▼
   │ retrieval  │       │        ┌──────────┐
   │ reranking  │       │        │  Index   │
   └──┬────┬────┘       │        │  Lambda  │
      │    │             │        └────┬─────┘
      ▼    ▼             ▼             │
  Qdrant  Cohere    Hosted MCP    OpenAI Embed
  Cloud   Rerank    Server(s)     + Qdrant Upsert
                                  + Supabase UPDATE
```

### 5.2 핵심 경로: Search Flow

```
Query "I need a tool to search GitHub repos"
    │
    ▼
Search Lambda
    ├── [1] Qdrant semantic search (top-10)       ← shared/retrieval
    ├── [2] Supabase lexical fallback              ← 미인덱싱 도구 보완
    │       (index_status != 'indexed' 인 것만,
    │        tsvector @@ plainto_tsquery)
    ▼
    Merge & deduplicate
    │
    ▼
    [3] Cohere Rerank (top-10 → top-3)             ← shared/reranking
    │
    ▼
    [4] Confidence branching (gap > 0.15)           ← shared/pipeline
    │
    ▼
    SearchResult(
      tool_id, score_breakdown, reason,
      input_schema, is_boosted=False
    )
```

### 5.3 Async Indexing Pipeline

```
Provider 등록
    │
    ▼
Register Lambda
    ├── Supabase INSERT (metadata, index_status='pending')
    │   → tsvector 즉시 생성 → lexical 검색 가능
    └── EventBridge PutEvents ("server.registered")
             │
             ▼
        Index Lambda (EventBridge 트리거)
             ├── OpenAI embed (tool descriptions)
             ├── Qdrant upsert (uuid5 idempotent)
             └── Supabase UPDATE (index_status='indexed')
                  │
                  실패 시 → index_status='failed'
                  → Lambda DLQ (SQS) → 재시도/알림
```

### 5.4 MCP + REST 이중 노출 (DP1)

```
API Gateway
├── /mcp              → Bridge MCP Server (Streamable HTTP)
│                       awslabs.mcp-lambda-handler
│                       find_best_tool / execute_tool
│
├── /api/search       → REST Search API (JSON)
├── /api/execute      → REST Execute API (JSON)
├── /api/servers      → Registry CRUD
└── /api/providers/*  → Provider Analytics

/mcp 와 /api/search 는 같은 내부 서비스 레이어를 공유.
Lovable Dashboard → /api/* (REST)
LLM Agent → /mcp (MCP protocol)
```

### 5.5 코드 구조 (Hybrid C)

```
shared/                ← src/에서 core 모듈 추출 (기존 검증 코드)
├── models.py          MCPTool, MCPServer, SearchResult, ScoreBreakdown
├── pipeline/          PipelineStrategy ABC, Sequential, Confidence
├── embedding/         Embedder ABC, OpenAIEmbedder
├── retrieval/         QdrantStore (AsyncQdrantClient)
├── reranking/         Reranker ABC, CohereReranker
└── analytics/         ← 기존 src/analytics/ 재사용
    ├── geo_score.py   GEO Score 6D (heuristic) — Provider Dashboard 핵심
    ├── confusion_matrix.py  도구 간 경쟁 분석
    ├── aggregator.py  로그 → 도구별 통계 (입력 소스 Supabase로 교체)
    └── logger.py      QueryLogEntry 모델 재사용 (저장소 Supabase로 변경)

# NOTE: description_optimizer/는 merge 후 revert됨 (성능 회귀, 2026-04-01).
# GEO Score는 src/analytics/geo_score.py를 canonical로 사용.
# LLM 기반 description 최적화 (개선 제안 생성)는 Phase 2에서 재설계.

lambdas/               ← 신규 Lambda handlers
├── search/            query → shared.pipeline.search() → response
├── register/          provider → Supabase + EventBridge
├── index/             EventBridge → shared.embedding + Qdrant upsert
├── execute/           tool_id → hosted MCP proxy
└── bridge/            MCP Streamable HTTP (awslabs.mcp-lambda-handler)

experiments/           ← 기존 src/evaluation, scripts (오프라인 유지)
├── evaluation/        harness, metrics
├── scripts/           run_e0.py, etc.
└── data/              ground truth, external datasets
```

### 5.6 Tech Stack

| Layer | Choice | 선택 근거 |
|-------|--------|----------|
| Compute | AWS Lambda + API Gateway | CTO 요구 |
| Async | EventBridge + Lambda | 유휴 비용 $0, push 방식 |
| Frontend | Lovable (+ v0 보조) | Supabase 네이티브 통합, 최고 MVP 속도 |
| Metadata DB | Supabase PostgreSQL | full-text search, Auth, Lovable 통합 |
| Vector DB | Qdrant Cloud free | 기존 통합, async 클라이언트, 97.5% 용량 여유 |
| Embedding | OpenAI text-embedding-3-small (1536d) | 최저 비용, 기존 통합. E2에서 대안 실험 |
| Reranker | Cohere Rerank 3.5 (유료) | 기존 통합, 높은 품질. E3에서 Jina v2 비교 |
| MCP Transport | Streamable HTTP (stateless) | Lambda 호환, awslabs 공식 라이브러리 |
| Auth | Supabase Auth | Lovable 네이티브, OAuth/JWT 내장 |
| Warming | CloudWatch Events (5분) | Cold start 방지 + Qdrant/Supabase keep-alive, $0 |
| Observability | X-Ray + CloudWatch + Lambda Powertools | 분산 트레이싱 + 구조화 로깅 + 대시보드 + 알림 |
| Security | API Gateway Usage Plan + WAF | Rate limit + API Key + DDoS 방지 |
| IaC | AWS SAM | 단일 템플릿 배포 (throttle, WAF, X-Ray 포함) |

### 5.7 Decision Log

설계 과정에서 검토한 주요 결정과 근거.

| DP | 결정 | 검토한 대안 | 선택 이유 |
|----|------|-----------|----------|
| DP1 | Approach A (Search-Centric MLP) | Full-Loop (B), Vertical Slice (C) | 핵심 차별화 집중, 4/6 실현 가능 |
| DP2 | Hybrid C (shared/ + Lambda) | Core 재사용 (A), 별도 서비스 (B) | 검증 코드 활용 + Lambda 최적화 |
| DP3 | Supabase PostgreSQL | DynamoDB, Qdrant payload, S3 JSON | full-text search, SQL aggregation, Lovable 통합 |
| DP4 | Lovable (+ v0) | Bolt.new, Cursor, Retool, Replit | 네이티브 Supabase, MVP 속도 최고 |
| DP5 | EventBridge + Lambda | SQS (폴링 비용), Step Functions (과잉), 동기 처리 | $0 유휴 비용, push 방식, Phase 2 확장 가능 |
| DP6 | AWS Lambda + warming | GCF 2nd Gen, Fly.io | CTO 요구 + 공식 MCP 라이브러리 존재 |
| DP7 | awslabs.mcp-lambda-handler | REST-only, ECS 하이브리드 | AWS 공식, Streamable HTTP stateless 모드 |
| DP8 | Qdrant Cloud free | Pinecone, pgvector, Weaviate | 기존 통합, async 최고, 2.5% 사용률 |
| DP9 | text-embedding-3-small | text-embedding-3-large, gemini-embedding-001 | 최저 비용, E2에서 대안 실험 |
| DP10 | Cohere Rerank 3.5 (유료) | Jina v2, self-hosted cross-encoder | 기존 통합, 유료 전환 완료. Jina는 E3 비교용 |

---

## 6. Serverless Design Principles

### 6.1 최신성 (Freshness) — Lexical-First / Semantic-Later

**문제**: 등록 직후 검색 요청 시 임베딩 미완료로 검색 누락 가능.

**해법**: 2-track 검색.

| Track | 대상 | 방식 | 활성화 시점 |
|-------|------|------|-----------|
| Semantic | index_status='indexed' | Qdrant vector search | 임베딩 완료 후 (~30초) |
| Lexical | index_status='pending' | Supabase tsvector | 등록 즉시 (0초) |

Search Lambda가 두 track을 merge → deduplicate → rerank.

### 6.2 안정성 / 완결성 (Consistency)

**3중 안전장치:**

| 장치 | 설명 |
|------|------|
| Idempotent upsert | Qdrant ID = `uuid5(MCP_DISCOVERY_NAMESPACE, tool_id)`. 재처리 안전 |
| Atomic status | Supabase `index_status`: `pending` → `indexed` / `failed`. Qdrant 성공 후에만 전이 |
| DLQ | Index Lambda 실패 → Lambda target DLQ (SQS) → 재시도/알림 |

**실패 시나리오:**

| 실패 지점 | 상태 | 복구 |
|-----------|------|------|
| OpenAI embed 실패 | pending, Qdrant 없음 | EventBridge 재시도 → 성공 시 정상 |
| Qdrant upsert 실패 | pending, Qdrant 없음 | 재시도 → idempotent |
| Supabase status 업데이트 실패 | pending, Qdrant 있음 | 재시도 → upsert idempotent + status 재업데이트 |
| Lambda timeout | 어느 단계든 | DLQ → 자동 재시도 |

어느 시점에서 죽어도 `pending` 상태가 유지 → lexical 검색 계속 동작.

### 6.3 Cold Start 대응

| 전략 | 설명 | 비용 |
|------|------|------|
| **SnapStart 필수** | Python 3.12+ GA. 메모리 스냅샷에서 복원 → cold start 3-5초 → **~200-500ms** (90% 감소). `after_restore` 훅에서 Qdrant/Supabase/Cohere 클라이언트 재연결 처리 필수 | $0 |
| Lambda 메모리 512MB+ | cold start ~40% 감소 효과. 128MB 기본값 사용 금지 | $0 (free tier 내) |
| Lambda Layer | shared/ core + numpy + qdrant-client를 Layer로 패키징 → cold start 60-75% 감소 | $0 |
| Handler 밖 초기화 | 클라이언트를 handler 밖에서 생성 → warm start 시 재사용 | $0 |
| CloudWatch warming ping | 5분 간격. **Qdrant search + Supabase query를 실제 호출** → 두 서비스 모두 활성 유지 (Qdrant free: 1주 미사용 시 자동 정지, Supabase free: 7일 미사용 시 일시정지) | $0 |

Warm 상태 Search 응답: Qdrant ~10ms + Cohere ~100ms + 오버헤드 ~100ms ≈ **~300ms**.

### 6.4 외부 API 타임아웃 전략

각 외부 호출에 독립 타임아웃 + 잔여 시간 기반 동적 버짓:

| 호출 | 타임아웃 | 실패 시 |
|------|---------|--------|
| Qdrant search | 5초 | Supabase full-text fallback |
| Cohere rerank | 5초 | Qdrant 점수 기반 결과 직접 반환 (reranking 스킵) |
| OpenAI embed (Index Lambda) | 10초 | SQS DLQ → 재시도 |
| Lambda 전체 | 15초 | API Gateway가 클라이언트에 timeout 반환 |

```python
# 잔여 시간 기반 동적 타임아웃
remaining = context.get_remaining_time_in_millis() / 1000
qdrant_timeout = min(5, remaining - 7)  # Cohere + 오버헤드 여유
cohere_timeout = min(5, remaining - 2)  # 응답 직렬화 여유
```

### 6.5 Degraded Mode

전체 검색 파이프라인이 아닌 부분 장애 시에도 서비스 제공:

| 장애 | Degraded Mode | 사용자에게 표시 |
|------|--------------|----------------|
| Qdrant 다운 | Supabase full-text search (전체 도구 대상, reranking 스킵) | "검색 품질이 일시적으로 제한됩니다" |
| Cohere 다운/429 | Qdrant 점수 기반 결과 직접 반환 | 정상 응답 (품질 약간 저하) |
| Supabase 다운 | Qdrant semantic 검색만 (lexical fallback 없음, pending 도구 누락) | 정상 응답 (신규 등록 도구 누락 가능) |
| OpenAI 다운 | Index Lambda 실패 → DLQ. 검색은 정상 동작 | Provider에게 "인덱싱 지연 중" 표시 |

### 6.6 Observability

| 계층 | 도구 | 설정 |
|------|------|------|
| **분산 트레이싱** | AWS X-Ray | Lambda + API Gateway 활성화. 외부 API 호출을 subsegment로 기록. Free tier 100K traces/mo |
| **구조화 로깅** | Lambda Powertools (Python) | 모든 Lambda에 request_id, 각 외부 호출 latency_ms, 결과 요약을 JSON 구조로 로깅 |
| **대시보드** | CloudWatch Dashboard | Search p50/p95 latency, Qdrant/Cohere/Supabase 개별 latency, error rate, cold start rate, 캐시 hit rate |
| **알림** | CloudWatch Alarms | Search p95 > 2초, error rate > 5%, Qdrant/Supabase health check 실패 → SNS 알림 |
| **비용 알림** | AWS Budgets | 월 $20 초과 시 알림. Lambda 호출 수 급증 탐지 |

---

## 7. Existing Document Conflicts & Document Mapping

### 7.1 갱신이 필요한 사항

| # | 기존 문서 | 변경 | 이유 |
|---|----------|------|------|
| 1 | `architecture.md` DP8: "로컬 FastAPI → Lambda" | 구체화 | Lambda 확정, Supabase/EventBridge 추가 |
| 2 | `code-structure.md`: `src/api/main.py` FastAPI | 수정 | MLP는 Lambda handler. FastAPI는 로컬 실험용 |
| 3 | `architecture.md`: Bridge MCP Server | 수정 | Lambda + Streamable HTTP + awslabs 라이브러리 |
| 4 | CLAUDE.md: North Star 설명 | 보완 | 실험 풀 vs 제품 풀 구분 |
| 5 | `implementation.md`: Phase 8/13 순서 | 재배치 | MLP에서 Search API + Bridge 동시 구현 |
| 6 | (신규) Metadata store | 추가 | Supabase PostgreSQL. 기존 설계에 미정의 |
| 7 | (신규) Lexical fallback | 추가 | Semantic-only → Lexical-first 패턴 |

### 7.2 기존 설계와 정합 (변경 불필요)

| 사항 | 근거 |
|------|------|
| ABC 패턴 (PipelineStrategy, Embedder, Reranker) | Lambda에서도 동일 |
| Composite score (relevance + quality + boost) | SearchResult, ScoreBreakdown 이미 구현 |
| GEO Score 6D | 기존 설계 그대로 |
| Confidence branching (gap > 0.15) | 그대로 |
| Ground Truth / 실험 체계 (E0-E7) | 오프라인 독립 |
| Popularity 미반영 | 기존 결정 일치 |
| tool_id가 최종 검색 단위 | server는 내부 최적화 레이어 |
| Sequential 기본, Parallel은 실험 후보 | feature flag로 전환 가능 |

### 7.3 문서 매핑

| 반영 대상 | 반영 내용 | 신규/수정 |
|----------|----------|----------|
| `mlp/docs/service-design.md` | 이 문서 (Section 1-7 전체) | 신규 |
| `docs/design/architecture.md` | DP8 구체화, metadata store, lexical fallback | 수정 |
| `docs/design/code-structure.md` | shared/, lambdas/, experiments/ 구조 | 수정 |
| `CLAUDE.md` | 제품 풀 vs 실험 풀, Lambda 배포 | 수정 |
| `docs/plan/implementation.md` | MLP Phase 통합, 순서 재조정 | 수정 |
| `docs/plan/checklist.md` | MLP 체크리스트 항목 | 수정 |
| `docs/design/metrics-dashboard.md` | Provider Dashboard GEO 뷰 | 수정 |

---

## Appendix A: Pool Data

| 항목 | 수량 | 설명 |
|------|------|------|
| MCP-Zero 원본 | 308 entries | servers.json |
| Unique 서버 | 293 | 14개 서버 중복 (AWS 2x, Redis 3x 등) |
| base_pool.json | 292 | snake_case 변환 + 중복 제거 후 1개 추가 탈락 |

문서에서는 "MCP-Zero 308" (원본)과 "Pool 292" (실제 사용)를 구분하여 표기.

## Appendix B: Retrieval Strategy 운영 원칙

- MLP 기본 전략: **Sequential** (server index → filtered tool search → rerank)
- Parallel Strategy: 실험 트랙 1순위 후보 (E1에서 비교)
- feature flag / config로 릴리즈 직전 스위치 가능하도록 설계
- `StrategyRegistry`로 동일 평가 하네스에서 비교

## Appendix C: Provider Metadata 수정 범위

| 구분 | 필드 | GEO 최적화 대상 | Provider 수정 가능 |
|------|------|----------------|-------------------|
| Description 류 | description, use-case, examples, tags | Yes | Yes (재등록) |
| 관측 사실 | tool_name, input_schema, execution metrics | No | No |

MLP에서는 수정 UI 없음. 진단 리포트 → Provider 자체 서버에서 수정 → 재등록.
