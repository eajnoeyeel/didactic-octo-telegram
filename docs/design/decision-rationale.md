# 기술 결정 근거 (Decision Rationale)

> 대화 히스토리에서 복원. 각 기술 선택 시 비교한 옵션과 트레이드오프를 기록한다.
> 작성 기준: 2026-03-24

---

## DP0 — Bridge MCP Server 아키텍처 (접근 방식)

### 배경

LLM이 여러 MCP 서버에 연결되면 모든 툴 정의가 컨텍스트에 올라간다.
```
서버 10개 × 툴 평균 20개 × 툴 정의 300토큰 = 60,000토큰 → 비용 ↑, LLM 추론 품질 ↓
```

### 비교한 옵션

| 옵션 | 설명 | 평가 |
|------|------|------|
| **A: Static 2-Tool Proxy** | LLM에 `find_best_tool` + `call_tool` 고정 노출 | ✅ 선택 |
| **B: Dynamic Tool Injection** | `notifications/tools/list_changed`로 필요할 때만 툴 동적 노출 | ❌ |
| **C: N-way Routing** | 쿼리에 따라 여러 MCP 서버로 직접 라우팅 | ❌ (MCP 프로토콜 제약) |

**접근 B 탈락 이유**: `tools/call`은 연결된 서버에만 보낼 수 있음. 동적 주입을 해도 Proxy가 대신 호출해야 하므로 인증 구조가 접근 A와 동일. 복잡도만 추가.

**접근 A 선택 이유**:
- Prompt Bloating 완전 해결 (2툴 고정)
- 모든 MCP Client 호환 (현재 구현체 전부 `tools/list` 자동 호출)
- `call_tool` 단일 병목으로 Analytics 100% 로깅 가능
- CTO 설명 용이: "툴 2개, 역할 명확"

---

## DP2 — 추천 단위 (2-Layer)

### 비교한 옵션

| 옵션 | 설명 | 결론 |
|------|------|------|
| **A: MCP 서버 단위** | "Semantic Scholar를 연결해라" 수준. Smithery와 동일 레벨 | ❌ LLM이 실제 호출하는 단위(Tool)와 불일치 |
| **B: 개별 Tool 단위** | "search_papers를 호출해라" 수준. 이미 연결된 서버들 중 선택 | ❌ 서버 수가 많으면 검색 공간 폭발 |
| **C: 2-Layer (서버→Tool)** | 서버 추천 → 해당 서버 내 Tool 추천 | ✅ 선택 |

**2-Layer 선택 이유**: LLM의 실제 호출 단위(Tool)로 최종 추천하되, 검색 공간을 서버로 먼저 좁혀 정확도 향상. 단, 2-Layer가 1-Layer 대비 실제로 유리한지 E0 실험으로 검증.

---

## DP3 — 파이프라인 전략 (Strategy Pattern)

### 비교한 옵션

| 전략 | 동작 방식 | 장점 | 단점 |
|------|-----------|------|------|
| **A: Sequential** | 서버 인덱스 → 필터된 Tool 검색 → Rerank | 단순, 해석 용이 | Layer 1 실패 시 복구 불가 (Hard Gate) |
| **B: Parallel** | 서버 + Tool 인덱스 병렬 → RRF 점수 합산 → Rerank | Layer 1 미스에 강건 | 복잡도 높음, 비용 2배 |
| **C: Taxonomy-gated** | 의도 분류기 → 카테고리 서브인덱스 → Rerank | 카테고리 내 정밀도 높음 | 분류기 오류 시 전체 실패 (Fragile) |

**결정**: 전략 하나만 선택하지 않고 **Strategy Pattern으로 모두 구현 후 실험(E1)으로 비교**. 아키텍처 결정이 이미 내려진 것.

---

## DP4 — 임베딩 모델

### 비교한 옵션

| 모델 | 특징 | 평가 |
|------|------|------|
| **OpenAI text-embedding-3-small** | 1536차원, $0.02/1M tokens, Lambda 친화 | ✅ 채택 |
| **BGE-M3** | Dense + Sparse + Multi-vector 단일 모델, 무료 | ✅ 채택 (대안) |
| **Voyage AI voyage-code-2** | 코드/기술 텍스트 특화, 무료 200M tokens/월 | ❌ **명시적 금지** |
| **sentence-transformers (로컬)** | 완전 무료, 모델 ~400MB | ❌ Lambda cold start 심각 |

