# Pre-Mortem: MCP Discovery MLP

**Date**: 2026-04-04
**Status**: Draft
**Base Document**: `mlp/docs/service-design.md` v0.1

---

## Risk Summary

- **Tigers**: 14 (Launch-blocking: 4, Fast-follow: 5, Track: 5)
- **Paper Tigers**: 4
- **Elephants**: 3

---

## 1. Launch-Blocking Tigers

이것들이 해결되지 않으면 서비스가 첫 사용자에게부터 깨진다.

### T1. Qdrant Cloud / Supabase Free Tier 자동 정지

| 항목 | 내용 |
|------|------|
| **문제** | Qdrant Cloud free tier는 **1주일 비활성 시 자동 정지**, Supabase free tier는 **7일 비활성 시 자동 일시정지**. 정지 후 첫 요청에 connection error 또는 수 초~수 분 지연 발생 |
| **발생 조건** | MLP 단계에서 매일 트래픽이 보장되지 않음. 주말/연휴 후 월요일에 CTO가 시연하러 들어오면 서비스 다운 |
| **영향도** | **치명적** — 첫 인상에서 "서비스가 안 돌아간다" |
| **발생 가능성** | **높음** — MLP에서 거의 확실하게 발생 |
| **현재 설계 취약점** | CloudWatch warming ping은 Lambda만 warm 유지. Qdrant/Supabase의 비활성 정지는 별도 대응 없음 |
| **개선안** | (1) CloudWatch 5분 warming ping이 Qdrant search + Supabase query를 실제로 호출하도록 구성 — 두 서비스 모두 활성 상태 유지. (2) Supabase에 pg_cron으로 자체 keep-alive 쿼리 설정 (1시간 간격 `SELECT 1`). (3) 모니터링: 두 서비스 health check 실패 시 알림 |

### T2. Lambda Cold Start가 p95 3초 목표 초과

| 항목 | 내용 |
|------|------|
| **문제** | Python + numpy + pydantic + httpx + qdrant-client + cohere + openai SDK → cold start **3-5초**. 이것만으로 3초 예산 소진. 검색 파이프라인 실행 시간 추가하면 **총 4-8초** |
| **발생 조건** | warming ping 실패, 동시 요청 수 증가로 새 인스턴스 생성, 또는 15분 이상 요청 없을 때 |
| **영향도** | **치명적** — LLM 에이전트가 tool 호출에 8초 대기하면 사용자 경험 붕괴 |
| **발생 가능성** | **높음** — SnapStart 미적용 시 확실히 발생 |
| **현재 설계 취약점** | warming ping만으로는 동시 요청 증가 시 새 인스턴스의 cold start를 방지할 수 없음 |
| **개선안** | (1) **Lambda SnapStart 필수 적용** (Python 3.12+ GA). 3-5초 → ~200-500ms로 90% 감소. 단, `after_restore` 훅에서 Qdrant/Supabase/Cohere 클라이언트 재연결 처리 필요. (2) Lambda 메모리 512MB 이상 할당 (cold start ~40% 감소). (3) Lambda Layer로 공통 의존성 분리 (60-75% cold start 감소). (4) warming ping 병행 유지 |

### T3. API Gateway에 Rate Limiting 미설정 — Denial-of-Wallet

| 항목 | 내용 |
|------|------|
| **문제** | API Gateway에 throttling 미설정 시, 악의적/우발적 트래픽 폭주가 그대로 Lambda → Cohere/OpenAI API 호출로 전파. 1만 건 요청 = 1만 건 유료 API 호출 |
| **발생 조건** | 공개 URL이 노출된 순간. 봇, 크롤러, 의도적 공격 |
| **영향도** | **치명적** — 실제 사례: $47,000 주말 청구서, $100,000 봇 스팸 |
| **발생 가능성** | **중간** — 개인 프로젝트지만 공개 API면 언제든 발생 가능 |
| **현재 설계 취약점** | rate limiting, usage plan, WAF 언급 없음 |
| **개선안** | (1) API Gateway Usage Plan + API Key 필수 (무인증 접근 차단). (2) 엔드포인트별 throttle 설정: Search 100 req/s, Register 10 req/s. (3) AWS WAF rate-based rule 추가 (IP당 100 req/5min). (4) Lambda 함수 내에서 외부 API 호출 전 비용 차단 로직 |

