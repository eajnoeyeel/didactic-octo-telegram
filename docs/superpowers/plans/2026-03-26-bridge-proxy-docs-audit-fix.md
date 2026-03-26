# Bridge/Proxy Architecture Docs Audit Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** proxy_verification 검증 결과를 docs/에 반영 — deferred.md Phase 13 stub의 잘못된 MCP SDK API 수정, persistent connection 요건 추가, ADR-0001/architecture.md에 검증 근거 보강.

**Architecture:** 문서 업데이트만. 코드 변경 없음. 3개 파일 타겟:
1. `docs/plan/deferred.md` — Task 13.2 stub 코드 오류 수정 (Critical)
2. `docs/adr/0001-bridge-mcp-server-static-2-tool-proxy.md` — 검증 evidence 추가
3. `docs/design/architecture.md` — SDK 버전, registry.py 설명, persistent connection 요건

**Tech Stack:** Markdown edits only. 코드 구현 없음.

---

## Audit Summary (검토 결과)

| 파일 | 심각도 | 문제 |
|------|--------|------|
| `docs/plan/deferred.md` Task 13.2 | 🔴 Critical | `@server.tool()` 데코레이터 없음 (MCP SDK v1.26.0) |
| `docs/plan/deferred.md` Task 13.2 | 🔴 High | persistent connection 구현 요건 없음 |
| `docs/adr/0001-...` Consequences | 🟡 Medium | 레이턴시 실측값 없음, 검증 근거 없음 |
| `docs/design/architecture.md` | 🟡 Medium | SDK 버전 `v1.7.1+` → `v1.26.0+` 불일치 |
| `docs/design/architecture.md` | 🟡 Low | `registry.py` 역할 설명 부정확 |

### 문제 없음 (변경 불필요)

- **ADR-0001 핵심 결정**: Static 2-tool proxy → ✅ proxy_verification 6/6 PASS로 입증
- **proxy-architecture-design.md**: Approach A 채택 이유, Phase 1/2/3 전략 → ✅ 호환
- **ADR-0001 trade-offs**: SPOF, latency 리스크 식별 → ✅ 올바름

---

## Task 1: deferred.md Phase 13 stub 코드 수정 (Critical)

**Files:**
- Modify: `docs/plan/deferred.md` — Task 13.2 및 Phase 13 요건 섹션

**배경:**
현재 Task 13.2 stub은 `@server.tool("find_best_tool")` 데코레이터를 사용한다.
MCP Python SDK v1.26.0에는 이 데코레이터가 없다.
검증된 실제 API:
- `@server.list_tools()` — 도구 목록 반환
- `@server.call_tool()` — 도구 호출 처리

connect-per-call 레이턴시 실측값: Echo(Python) 기준 ~2200ms, Node.js 기준 ~3300ms.
프로덕션(Phase 13)에서는 `initSessions()` 패턴의 persistent connection이 필수.

- [ ] **Step 1: Task 13.2 stub 코드 교체**

`docs/plan/deferred.md`의 Task 13.2를 아래로 교체:

```markdown
### Task 13.2: MCP Tool Server (DP1 second exposure)

**Files:**
- Create: `src/bridge/mcp_bridge.py`
- Reference: `proxy_verification/src/proxy_server.py` (재사용 가능 패턴)

**Goal**: `find_best_tool`과 `execute_tool`을 MCP Tool로 노출.
LLM이 우리 MCP Server 하나에만 연결하면 전체 Provider 카탈로그를 사용 가능.

**MCP Python SDK v1.26.0 실제 API (proxy_verification에서 검증됨):**

```python
# ✅ 검증된 import 경로 (mcp>=1.26.0)
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("mcp-discovery")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="find_best_tool",
            description="Find the best MCP tool for a given query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 3}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="execute_tool",
            description="Execute a specific MCP tool by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "tool_id": {"type": "string"},
                    "params": {"type": "object"}
                },
                "required": ["tool_id", "params"]
            }
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "find_best_tool":
        result = await pipeline.search(arguments["query"], arguments.get("top_k", 3))
        return [TextContent(type="text", text=result.model_dump_json())]
    elif name == "execute_tool":
        result = await proxy.execute(arguments["tool_id"], arguments["params"])
        return [TextContent(type="text", text=str(result))]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())
