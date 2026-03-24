# Verification Gate — PR 전 체크리스트

PR 생성 전, 기능 완성 후 반드시 실행. `verification-loop` 스킬의 Python/uv 적용판.

## 6단계 검증 순서

### Phase 1: Lint & Format
```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```
실패 시 즉시 수정 후 재시작. 넘어가지 않는다.

### Phase 2: Type Check (선택적)
```bash
uv run python -m mypy src/ --ignore-missing-imports
```
CRITICAL 타입 오류는 수정. 서드파티 stub 부재는 무시 가능.

### Phase 3: 테스트 + 커버리지
```bash
uv run pytest tests/ --cov=src -v
```
- 모든 테스트 PASS 필수
- 커버리지 80%+ 필수
- Integration 테스트 API 키 없으면 skip 확인

### Phase 4: 보안 스캔
```bash
grep -rn "api_key\s*=\s*['\"]" src/ tests/
grep -rn "QDRANT_API_KEY\s*=" src/
grep -rn "print(" src/
```
- 하드코딩된 시크릿 발견 시 즉시 STOP
- `print()` 발견 시 `logger.*`로 교체
- API 키, 임베딩 벡터, 전체 쿼리 payload 로그 금지

### Phase 5: diff 검토
```bash
git diff --stat
git diff HEAD
```
- 의도치 않은 변경 없는지 확인
- 디버그 로그, 임시 주석 제거 확인

### Phase 6: 실험 영향 확인 (실험 관련 변경 시)
- 변경이 E0-E7 실험 결과에 영향을 주는가?
- Ground Truth 파일이 변경되었는가?
- 영향이 있으면 실험 재실행 후 결과 기록

## 결과 포맷

```
VERIFICATION REPORT
===================
Lint:      [PASS/FAIL]
Types:     [PASS/SKIP]
Tests:     [PASS/FAIL] (X/Y passed, Z% coverage)
Security:  [PASS/FAIL]
Diff:      [X files changed]
Exp Impact:[없음 / E1 재실행 필요]

Overall:   [READY/NOT READY]
```

## 빠른 체크 (단일 파일 변경 시)

```bash
uv run ruff check src/ tests/ && uv run pytest tests/unit/ -v
```

## 금지 사항

- `--no-verify` 플래그로 훅 우회 금지
- 실패한 테스트를 skip 처리하고 머지 금지
- 커버리지 80% 미달 상태로 PR 생성 금지