**Voyage voyage-code-2 금지 이유**: MCP Tool description은 자연어(서비스 설명)지 코드가 아님. 코드 특화 임베딩을 자연어 도메인에 쓰면 오히려 성능 저하.

**BGE-M3 강점**: BM25와 Dense 검색을 따로 구현하지 않고 하나의 모델로 처리 → Hybrid 전략 구현 복잡도 대폭 감소.

**sentence-transformers 탈락 이유**: 모델 파일 ~400MB → Lambda cold start에서 로딩 시간이 치명적. 컨테이너 또는 SageMaker 필요, CTO 서버리스 요구사항과 충돌.

---

## DP5 — Reranker

### 비교한 옵션

| 옵션 | 특징 | 평가 |
|------|------|------|
| **Cohere Rerank 3** | SOTA 성능, 무료 1,000 req/월 | ✅ 선택 |
| **Cross-Encoder (경량)** | 로컬 실행, 무료, 느림 | 초기 고려 → ❌ Cohere으로 대체 |
| **LLM fallback** | 확신 낮을 때 LLM이 직접 판단 | ✅ Low-confidence 케이스용 fallback |

**초기 계획**: Cross-Encoder(경량) → 변경 이유: Cohere Rerank 3가 SOTA 성능이고 무료 tier로 실험 가능. 성능 검증 없이 경량 모델을 먼저 쓸 이유가 없음.

**LLM fallback 유지 이유**: Confidence gap이 매우 작을 때 단순 점수 기반 선택보다 LLM이 context를 보고 판단하는 것이 더 정확할 수 있음.

---

## DP6 — Confidence 분기 방식

### 비교한 옵션

| 옵션 | 설명 | 평가 |
|------|------|------|
| **A: 항상 Top-1 반환** | 단순, LLM이 바로 사용 | ❌ 확신 낮을 때 틀린 Tool 반환 위험 |
| **B: 항상 Top-3 반환** | 구현 단순, LLM이 알아서 선택 | ❌ 판단을 LLM에 미룸 (불필요한 LLM 부하) |
| **C: Gap 기반 동적 분기** | gap 크면 Top-1, 작으면 Top-3 + hint | ✅ 선택 |

**결정**: `rank-1 score - rank-2 score > 0.15` → Top-1 반환; ≤ 0.15 → Top-3 + disambiguation hint 반환.

**0.15 threshold**: 초기값. 실험적으로 calibrate 예정. 근거가 없으므로 "초기값"으로 명시하고 E2/E3 결과 후 조정.

**동적 분기 선택 이유**: Precision@1과 UX 사이의 최적 균형. Top-1만 반환하면 틀렸을 때 UX 최악, Top-3 항상이면 불필요한 LLM 추론 비용.

---

## DP8 — 벡터 스토어 & 배포 아키텍처

### 벡터 스토어 비교 (전체 지형도)

#### 그룹 1: 파일 기반 (Lambda 내부 직접 로드)

| | FAISS | Annoy | hnswlib | numpy |
|--|-------|-------|---------|-------|
| 스케일업 | 100만개+ | 10만개 수준 | 100만개+ | 10만개 이하 |
| 복잡도 | 중간 | 낮음 | 낮음 | 매우 낮음 |
| 특이사항 | Meta 표준 | 빌드 후 추가 불가 | HNSW 전용 | 의존성 제로 |

> 1,000개 규모에선 numpy 브루트포스로 충분 (`np.dot(query_vec, all_vecs.T)` = 수 ms). FAISS 근사 알고리즘은 수십만 개부터 필요.

#### 그룹 2: 외부 서비스 (Lambda → REST API)

| | **Qdrant Cloud** | Pinecone | Weaviate | pgvector (Supabase) | Chroma |
|--|---|---|---|---|---|
| 무료 티어 | **1GB** | 100MB | 14일 trial | 500MB | 있음 |
| 필터링 | **payload 필터 내장** | 기본 | ✅ | SQL | 기본 |
| 오픈소스 | ✅ (Rust) | ❌ | ✅ | ✅ | ✅ |

