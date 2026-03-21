# MCP 추천 최적화 프로젝트 — Claude Code Handoff Document

> **⚠️ 이 문서는 2026-03-16 시점의 원본 핸드오프 문서입니다.**
> **최신 결정 사항 → `docs/discovery/brainstorm_ideas.md`**
> **평가 체계 → `docs/evaluation/metrics-rubric.md`**
> **구현 계획 → `docs/superpowers/plans/2026-03-18-mcp-discovery-platform.md`**
> DP1~DP9는 이후 세션에서 대부분 확정되었습니다. 아래 내용은 CTO 원문 발언, 과제 원문 등 1차 자료로서 보존합니다.
>
> 원본 작성: 2026-03-16

---

## 1. 프로젝트 개요

### 한 줄 정의
MCP 생태계의 양면 플랫폼: LLM/Agent에게는 쿼리 기반 자동 추천을, MCP Provider에게는 메타정보 분석/최적화 가이드를 제공하며, 두 고객의 피드백 루프가 서로를 강화하는 시스템.

### 배경
- 인포뱅크 채용 연계 프로젝트 (42Seoul)
- 평가자: 강진범 CTO (iLab)
- 기간: 약 5주 (프로젝트 OT 후 시작)
- 레퍼런스 서비스: Smithery (https://smithery.ai) — MCP 오픈 마켓플레이스, 2,880개+ MCP 등록

### 과제 원문 (4개 항목)
1. LLM의 MCP 선택 기준 정의 및 평가 지표, 테스트 체계 구축
2. MCP 차별화 설계 및 노출, 추천 최적화
3. 실제 사용 로그 기반 성능 측정, 테스트, 피드백 루프 통해 지속 개선
4. 등록-배포-버전관리-호환성 검증까지 운영/배포 자동화 및 품질 게이트 구축

### CTO 핵심 발언 (Transcript에서 추출)
- "메타 정보가 어떻게 최적화를 해야 **내 MCP가 잘 콜링될 수 있느냐**"
- "LLM이 어떻게 불려진지를 **모니터링**을 해서 그걸 기반으로 **메타 정보를 개선**"
- "MCP가 100개가 있는데, 내가 만든 MCP를 더 잘 부르고 더 많이 쓸 수 있게끔 **어떻게 시스템적으로 제공**할 것이냐"

### CTO 평가 기준 (4축)
1. **엔지니어링 판단력**: 완벽한 솔루션보다 "나만의 논리와 스토리". 트레이드오프를 설명할 수 있어야 함
2. **서버리스/비용 최적화**: AWS Lambda, Step Functions, boto3 직접 언급. 비용을 제로에 가깝게 유지하는 구조
3. **LLM 통제력**: LLM을 써도 되지만 코드 리뷰 때 그 코드를 설명할 수 있어야 함
4. **비즈니스 임팩트**: BM 캔버스, 고객 세그먼트를 이해하는 개발자

---

## 2. 확정된 결정 사항

### DP0: 프로젝트 범위 — 확정 (Option C)

**결정**: Discovery 추천 + Description 최적화, 둘 다. 극한 완성도 추구. 범위 축소 non-negotiable.

**고객 2종류**:
- **고객 1 (LLM/Agent)**: `find_best_tool(query)` → 수천 개 MCP 중 best tool 반환
- **고객 2 (MCP Provider)**: 자기 MCP를 등록하고, 선택률을 높이기 위한 분석/가이드 도구

**핵심 구조**: 하나의 추천 파이프라인에서 두 개의 출구
```
쿼리 → 임베딩 → 벡터 검색 → Reranking → Confidence 분기
                                              │
                             ┌────────────────┴────────────────┐
                             ▼                                 ▼
                     [고객 1: LLM]                      [고객 2: Provider]
                     best tool 반환                         분석 대시보드
                                                     description 개선 가이드
```

**두 목적 함수의 관계**: "Tool Selection 정확도 최대화"와 "내 MCP 선택 빈도 최대화"는 정직하게 하면 수렴함. 메커니즘은 동일하고 산출물 형태만 다름.

### Provider 쪽 필수 기능 4가지 (CTO 요구사항 + Smithery 제공 기능)

```
1. Distribution — MCP Provider가 서버를 등록하고, 사용자가 발견/설치할 수 있는 페이지
2. Analytics — Tool call 추적, 사용 패턴 모니터링, 추천 순위/점수/Confusion 분석
3. Spec Compliance — MCP 프로토콜 준수 검증, 메타데이터 enrichment, 캐싱
4. OAuth UI — 인증이 필요한 서버용 자동 인증 모달 생성
```

**깊이 분배**:
- 극한의 깊이: 추천 파이프라인 + Analytics (Provider 분석 포함)
- 높은 완성도: Distribution (등록 + 품질 피드백)
- 견고한 구현: Spec Compliance (검증 + 품질 게이트)
- 동작하는 수준: OAuth UI (인증 플로우)

---

## 3. 미결정 Decision Points (DP1 ~ DP9)

아래 DP들은 아직 옵션 분석/확정이 안 된 상태. 순서대로 분석 필요.

### DP1: 추천 시스템 노출 방식
**옵션들**:
- A: MCP Tool — `find_best_tool`을 MCP Tool로 노출. LLM이 자발적으로 호출. MCP 프로토콜 준수.
- B: Client-side 미들웨어 — Agent 코드 내부에 추천 로직. 구현 단순, 범용성 낮음.
- C: REST API — HTTP 엔드포인트. 어떤 클라이언트든 사용 가능. MCP 생태계와 분리.
- D: 이중 노출 — 내부 파이프라인은 동일, REST + MCP Tool 인터페이스 둘 다 제공.

**주의**: DP0에서 Provider 쪽 기능 (Distribution, Analytics)이 포함되면서, Provider 대시보드는 REST API 기반이 자연스러움. 따라서 LLM 쪽과 Provider 쪽의 인터페이스가 다를 수 있음.

**이전 대화에서의 논의**: Method 1 (MCP Tool)이 가장 유력했음. MCP 프로토콜을 벗어나지 않고, LLM이 자연스럽게 의도를 전달하며, 기존 설계한 모든 것이 그대로 적용되기 때문. 하지만 Provider 쪽 기능이 추가되면서 재검토 필요.

### DP2: 추천 대상 단위
**옵션들**:
- A: MCP 서버 단위 — "어떤 MCP 서버를 연결할지" 추천. Smithery 레지스트리 레벨.
- B: Tool 단위 — "이미 연결된 서버들의 Tool 중 어떤 걸 호출할지" 추천.
- C: 2-Layer — 서버 추천 → Tool 추천 2단계. 가장 완전하지만 복잡도 높음.

**이전 대화에서의 논의**: CTO 원문의 "MCP"가 서버인지 Tool인지 모호. 양쪽 다 description이 있고 매칭 메커니즘은 동일. 둘 다 커버하는 것이 가장 안전하다는 결론이었으나 확정은 안 됨.

### DP3: Stage 1 검색 전략
**옵션들**:
- A: Dense Vector 검색 (Bi-Encoder) — 시맨틱 이해 강, 키워드 매칭 약할 수 있음
- B: Sparse/키워드 검색 (BM25) — 키워드 매칭 강, 의미적 유사성 못 잡음
- C: 하이브리드 — Dense + Sparse 결합. 가장 robust, 구현/튜닝 복잡

### DP4: 임베딩 모델 선택
**옵션들**:
- A: OpenAI text-embedding-3-small — 성능 검증됨, API 비용, 서버리스 친화적
- B: 오픈소스 (sentence-transformers) — 비용 0, Cold Start 이슈, 모델 로딩
- C: 도메인 파인튜닝 — MCP description 특화. 잠재적 최고 정확도, 학습 시간 필요

### DP5: Stage 2 Reranker 전략
**옵션들**:
- A: Cross-Encoder — 경량, 빠름, 비용 0. 정확도는 LLM보다 낮을 수 있음
- B: LLM-as-Judge — 정확도 높지만 API 비용, latency 증가
- C: Rule-based — 가장 빠르고 저렴, 유연성 낮음
- D: 하이브리드 — Cross-Encoder 먼저, 확신 낮으면 LLM fallback

### DP6: Confidence 분기 정책
**옵션들**:
- A: 항상 단일 추천 (Top-1)
- B: 항상 Top-K (2~3개 + disambiguation hint)
- C: Confidence 기반 분기 — 높은 확신 → 1개, 낮은 확신 → 2~3개
- D: Confidence + fallback — 확신 낮으면 "사용자에게 물어보세요" 지시 포함

### DP7: 데이터 소스 전략
**옵션들**:
- A: Smithery API/크롤링 — 실제 데이터 2,880개+, API 제한 리스크
- B: MCP 서버 직접 연결 — `tools/list` 실시간 수집, 시간/비용
- C: 수동 큐레이션 — 핵심 50~100개 직접 선별, 규모 제한
- D: 하이브리드 — Smithery 대량 수집 + 핵심 세트 수동 검증

### DP8: 배포 아키텍처
**옵션들**:
- A: AWS Lambda + API Gateway — CTO 직접 언급, 비용 ≈0, Cold Start
- B: 컨테이너 (ECS/Fargate) — 모델 로딩 이슈 없음, Always-on 비용
- C: 하이브리드 — API는 Lambda, 모델 서빙은 SageMaker/EC2
- D: 로컬 MVP 먼저 — FastAPI로 동작 확인 후 배포

### DP9: 평가 방법론
**옵션들**:
- A: 오프라인 벤치마크 — Ground Truth 테스트 케이스 + 자동 측정
- B: 실사용 로그 분석 — 가장 현실적, 사용자 확보 필요
- C: LLM-as-Evaluator — Ground Truth 없이 가능, evaluator bias
- D: A/B 테스트 — Description 변형별 성능 비교 (과제에서 명시적 요구)

---

## 4. 아키텍처 설계 결정에서의 주요 교훈 / 제약 조건

### MCP 프로토콜 제약 (이전 대화에서 발견)
- `tools/list`는 쿼리 파라미터가 없음. 항상 전체 Tool 목록 반환.
- MCP에는 "이 쿼리에 관련된 Tool만 골라서 줘"라는 필터링 메커니즘이 없음.
- 이것이 "Tool Discovery Problem"이며, 이 프로젝트가 해결하려는 핵심 문제.
- 추천 시스템 자체를 MCP Tool로 노출하는 것 (Method 1)이 프로토콜을 벗어나지 않는 해결책.

### 용어 정리
- `tools/list`: 단일 MCP 서버 내부의 Tool 목록을 반환하는 엔드포인트. 서버 목록이 아님.
- MCP 서버: Semantic Scholar, Brave Search 같은 서비스 단위
- Tool: MCP 서버 안의 개별 기능 (search_papers, get_citations 등)
- 레지스트리: MCP 서버들의 목록을 관리하는 곳 (Smithery가 현재 가장 큰 오픈 레지스트리)

### 선행 연구
- RAG-MCP 논문: dense vector retrieval로 MCP 레지스트리에서 Top-K Tool을 동적으로 가져옴. 프롬프트 크기 50%+ 감소, Tool 선택 정확도 3배 향상 (약 43% vs baseline).
- "MCP Search Engine" 글, "Solving the MCP Tool Discovery Problem" 글 — 본 프로젝트와 거의 동일한 비전.
- MCP Gateway & Registry 개념 — 에이전트가 자연어로 레지스트리에 쿼리하는 구조.

---

## 5. 이전에 설계한 구성 요소 (V2.1 계획서 기반)

### 2-Stage 파이프라인
- Stage 1: Bi-Encoder 벡터 검색 → Top-K 후보 (K=10 정도)
- Stage 2: Cross-Encoder Reranking → Top-1 (or Top-N with confidence)
- Confidence 기반 응답: 높은 확신 → 1개, 낮은 확신 → 2~3개 + disambiguation

### 메트릭 체계
- **Stage 1**: Recall@K (정답이 Top-K 안에 포함되는 비율)
- **Stage 2**: Precision@1 (최종 추천이 정답인 비율), Confusion Rate (유사 Tool 간 오선택)
- **End-to-end**: 비용 대비 정확도 (Cost per Correct Selection)
- **Provider 쪽**: Description Quality Score, 선택률, 유사 Tool 대비 차별화 점수

### 통제 변인 실험 설계
- Pool Size: 10 / 30 / 50 / 100개
- Similarity Density: 유사 Tool 비율 0% / 20% / 50%
- Description 품질: vague / moderate / specific
- 쿼리 모호도: 명시적 / 모호 / 매우 모호
- 모델 종류: Claude Sonnet / Haiku / GPT-4o / Llama 3 등

### 비즈니스 연결
- in7 서비스: 멀티 LLM + RAG 기반 업무 보조 서비스 (종량제)
- MCP 생태계 확장 시 추천 레이어가 필수 인프라
- 비용 스토리: "정확도 X% 포기하면 비용 100배 절감" 트레이드오프

---

## 6. 남은 작업 (Claude Code에서 이어갈 것)

### 즉시 다음 단계
1. DP1 ~ DP9 순차 분석 및 확정
2. DP1은 특히 Provider 쪽 4가지 기능 (Distribution, Analytics, Spec Compliance, OAuth UI)이 포함되면서 재검토 필요

### 이후 단계
3. 확정된 DP 기반으로 구현 스펙 작성
4. Superpowers의 brainstorming → writing-plans → execute 워크플로우로 구현 진행
5. 4일 학습 플랜 병행 (MCP 스펙 읽기 + 프로토타입)

---

## 7. 참고 리소스

- Smithery: https://smithery.ai
- MCP 공식 Spec: https://modelcontextprotocol.io/specification
- Anthropic Tool Use 문서: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
- RAG-MCP 논문: 검색 필요
- MCP Search Engine 글: epicai.pro
- A2A Protocol: https://google.github.io/A2A/
- sentence-transformers: https://www.sbert.net/
- FAISS: https://github.com/facebookresearch/faiss/wiki