# Proxy MCP Verification — CLAUDE.md

> **이 파일은 규칙과 참조 포인터만 둔다.** 상세 컨텍스트는 각 문서에 분리.
> 최종 업데이트: 2026-03-24

---

## 프로젝트 한줄 요약

MCP Bridge/Router 패턴 검증 프로토타입 — Python 프록시 MCP 서버가 여러 백엔드 MCP 서버의 도구를 수집·네임스페이스화하여 단일 MCP로 노출하고, Claude Code에서 E2E로 사용 가능한지 검증.

---

## 상세 컨텍스트 참조 (Lazy Loading)

필요 시 아래 파일을 Read tool로 읽을 것:

| 파일 | 내용 |
|------|------|
| `docs/metamcp-analysis.md` | MetaMCP 프록시 아키텍처 분석 (소스 코드 기반) |
| `docs/verification-report.md` | 검증 결과 보고서 (검증 완료 후 작성) |

---

## 코딩 컨벤션

### 일반 규칙
- Python 3.12, **type hints 필수**
- Pydantic v2 모델로 데이터 검증
- async/await: MCP 통신은 모두 비동기
- 환경변수: `.env` + pydantic-settings (하드코딩 금지)
- `.env` 파일은 절대 커밋하지 않음

### 테스트
- TDD: 실패 테스트 먼저 → 구현 → 통과
- pytest + pytest-asyncio
- 외부 MCP 테스트는 `@pytest.mark.skipif` 적용 (Node.js 미설치 대비)

### 네이밍
- 파일/변수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`
- 네임스페이스 구분자: `__` (예: `echo__echo`, `filesystem__read_file`)

### Git
- 커밋 메시지: `feat: ...`, `fix: ...`, `test: ...`, `docs: ...`, `refactor: ...`

---

## 실행 방법

```bash
# 의존성 설치
cd proxy_verification && uv sync --extra dev

# 테스트 실행
uv run pytest

# 프록시 서버 실행 (Claude Code 연결용)
uv run python -m src.proxy_server
```

---

## 아키텍처

```
Claude Code --stdio--> Proxy Server --stdio(subprocess)--> Echo Server (Python)
                                    --stdio(subprocess)--> Filesystem Server (Node.js)
                                    --stdio(subprocess)--> Memory Server (Node.js)
```

- 프록시의 stdin/stdout은 Claude Code 전용
- 백엔드 연결은 별도 subprocess + 별도 파이프 → 충돌 없음
- 네임스페이스: `{server_id}__{tool_name}` (MetaMCP 패턴 차용)