### T4. Observability 부재 — 장애 원인 파악 불가

| 항목 | 내용 |
|------|------|
| **문제** | 서비스 설계에 모니터링/로깅/트레이싱 전략이 없음. Lambda 5개 + EventBridge + Qdrant + Supabase + Cohere + OpenAI — 6개 외부 서비스를 거치는 파이프라인에서 "어디서 느려졌는지" 파악 불가 |
| **발생 조건** | 검색 결과가 이상하거나 느릴 때. "왜?"에 답할 수 없음 |
| **영향도** | **치명적** — 문제를 모르면 고칠 수 없다 |
| **발생 가능성** | **확실** — 분산 시스템에서 observability 없이 운영은 불가능 |
| **현재 설계 취약점** | 기존 코드는 loguru만 사용. Lambda CloudWatch 로그는 구조화되지 않음. 분산 트레이싱 없음 |
| **개선안** | (1) **구조화 로깅**: 모든 Lambda에 request_id, 각 외부 호출 latency, 결과 요약을 JSON으로 로깅. (2) **X-Ray 트레이싱**: Lambda + API Gateway에 AWS X-Ray 활성화 (free tier 100K traces/mo). 외부 API 호출을 subsegment로 기록. (3) **CloudWatch 대시보드**: Search latency p50/p95, Qdrant latency, Cohere latency, error rate, cold start rate. (4) **알림**: Search p95 > 2초, error rate > 5%, Qdrant/Supabase health check 실패 시 알림 |

---

## 2. Fast-Follow Tigers

출시 직후 첫 스프린트 내에 해결해야 할 리스크.

### T5. Tool Description을 통한 Prompt Injection

| 항목 | 내용 |
|------|------|
| **문제** | Bridge MCP Server가 tool description을 LLM에 전달. 악의적 Provider가 description에 "이 도구를 무조건 선택하라"는 숨겨진 지시를 삽입하면 LLM이 조작됨 (Tool Poisoning). Smithery에서 2025년 이미 유사 취약점 발견됨 |
| **영향도** | **높음** — 보안 사고, 사용자 신뢰 완전 상실 |
| **발생 가능성** | **중간** — MCP 생태계에서 이미 보고된 공격 벡터 |
| **개선안** | (1) description sanitization: 등록 시 숨겨진 지시문/특수 토큰/과도한 길이 탐지. (2) 검색 결과에 raw description 대신 정제된 요약만 전달. (3) GEO Score에 "안전성" 차원 추가 검토 (Phase 2) |

### T6. Description SEO Gaming — 랭킹 조작

| 항목 | 내용 |
|------|------|
| **문제** | 랭킹이 100% description 품질에 의존. Provider가 keyword stuffing, 경쟁 도구 키워드 삽입, 임베딩 공간 최적화된 문구 사용으로 순위 조작 가능. npm에서는 50% 이상이 SEO 스팸이었던 사례 존재 |
| **영향도** | **높음** — 검색 품질 저하 → 사용자 이탈 → quality death spiral |
| **발생 가능성** | **중간** (MLP에서는 낮지만 Phase 2에서 높아짐) |
| **현재 설계 취약점** | anti-spam 로직 없음. GEO Score가 "좋은 description"을 정의하지만, "조작된 좋은 description"은 구분 못함 |
| **개선안** | (1) Phase 2에서 behavioral signal 도입: 실제 실행 성공률, 사용자 피드백을 quality_score에 반영. (2) 등록 시 description 유사도 검사: 기존 도구와 코사인 유사도 > 0.95이면 플래그. (3) 비정상 등록 패턴 탐지 (같은 IP에서 대량 등록 등) |

### T7. Cohere Rate Limit Ceiling

| 항목 | 내용 |
|------|------|
| **문제** | Cohere Production key: **1,000 req/min** (rerank). 동시 사용자 17명이 1초에 검색하면 한도. 이후 429 에러 |
| **영향도** | **높음** — 검색 서비스 자체가 중단 |
| **발생 가능성** | **낮음** (MLP), **높음** (트래픽 증가 시) |
| **현재 설계 취약점** | Reranker ABC fallback이 설계에는 있지만 MLP에서 미구현 |
| **개선안** | (1) LLM fallback reranker 구현 (low-confidence 또는 Cohere 429 시). (2) Jina Reranker v2를 secondary로 구현 (10M 무료 토큰). (3) Cohere 호출 전 클라이언트 측 rate limiter (토큰 버킷). (4) 결과 캐싱: 동일 쿼리 30분 TTL |