#### 그룹 3: AWS 네이티브

| | OpenSearch Serverless | DynamoDB+커스텀 | S3+FAISS |
|--|---|---|---|
| 최소 비용 | **~$700/월** | ~$0 | ~$0 |
| 결론 | ❌ 오버킬 | ❌ 직접 구현 복잡 | ✅ |

### 최종 선택: Qdrant Cloud free tier

**핵심 이유 2가지**:
1. **`server_id` 필터가 필수** — Sequential Strategy Stage 2에서 "이 서버 소속 Tool만 검색"이 필요. Qdrant는 payload 필터 + 벡터 검색을 단일 API 호출로 처리
2. **무료 1GB** — 약 4만 개 Tool 수용. Pinecone 100MB 대비 10배, 실험 단계 인프라 비용 $0

**pgvector 탈락**: 기존 Postgres가 없으면 도입 불리. SQL 쿼리 직접 작성 필요 (Qdrant의 payload 필터 API 대비 개발 부담 큼).

**Pinecone 탈락**: 무료 티어 100MB로 Pool 규모 실험 시 부족. 블랙박스 (직접 튜닝 불가).

**Bedrock Knowledge Bases 탈락**: OpenSearch Serverless 백엔드 사용 → 최소 비용 ~$690/월. 데모 프로젝트에 부적합.

**FAISS+S3 vs Qdrant 선택 이유**: FAISS+S3도 비용 ~$0이지만, 인덱스 업데이트 시 파일 재생성 필요. Qdrant는 upsert 가능 + payload 필터 내장. 실험 루프에서 데이터 추가/변경이 잦으므로 Qdrant가 적합.

---

## DP7 — 데이터 소스

### 비교한 옵션

| 옵션 | 설명 | 결론 |
|------|------|------|
| Smithery 크롤링 (전체) | 전체 레지스트리 크롤링 | ❌ 품질 통제 어려움 |
| 수동 큐레이션 | 직접 50~100개 선별 | ✅ Pool 통제 가능 |
| Synthetic variants | LLM으로 description 변형 | ✅ 보완적 사용 |

**결정**: 50~100개 큐레이션 + synthetic query variants 조합.

---

## DP9 — 평가 방식

### 비교한 옵션

| 옵션 | 지표 | 근거 |
|------|------|------|
| **A: 핵심만** | Precision@1, Recall@K, Latency | TREC 표준, RAG-MCP 논문 동일 사용 |
| **B: 중간** | A + Confusion Rate, ECE | arxiv 2601.16280, Naeini AAAI 2015 |
| **C: 풀** | B + MRR, Cost/Correct, DQS 상관관계 | RAGAS (EACL 2024) |

**결정**: Option B 채택.

**B 선택 이유**: C는 구현 비용 대비 추가 설득력이 5주 프로젝트에서 크지 않음. B는 CTO의 "모니터링 → 개선 루프" 스토리를 수치로 증명하는 최소 세트.

---

## Tool ID 구분자 (`::`)

**비교한 옵션**: `/` vs `::` vs `:` vs `__`

**`/` 탈락 이유**: Smithery qualifiedName 자체에 `/`가 포함 (`@anthropic/github`). `/`로 구분하면 `"@anthropic/github/search_issues"`에서 서버가 어디까지인지 파싱 불가.

**`::`선택 이유**: Smithery qualifiedName, Tool name 어디에도 `::` 패턴이 나타나지 않아 안전한 구분자.

---

## 보조 도구 선택

| 도구 | 대안 고려 | 선택 이유 |
|------|-----------|-----------|
| **W&B** | MLflow, TensorBoard | 실험 결과 자동 기록 + 비교 그래프, 무료 |
| **Langfuse** | LangSmith, PromptLayer | LLM 호출 trace + 비용 추적, 오픈소스 |
| **FastAPI** | Flask, Django | Async 네이티브, Pydantic 통합, Lambda 배포 용이 |
| **uv** | pip, poetry | 가장 빠른 Python 패키지 매니저 |
| **ruff** | black + flake8 + isort | 단일 도구로 lint + format, 속도 압도적 |
| **pytest-asyncio** | asynctest | pytest 생태계 통합, `asyncio_mode="auto"` |