```

> **❌ 금지 패턴 (v1.26.0에 없음):**
> ```python
> @server.tool("find_best_tool")  # 이 데코레이터 존재하지 않음
> ```

**⚠️ Persistent Connection 필수 (프로토타입과 프로덕션의 차이):**

proxy_verification 실측 레이턴시:
- Connect-per-call (Python 백엔드): ~2200ms/call
- Connect-per-call (Node.js 백엔드): ~3300ms/call

프로덕션에서는 `initSessions()` 패턴으로 서버 시작 시 사전 연결 유지 필요:

```python
# registry.py — Phase 13에서 구현 (proxy_verification/src/proxy_server.py 참조)
_sessions: dict[str, ClientSession] = {}  # 세션 풀

async def init_sessions(config: RegistryConfig) -> None:
    """서버 시작 시 모든 Provider MCP에 사전 연결"""
    for server_id, params in config.backends.items():
        _sessions[server_id] = await _connect(params)

async def get_session(server_id: str) -> ClientSession:
    """캐시 히트 시 재사용, 미스 시 재연결 (3회 재시도 + 2.5s 간격)"""
    if server_id not in _sessions:
        _sessions[server_id] = await _connect_with_retry(server_id)
    return _sessions[server_id]
```

**재사용 가능 패턴**: `proxy_verification/src/` 코드를 `src/bridge/`로 이식 가능.
- `proxy_verification/src/proxy_server.py` → `src/bridge/mcp_bridge.py` (라우팅 로직)
- `proxy_verification/src/registry.py` → `src/bridge/registry.py` (tool→client 매핑)
```

- [ ] **Step 2: verify_ground_truth.py 스크립트와 동일하게 proxy 참조 추가**

`docs/plan/deferred.md`의 Phase 13 Gate 조건 업데이트:

현재:
```
> **Gate**: Do NOT start this phase until (a) Phases 0–12 are passing, AND (b) CTO mentoring on 2026-03-25 has confirmed Strategy C viability and MCP Tool server design.
```

변경 후:
```
> **Gate**: Do NOT start this phase until (a) Phases 0–12 are passing, AND (b) CTO mentoring on 2026-03-25 has confirmed Strategy C viability and MCP Tool server design.
>
> **Pre-implementation reference**: `proxy_verification/docs/verification-report.md` — E2E 검증 완료 (6/6 PASS, 2026-03-22). MCP SDK import 경로, 도구 발견 패턴, 에러 전파 패턴, pytest-asyncio 호환성 이슈 해결책 포함.
```

- [ ] **Step 3: "SEO 점수 방식 미결" 섹션 업데이트 (이전 세션 leftover)**

`docs/plan/deferred.md`에 Design Discussion Log 섹션에 SEO → GEO 업데이트:

현재 line 109-111:
```
### SEO 점수 방식 미결

정규식 휴리스틱 방식의 한계 확인. 논문 리서치 후 LLM-based 방식과 비교 실험 예정. 핵심 테제(Spearman 상관계수)의 유효성이 SEO 점수 품질에 달려 있음. `mentoring/open-questions.md` — OQ-1 참고.
```

변경 후:
```
### GEO 점수 방식 미결 (→ OQ-1 RESOLVED)

정규식 휴리스틱 방식의 한계 확인. GEO 논문(Aggarwal et al., ACM SIGKDD 2024) 리서치 후 LLM-based 방식과 비교 실험 예정. 핵심 테제(Spearman 상관계수)의 유효성이 GEO 점수 품질에 달려 있음.
OQ-1 RESOLVED (2026-03-26): SEO Score → GEO Score (6-dimension). 상세: `docs/design/metrics-rubric.md` — GEO Score 섹션.
```

---

## Task 2: ADR-0001에 검증 evidence 추가

**Files:**
- Modify: `docs/adr/0001-bridge-mcp-server-static-2-tool-proxy.md`

**배경:**
ADR은 설계 결정의 근거를 담는 문서다.
proxy_verification이 이 결정의 타당성을 실증했으나 ADR에 반영되지 않았다.
레이턴시 Consequences 항목도 실측값 없이 막연하다.

- [ ] **Step 1: Consequences의 Risks 섹션 업데이트**

현재:
```
### Risks
- Bridge 지연이 E2E 레이턴시에 직접 영향 → 파이프라인 최적화 필요
```