### T8. 검색 결과 캐싱 부재

| 항목 | 내용 |
|------|------|
| **문제** | 동일 쿼리가 반복되면 매번 Qdrant + Cohere 호출. 비용 + 지연 + rate limit 소모 |
| **영향도** | **높음** — 불필요한 외부 API 호출이 모든 리스크를 증폭 |
| **발생 가능성** | **높음** — LLM 에이전트는 같은 패턴의 쿼리를 반복하는 경향 |
| **개선안** | (1) Lambda 내 인메모리 캐시 (warm instance에서 TTL 5분). (2) 또는 DynamoDB/ElastiCache에 쿼리 해시 → 결과 캐싱 (비용 대비 효과 검토 필요) |

### T9. Qdrant 단일 노드 — 가용성 0% HA

| 항목 | 내용 |
|------|------|
| **문제** | Qdrant Cloud free tier = 단일 노드. 노드 장애 = 검색 전체 불가. Lexical fallback은 pending 도구만 대상이므로 대부분의 도구가 검색 불가 |
| **영향도** | **높음** — 검색 서비스 전체 중단 |
| **발생 가능성** | **낮음** (관리형 서비스), 하지만 발생 시 대응 불가 |
| **개선안** | (1) MLP에서는 수용. Qdrant 장애 시 Supabase full-text search로 전체 fallback하는 degraded mode 구현. (2) Phase 2에서 유료 tier (HA 지원)로 업그레이드 |

---

## 3. Track Tigers

모니터링하되 즉시 조치 불필요. 트리거 조건 충족 시 대응.

### T10. Evaluation-Production Gap

| 트리거 | 대응 |
|--------|------|
| Precision@1 >= 50% 달성했지만 실제 LLM 클라이언트가 결과에 불만족 | online evaluation 도입: 실행 성공/실패 로그, implicit feedback (선택된 도구 vs 무시된 도구) |

근본 원인: 474개 GT는 LLM 생성 step-level 쿼리 포함. 실제 사용자 쿼리 분포와 다를 수 있음. Precision@1은 binary metric이라 "거의 맞는" 결과도 0점.

### T11. EventBridge 중복 이벤트 전달

| 트리거 | 대응 |
|--------|------|
| 같은 서버가 Qdrant에 2번 upsert되는 것이 관찰됨 | 현재 uuid5 idempotent upsert로 데이터 무결성은 보장됨. 비용 낭비만 발생. 고빈도 시 deduplication 로직 추가 |

### T12. Supabase 500MB 저장 한도

| 트리거 | 대응 |
|--------|------|
| 쿼리 로그/분석 데이터가 400MB 도달 | 오래된 로그를 S3로 아카이브하는 pg_cron job 설정. 또는 Supabase Pro ($25/mo)로 업그레이드 |

### T13. Lambda INIT 과금으로 비용 상승

| 트리거 | 대응 |
|--------|------|
| Cold start 빈도가 높아 INIT 과금이 눈에 띄게 증가 | SnapStart 적용 확인. 미적용 시 22x 비용 증가 보고됨. Lambda 메모리 최적화 |

### T14. 외부 API 타임아웃 체인 — 29초 hard limit

| 트리거 | 대응 |
|--------|------|
| Qdrant 느려짐 + Cohere 느려짐이 동시 발생하여 API Gateway 29초 초과 | 각 외부 호출에 독립 타임아웃 설정: Qdrant 5초, Cohere 5초, 전체 Lambda 15초. 잔여 시간 기반 동적 타임아웃 버지닝 |

---

## 4. Paper Tigers

무섭게 보이지만 실제로는 관리 가능한 리스크.

### PT1. Lambda 동시성 한도 (1,000)

**왜 관리 가능한가**: MLP 트래픽에서 동시 Lambda 인스턴스가 100을 넘을 가능성 극히 낮음. 서비스가 성장하면 한도 상향 요청 가능.
**진짜 Tiger가 되는 조건**: 다른 Lambda 함수가 같은 AWS 계정에서 동시성을 소모하는 경우. → 별도 AWS 계정 사용 또는 reserved concurrency 설정.

