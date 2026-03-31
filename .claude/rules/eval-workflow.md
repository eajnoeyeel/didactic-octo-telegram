# Eval-Driven Development (EDD) — MCP Discovery Platform

실험(E0–E7)과 평가 하네스를 위한 공식 eval 워크플로.
`eval-harness` 스킬의 EDD 원칙을 이 프로젝트에 맞게 적용.

## 핵심 원칙

**코드 작성 전에 성공 기준을 정의한다.**
TDD에서 테스트를 먼저 쓰는 것처럼, 실험 코드를 작성하기 전에 eval을 먼저 정의한다.

## Eval 유형

### 1. Code Grader (결정론적 — 우선 사용)

```python
# pytest 테스트로 구현 — 아래는 형식 예시이며 실제 목표는 .claude/evals/ 참조
def test_e0_2layer_improvement():
    """E0 gate: 2-Layer가 1-Layer 대비 Precision@1 +5%p 이상"""
    flat = evaluate(flat_strategy, queries, ground_truth)
    seq = evaluate(sequential_strategy, queries, ground_truth)
    assert seq["precision_at_1"] - flat["precision_at_1"] >= 0.05

def test_recall_at_k_target():
    """E1 예시: Server Recall@K (K=5 for pool >50 servers)"""
    results = evaluate(strategy, queries, ground_truth)
    assert results["server_recall_at_5"] >= 0.50
```

### 2. Model Grader (LLM 판단)

복잡한 품질 평가에만 사용 (Description GEO score 등):

```python
# 명확한 루브릭 필요
RUBRIC = """
Score 1-5:
5 = 쿼리와 완벽히 매칭, 명확한 기능 설명
3 = 관련 있으나 부분적 매칭
1 = 관련 없음
"""
```

### 3. Human Grader

Ground Truth 품질 검증에만 사용. 자동화 금지.

## pass@k 기준

| 평가 유형     | 기준          | 적용               |
| ------------ | ------------- | ------------------ |
| Capability eval | pass@3 >= 0.90 | 새 실험 기능 |
| Regression eval | pass^3 = 1.00 | 기존 파이프라인 |
| 메트릭 목표 | pass@1 | Precision@1 등 단일 측정 |

## 실험별 Eval 정의 방법

실험 코드 작성 전 `.claude/evals/<experiment>.md` 작성:

```markdown
## EVAL: E1-strategy-comparison

### 성공 기준
- [ ] Sequential(A) Precision@1 측정 가능
- [ ] Parallel(B) Precision@1 측정 가능
- [ ] Taxonomy(C) Precision@1 측정 가능
- [ ] W&B에 결과 로깅

### 회귀 기준
- [ ] E0 baseline 수치 재현 (pass^3 = 1.00)
- [ ] Ground Truth 50 queries 동일하게 사용

### 메트릭 목표 (초기값, 실험 후 calibration)
- Sequential A: Precision@1 목표 설정 중
- Parallel B: Sequential 대비 개선 확인
```

## Eval 안티패턴

```python
# WRONG: 알려진 케이스에 프롬프트 오버피팅
# WRONG: 해피패스만 측정
# WRONG: 비용/지연 무시하고 pass rate만 추구
# WRONG: 불안정한 grader를 릴리즈 게이트에 사용
# WRONG: 코드 없이 eval 결과만 기록
```

## Eval 아티팩트 위치

```text
.claude/
  evals/
    E0-baseline.md          # Eval 정의
    E0-baseline.log         # 실행 이력
    E1-strategy.md
    ...
docs/
  experiments/
    E0-report.md            # 릴리즈 스냅샷
```

## Ground Truth 룰

- Seed set: 수동 큐레이션 (절대 LLM 생성 금지)
- External GT (MCP-Atlas): human-authored by Scale AI, `source=external_mcp_atlas`. `manually_verified=True` 취급
  - MCP-Atlas는 multi-step 벤치마크 (avg 4.8 tool calls/task) → **per-step single-tool GT로 분해** (ADR-0012)
  - 50~80 task 선별 → 각 substantive tool call마다 LLM으로 step-level query 생성 → Human review
  - 분해 후 모든 엔트리는 `task_type=single_step`, `correct_tool_id` 단일 사용
  - ~~`correct_tool_ids` multi-label / Hit@K 폐기~~ — granularity 불일치 문제로 ADR-0012에서 대체됨
  - `origin_task_id` + `step_index`로 원본 MCP-Atlas task 추적
  - 보일러플레이트 blocklist: `filesystem_list_allowed_directories`, `cli-mcp-server_show_security_rules`, `desktop-commander_get_config` 등
  - 서버/도구 ID 변환: `github_search_repositories` → `github::search_repositories` (첫 번째 `_` 분리)
  - query_id 네이밍: `gt-atlas-{task:03d}-s{step:02d}`
- Synthetic: LLM 생성 후 Human review 필수 — MCP-Atlas 채택으로 보조 역할로 격하
- 실험 간 동일한 GT 사용 (독립 변수 1개 원칙): MCP-Atlas per-step 분해 150~240 + self seed 80 = ~230~320개 primary (all single-step)
- 외부 GT도 동일 JSONL 포맷으로 변환 후 사용 — 형식 통일 원칙 유지
- JSONL 형식: `data/ground_truth/` (seed_set.jsonl, mcp_atlas.jsonl, synthetic.jsonl)