변경 후:
```
### Risks
- Bridge 지연이 E2E 레이턴시에 직접 영향 → 파이프라인 최적화 필요
  - **실측 (proxy_verification, 2026-03-22)**: connect-per-call 기준 Python 백엔드 ~2200ms, Node.js 백엔드 ~3300ms
  - **프로덕션 완화**: persistent connections (`initSessions()` 패턴) 필수 — 세션 풀 유지로 cold start 제거
```

- [ ] **Step 2: 검증 결과 섹션 추가**

ADR 끝에 추가:

```markdown
## Validation

**proxy_verification (2026-03-22)**: Python 프록시 MCP 서버 구현으로 E2E 검증 완료.

| 검증 항목 | 결과 |
|-----------|------|
| Python → Python stdio 프록시 | ✅ PASS |
| Python → Node.js 크로스 언어 프록시 | ✅ PASS |
| 다중 백엔드 네임스페이스 집약 | ✅ PASS |
| `__` 구분자 MCP SDK 호환성 | ✅ PASS |
| 에러 전파 (백엔드 부재 시 graceful degradation) | ✅ PASS |
| 상태 있는 백엔드 라운드트립 | ✅ PASS |

상세: `proxy_verification/docs/verification-report.md`
```

---

## Task 3: architecture.md bridge 섹션 업데이트

**Files:**
- Modify: `docs/design/architecture.md`

**배경:**
기술 스택 테이블에 MCP SDK 버전이 `v1.7.1+`로 표기되어 있으나
검증 환경 및 실제 동작은 v1.26.0 기준 (API 변경됨).
`registry.py` 역할 설명도 실제 구현과 다르다.

- [ ] **Step 1: 기술 스택에 MCP SDK 버전 수정**

현재 (없음 — 기술 스택 테이블에 MCP SDK 항목 없음):
```
| Bridge/Router 구현 참조 | `mcp` (PyPI v1.7.1+), `fastmcp`, MetaMCP, mcp-bridge |
```
(architecture.md line 58에 이 텍스트가 있음)

변경 후:
```
- 기술 참조: `mcp>=1.26.0` (PyPI, `Server`/`ClientSession` API), MetaMCP 패턴 참조
  - ⚠️ v1.26.0+ 기준: `@server.list_tools()` / `@server.call_tool()` 데코레이터 사용
  - v1.7.x와 API 다름 — import 경로는 `proxy_verification/docs/verification-report.md` 3.1절 참조
```

- [ ] **Step 2: registry.py 역할 설명 수정**

현재 (architecture.md 모듈 트리):
```
│   └── registry.py        # Provider MCP endpoint cache
```

변경 후:
```
│   └── registry.py        # tool_id → ClientSession 매핑 + 세션 풀 관리 (persistent connections)
```

- [ ] **Step 3: bridge 섹션에 persistent connection 요건 추가**

Bridge/Router 섹션 끝에 추가:
```markdown
> **⚠️ Persistent Connection (Phase 13 구현 시 필수)**:
> proxy_verification에서 connect-per-call 레이턴시 2200~3300ms 측정.
> 프로덕션에서는 `registry.py`가 `initSessions()`로 시작 시 백엔드에 사전 연결 유지.
> 패턴: `proxy_verification/docs/verification-report.md` 4절 참조.
```

---

## Self-Review

**Spec Coverage 체크:**
- [x] deferred.md Task 13.2 wrong API → Task 1에서 수정
- [x] persistent connection 요건 누락 → Task 1 Step 1, Task 3 Step 3에서 추가
- [x] ADR-0001 레이턴시 실측값 누락 → Task 2 Step 1에서 추가
- [x] ADR-0001 검증 근거 없음 → Task 2 Step 2에서 추가
- [x] architecture.md SDK 버전 불일치 → Task 3 Step 1에서 수정
- [x] registry.py 설명 부정확 → Task 3 Step 2에서 수정

**변경 불필요 (audit에서 Valid 판정):**
- ADR-0001 핵심 결정 (Static 2-tool proxy)
- proxy-architecture-design.md 전체 내용
- deferred.md Task 13.1 (Taxonomy-gated stub)
- deferred.md Task 13.3 (A/B Test Qdrant swap)

**Placeholder 검사:** 없음. 모든 코드/텍스트 블록이 실제 내용.

**Type consistency:** 문서 업데이트만이므로 해당 없음.