### PT2. Supabase 500MB로 도구 메타데이터 부족

**왜 관리 가능한가**: 292 서버 + ~2,800 도구의 메타데이터는 ~5-10MB. 500MB의 2%. 쿼리 로그가 아닌 이상 넘칠 가능성 없음.

### PT3. Qdrant 1GB로 벡터 부족

**왜 관리 가능한가**: 2,800 도구 × 1536d × float32 ≈ 25MB. 1GB의 2.5%. 10만 도구까지 수용 가능.

### PT4. API Gateway 29초 타임아웃

**왜 관리 가능한가**: warm 상태 Search 파이프라인은 ~300ms. cold start + 파이프라인도 SnapStart 적용 시 ~1-2초. 29초 한도까지 여유 충분.
**진짜 Tiger가 되는 조건**: 모든 외부 API가 동시에 느려지는 경우 (위 T14).

---

## 5. Elephants in the Room

팀이 알고 있지만 직면하지 않는 불편한 진실.

### E1. Chicken-and-Egg: 사용자가 없다

**불편한 진실**: 이 플랫폼은 양면 시장이다. LLM 클라이언트(수요)와 MCP Provider(공급) 모두 없는 상태에서 출시한다. MCP-Zero 292개 서버는 프로젝트 팀이 임포트한 것이지, Provider가 자발적으로 등록한 것이 아니다.

**대화 시작점**: "MLP 시연 대상은 CTO 1명이다. CTO 시연이 성공하면 다음 단계는 무엇인가? 실제 사용자 획득 전략이 있는가, 아니면 이 프로젝트의 목적은 기술 역량 시연인가?"

**시사점**: 만약 목적이 기술 역량 시연이라면, 양면 시장 문제는 pre-mortem 범위 밖. 만약 실제 서비스화가 목표라면, 공급 측 부트스트래핑(Official MCP Registry에서 자동 크롤링, Smithery API에서 pull)이 MLP에 포함되어야 한다.

### E2. Core Thesis가 틀릴 수 있다

**불편한 진실**: "Higher description quality → higher tool selection rate"는 Description Smells 논문(+11.6% uplift)이 뒷받침하지만, 그 연구는 **description smell 수정** 후의 uplift이지, **GEO Score 6D 최적화** 후의 uplift이 아니다. GEO Score가 실제 selection rate을 개선하는지는 아직 검증되지 않았다 (E4 실험 예정).

**대화 시작점**: "만약 E4 실험에서 GEO Score 개선이 selection rate에 유의미한 영향을 주지 않으면, Provider Dashboard의 핵심 가치 제안이 무너진다. 이 경우의 pivot 계획은?"

### E3. 4/26 마감 vs 실제 범위

**불편한 진실**: 남은 시간 ~22일. 현재 설계 범위:
- AWS Lambda 배포 (SAM 템플릿, 5개 Lambda)
- EventBridge 파이프라인
- Supabase 스키마 + RLS + seed 데이터
- Lovable 프론트엔드 (Registry UI + Provider Dashboard + Landing)
- Bridge MCP Server (awslabs.mcp-lambda-handler)
- GEO Score 계산 로직
- 기존 실험 코드도 병행 (E0-E7)

AWS 경험이 깊지 않은 상태에서 이 모든 것을 22일에 완성하는 것은 매우 도전적이다.

**대화 시작점**: "MLP 범위를 더 좁힐 수 있는가? 예를 들어 Bridge MCP Server를 Phase 2로 미루고, REST Search API + Registry UI + Provider Dashboard만 출시하면?"

---

## 6. 검색 엔진 관점 심층 분석

### 6.1 Retrieval 품질 저하 요인

| 요인 | 설명 | 영향 |
|------|------|------|
| **Embedding 유사도 floor** | OpenAI text-embedding-3-small의 코사인 유사도는 무관한 텍스트 간에도 0.68+ 나옴. 임계값 기반 필터링이 무의미할 수 있음 | Qdrant 검색 결과의 bottom-K가 노이즈 |
| **쿼리-문서 비대칭** | 사용자 쿼리는 짧고 의도 중심 ("GitHub repo 검색 도구"), description은 길고 기능 나열 중심. 임베딩 공간에서 다른 위치에 매핑될 수 있음 | retrieval 정밀도 저하 |
| **도메인 외 쿼리** | 풀에 없는 도메인의 쿼리 ("양자 컴퓨팅 시뮬레이션 도구")에 대해 관련 없는 도구를 높은 confidence로 반환 | 사용자 신뢰 손상 |
| **Reranker 역효과** | 구조화된 쿼리(SQL 유사, 파라미터 명시)에서 Cohere cross-encoder가 Stage 1 결과를 악화시키는 사례 보고됨 | confidence gap이 잘못된 도구에 높게 나옴 |

