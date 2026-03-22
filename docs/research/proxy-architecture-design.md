# Proxy 아키텍처 설계 옵션 분석

> 최종 업데이트: 2026-03-22
> 조사 목적: LLM ↔ MCP Provider 사이 Proxy 여부 및 방식 결정

---

## 해결하려는 기능/문제

**Prompt Bloating** — LLM이 여러 MCP 서버에 연결되면, 각 서버의 모든 툴 정의가 컨텍스트에 올라간다.

```
서버 10개 × 툴 평균 20개 × 툴 정의 300토큰 = 60,000토큰
→ 비용 ↑, LLM 추론 품질 ↓
```

**목표**: LLM이 수천 개 MCP 툴 중 최적의 툴을 찾되, 컨텍스트는 최소로 유지한다.

---

## MCP 프로토콜 내부 동작 이해

### 기본 흐름

```
┌─────────┐      ┌────────────┐      ┌────────────┐
│   LLM   │ ←──→ │ MCP Client │ ←──→ │ MCP Server │
│(Claude) │      │(Claude App,│      │(GitHub MCP,│
│         │      │Cursor, etc)│      │ Slack MCP) │
└─────────┘      └────────────┘      └────────────┘
```

### 연결 시점 (앱 시작 시 한 번)

```
MCP Client → MCP Server: tools/list 요청
MCP Server → MCP Client: 툴 정의 목록 반환
MCP Client → LLM: 툴 정의를 시스템 프롬프트에 삽입
```

### 대화 중 (툴 사용할 때마다)

```
사용자: "GitHub 이슈 찾아줘"
LLM: search_issues 툴 호출 결정
MCP Client → MCP Server: tools/call (search_issues, params)
MCP Server: GitHub API 호출 → 결과 반환
MCP Client → LLM: 결과 전달
```

### 핵심 제약

- `tools/call`은 **연결된 서버에만** 보낼 수 있다
- MCP에는 "저 다른 서버에 연결해"라는 프로토콜 메시지가 없다
- `notifications/tools/list_changed`: 서버→클라이언트 "내 툴 목록 바꼈어" 알림 (선택적)
- `tools/list`는 프로토콜상 강제가 아니지만, 현재 모든 MCP Client 구현체가 연결 즉시 자동 호출

---

## 검토한 논문/자료 목록

| 자료 | 파일 | 핵심 기여 |
|------|------|-----------|
| MCP 프로토콜 스펙 | — | `tools/list`, `tools/call`, `notifications/tools/list_changed` 동작 정의 |
| MetaMCP 프로젝트 | — | 유저가 Proxy에 크리덴셜 등록하는 방식의 실제 구현 사례 |

---

## 각 자료에서 가져온 핵심 포인트

- **MCP 프로토콜 스펙**: `tools/call`은 이미 연결된 서버에만 보낼 수 있으며, "다른 서버에 직접 연결해"라는 메시지는 프로토콜에 존재하지 않는다. 이 제약이 Proxy 구조를 강제한다.
- **MetaMCP**: 유저가 각 서비스 토큰을 Proxy 설정에 저장하는 방식. 간단하지만 Proxy가 크리덴셜 저장소가 된다. Phase 2 참고용.

---

## 후보 접근 방식 비교

| 전략 | 방법 | Prompt Bloating | MCP Client 호환성 | 구현 복잡도 | Analytics 로깅 | 비고 |
|------|------|-----------------|-------------------|-------------|----------------|------|
| **A: Static 2-Tool Proxy** | `find_best_tool` + `call_tool` 2개 고정 노출 | 완전 해결 (2툴) | 모든 클라이언트 지원 | 낮음 | call_tool 단일 병목으로 100% 로깅 | — |
| **B: Dynamic Tool Injection** | `notifications/tools/list_changed`로 동적 노출 | 해결 | Client 구현마다 다름 | 중간 | 가능 | 인증 구조는 A와 동일 |
| **C: Single Composite Tool** | `execute(query, context)` 1개로 발견+실행 | 최소 (1툴) | 모든 클라이언트 지원 | 높음 | 가능 | 파라미터 자동 추출 불안정 |

### 접근 A: Static 2-Tool Proxy

LLM에게 항상 고정된 2개 툴만 노출:

```
1. find_best_tool(query) → 추천 결과 + schema 반환
2. call_tool(tool_id, params) → 실제 실행 포워딩
```

Confidence 분기 (DP6): gap 큼 → Top-1 반환, gap 작음 → Top-3 + disambiguation hint 반환.

### 접근 B: Dynamic Tool Injection

`notifications/tools/list_changed` 활용. 초기 1개 → 검색 후 해당 툴을 동적 추가. 단, Client 호환성 리스크 있고 인증 구조는 A와 동일.

### 접근 C: Single Composite Tool

자연어 → 구조화된 파라미터 변환이 불안정. 툴마다 파라미터 이름이 다르며(`channel` vs `channelName` vs `ch`), 서버 측 LLM 또는 복잡한 NLP가 추가로 필요.

---

## 채택안 / 제외안

**채택: 접근 A (Static 2-Tool Proxy)**

**제외:**
- **접근 B**: Client 호환성 불확실 + 인증 이점 없음 → 복잡도 대비 이득 없음
- **접근 C**: 파라미터 자동 추출 정확도 문제 → 신뢰성 확보 어려움

---

## 판단 근거

1. **모든 MCP Client에서 동작** — 호환성 리스크 제거
2. **call_tool 단일 병목** — 모든 호출이 여기를 통과하므로 Provider Analytics 로깅이 자연스럽게 완성
3. **CTO 설명 용이** — "툴 2개, 역할 명확" — 트레이드오프 명확
4. **기존 DP1 확장** — `find_best_tool` 설계에 `call_tool` 추가 → 추천에서 Proxy로 격상
5. **내부 파이프라인 은닉** — LLM은 2개 툴만 인지, 내부적으로 2-Layer + Reranker + Confidence 분기 동작

---

## 프로젝트 반영 방식

### 인증/인가 Phase별 전략

| Phase | 전략 | 설명 |
|-------|------|------|
| **Phase 1 (MVP)** | Public 서버만 | 자체 제작 MCP 서버 (mcp-arxiv, mcp-calculator 등). 인증 문제 우회, 추천 파이프라인 + Analytics에 집중 |
| **Phase 2** | 로컬 Proxy + 유저 크리덴셜 | MetaMCP 방식: config 파일에 토큰 저장. 크리덴셜 유저 로컬 보관 → 보안 부담 최소 |
| **Phase 3 (미래)** | OAuth 중개 | 현재 프로젝트 범위 밖 |

### 코드/설계 반영

- Discovery Proxy는 MCP Server로 구현 → `find_best_tool`, `call_tool` 두 툴 노출
- `call_tool` 내부에서 백엔드 MCP Server로 `tools/call` 포워딩
- 모든 `call_tool` 호출에 대해 Analytics 이벤트 자동 기록

### 미래 가능성

현재 MCP 프로토콜 한계:
- 서버가 클라이언트에게 "다른 서버에 연결해"를 시킬 수 없음
- "Lazy Tool Loading" (연결은 하되 툴을 컨텍스트에 미로드)이 표준에 없음

이 gap이 해결되면: Client가 Discovery 추천 시 해당 서버 툴만 로드 + 직접 연결 → 인증은 Client 담당, Prompt Bloating 해결 → 더 자연스러운 구조 가능

---

## 관련 papers

- (직접 참조 논문 없음 — MCP 프로토콜 스펙 및 MetaMCP 오픈소스 프로젝트를 근거로 작성)