### 6.2 Adversarial Embedding 조작

연구에 따르면 의미 없는 문자열("Text this PieceICWLISHTION")이 자연어 쿼리보다 높은 유사도를 보이는 경우가 있음. Provider가 description에 embedding 공간 최적화된 토큰을 삽입하면 순위 조작 가능.

**방어**: Phase 2에서 BM25 + vector hybrid 검색 도입. 연구에 따르면 hybrid 검색은 corpus poisoning 성공률을 38% → 0%로 감소시킴.

### 6.3 "검색 엔진이 망하는 패턴"과의 매핑

| 패턴 | Google/Yelp 사례 | MCP Discovery 해당 여부 |
|------|-------------------|----------------------|
| 자기 참조적 품질 지표 | Google이 CTR로 랭킹 → 상위 결과에 더 많은 클릭 → 자기 강화 루프 | MLP에서는 해당 없음 (usage data 미반영). Phase 2에서 주의 |
| 정보 비대칭 악용 | Yelp에서 사업자가 가짜 리뷰 작성 | Provider가 description 과장. 검증 메커니즘 없음 |
| 광고 = 검색 결과 혼합 | Google에서 광고와 organic 구분 모호 | `is_boosted` 라벨로 투명성 확보 설계됨. 다만 실제 구현/집행이 관건 |
| Quality death spiral | Gresham's Law: 나쁜 도구가 좋은 도구를 구축 | Description gaming이 보상받으면 정직한 Provider 이탈 |

---

## 7. 수익화/플랫폼 아키텍처 평가

### 7.1 현재 설계의 광고 수용 가능성

현재 `SearchResult.score_breakdown`의 3단 구조(`relevance + quality + boost`)와 `is_boosted` 필드는 **구조적으로는 준비됨**. 하지만 실제 광고 시스템에는 추가로 필요한 것들:

| 필요 요소 | 현재 상태 | 필요 작업 |
|-----------|----------|----------|
| Organic/Sponsored 분리 랭킹 | 단일 파이프라인 | Sponsored 후보를 별도 풀에서 선택 후 organic 결과에 삽입하는 로직 |
| 광고 경매 시스템 | 없음 | Second-price auction 또는 CPC 입찰 시스템 |
| 광고 품질 게이트 | `quality_score` scaffold 존재 | 최소 relevance 임계값 미달 시 광고 미노출 (Google의 Ad Rank 방식) |
| 클릭/노출 카운터 | 없음 | 이벤트 로깅 파이프라인 |
| Fraud 탐지 | 없음 | 클릭 패턴 분석, IP 기반 중복 필터링 |
| 투명성 집행 | `is_boosted` 필드 존재 | 클라이언트 SDK에서 라벨 표시 강제 |

### 7.2 Enshittification 압력

Google의 내부 문서(DOJ 공개)에 따르면, 광고 수익 극대화와 검색 품질은 구조적으로 충돌한다. `boost_score`가 0이 아니게 되는 순간 이 압력이 시작된다.

**방어 원칙** (설계 문서에 명시 권장):
1. Sponsored 결과는 항상 라벨 표시 (클라이언트에서 제거 가능)
2. Sponsored 결과도 최소 relevance 임계값 충족 필수
3. Organic 순위는 boost_score에 의해 절대 변경되지 않음 (별도 슬롯)
4. Provider가 boost 없이도 GEO Score 개선으로 순위 향상 가능해야 함

---

## 8. 확장성 병목 분석

| 컴포넌트 | Read-heavy 병목 | Write-heavy 병목 | 임계점 |
|----------|----------------|------------------|--------|
| **Qdrant free** | 단일 노드, gRPC pool 3개 기본 | upsert 직렬화 | 동시 검색 ~50 req/s에서 지연 증가 예상 |
| **Cohere Rerank** | 1,000 req/min hard limit | N/A | **~17 req/s** (이 이후 429) |
| **Supabase free** | 60 direct connections | 500MB 저장 한도 | 동시 쿼리 ~30에서 connection 부족 |
| **Lambda** | 1,000 concurrent (계정 공유) | N/A | burst 3,000 후 분당 500씩 증가 |
| **API Gateway** | 10,000 req/s (계정 공유) | N/A | MLP에서 도달 불가 |
| **OpenAI Embed** | N/A | batch embedding 시 rate limit | MLP에서는 초기 1회 batch만 |
| **EventBridge** | N/A | 100K events/s | MLP에서 도달 불가 |

**첫 번째 병목**: Cohere 1,000 req/min. 이것이 서비스 전체의 throughput ceiling.

---

## 9. 보안 & 악용 시나리오

| # | 시나리오 | 심각도 | 대응 |
|---|----------|--------|------|
| 1 | **Prompt Injection via description**: Provider가 tool description에 LLM 조작 지시 삽입 | 치명적 | 등록 시 description sanitization, 길이 제한, 패턴 탐지 |
| 2 | **API Key 유출**: Supabase service key가 Lovable 프론트엔드 코드에 노출 | 치명적 | Supabase anon key만 프론트엔드에 사용, service key는 Lambda에서만 |
| 3 | **Description stuffing**: 경쟁 도구 키워드를 description에 삽입하여 순위 탈취 | 높음 | 유사도 기반 중복 탐지, GEO Score에 "정직성" 차원 추가 |
| 4 | **등록 스팸**: 같은 도구를 이름만 바꿔 대량 등록 | 높음 | rate limit (IP/계정당), description 유사도 검사 |
| 5 | **Denial-of-Wallet**: API 엔드포인트 대량 호출로 Cohere/OpenAI 비용 폭증 | 높음 | API Key + WAF + throttle (T3 참조) |
| 6 | **Proxy 악용**: execute_tool로 hosted MCP 서버에 악의적 파라미터 전달 | 중간 | 파라미터 validation, input_schema 기반 검증 |
| 7 | **Supabase RLS 우회**: service key 유출 시 모든 RLS 무력화 | 중간 | key rotation, 최소 권한 원칙 |

---

## 10. 최종 정리

### 가장 치명적인 리스크 (TOP 5)

| 순위 | 리스크 | 카테고리 |
|------|--------|----------|
| 1 | **T4. Observability 부재** | 운영 |
| 2 | **T2. Lambda cold start 3-5초** | 성능 |
| 3 | **T3. Rate limiting 미설정 (Denial-of-Wallet)** | 보안/비용 |
| 4 | **T1. Qdrant/Supabase 자동 정지** | 가용성 |
| 5 | **T5. Prompt Injection via description** | 보안 |

### 반드시 설계 단계에서 수정해야 하는 것

1. **SnapStart 적용** 명시 + `after_restore` 훅 설계
2. **API Gateway throttling + WAF** 설정을 IaC(SAM) 템플릿에 포함
3. **Observability stack** (X-Ray + 구조화 로깅 + CloudWatch 대시보드) 설계 추가
4. **Health check warming ping**이 Qdrant + Supabase를 실제 호출하도록 명시
5. **Qdrant 장애 시 Supabase full-text degraded mode** 설계 추가

### 추후 반드시 대비해야 하는 것 (Phase 2)

1. **Anti-spam/anti-gaming**: behavioral signal 기반 quality_score, description 유사도 검사
2. **Hybrid retrieval** (BM25 + vector): adversarial embedding 방어
3. **Online evaluation**: 실행 성공/실패 로그 기반 실제 사용자 만족도 측정
4. **Qdrant HA**: 유료 tier 업그레이드 또는 self-hosted cluster
5. **Reranker fallback 구현**: Cohere 429 시 Jina 또는 LLM fallback 자동 전환
6. **광고 투명성 원칙** 문서화: organic/sponsored 분리, 최소 relevance 게이트

### 핵심 개선 방향 요약

```
현재: "검색이 돌아가는 것"을 증명하는 MLP
목표: "검색이 안정적으로 돌아가고, 문제를 빠르게 파악할 수 있는" MLP

Gap: Observability + Rate Limiting + Cold Start + Health Check
이 4개가 해결되면 MLP는 "시연 가능한 워킹 시스템"에서
"운영 가능한 시스템"으로 한 단계 올라간다.
```
