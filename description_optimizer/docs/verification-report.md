# Description Optimizer — Verification Report

> Date: 2026-03-28
> Branch: `feat/description-optimizer`
> Verifier: Claude (자동 검증) + 수동 리뷰 가이드

> **최신 업데이트 (2026-03-30):** Phase 2 이후 boundary→fluency 교체, GEO가 diagnostic metric으로 전환, Quality Gate가 4-gate(GEO 비회귀 제외)로 변경됨. 이 문서의 검증 결과는 Phase 1 기준이며, 아래 내용은 해당 시점에서 유효합니다.

---

## 자동 검증 결과

### Test Summary

| Suite | Count | Pass | Fail |
|-------|-------|------|------|
| Unit — models | 11 | 11 | 0 |
| Unit — heuristic analyzer | 16 | 16 | 0 |
| Unit — llm optimizer | 7 | 7 | 0 |
| Unit — quality gate | 8 | 8 | 0 |
| Unit — pipeline | 10 | 10 | 0 |
| Evaluation | 4 | 4 | 0 |
| Integration | 2 | 2 | 0 |
| **Verification — heuristic edge cases** | **19** | **19** | **0** |
| **Verification — quality gate boundaries** | **13** | **13** | **0** |
| **Verification — LLM optimizer robustness** | **11** | **11** | **0** |
| **Verification — pipeline error paths** | **11** | **11** | **0** |
| **Verification — GEO calibration** | **11** | **11** | **0** |
| **Total** | **123** | **123** | **0** |

### Coverage

```
Name                                             Stmts   Miss  Cover   Missing
--------------------------------------------------------------------------------
src/description_optimizer/__init__.py                0      0   100%
src/description_optimizer/analyzer/__init__.py       3      0   100%
src/description_optimizer/analyzer/base.py           5      0   100%
src/description_optimizer/analyzer/heuristic.py    132      3    98%   241-242, 267
src/description_optimizer/models.py                 40      1    98%   33
src/description_optimizer/optimizer/__init__.py       0      0   100%
src/description_optimizer/optimizer/base.py          5      0   100%
src/description_optimizer/optimizer/llm_optimizer.py 28      0   100%
src/description_optimizer/optimizer/prompts.py      13      0   100%
src/description_optimizer/pipeline.py               42      0   100%
src/description_optimizer/quality_gate.py           46      0   100%
--------------------------------------------------------------------------------
TOTAL                                              314      4    99%
```

### Lint

```
ruff check: All checks passed
ruff format: No changes needed
```

### 발견된 이슈

| # | 이슈 | 심각도 | 상태 |
|---|------|--------|------|
| 1 | Pipeline에서 embedder 에러 미처리 — embedder 실패 시 batch 전체 중단 | Medium | 확인됨 (의도적 설계) |
| 2 | `test_pipeline_error_paths.py` E501 docstring 초과 | Low | 수정 완료 |

### 검증 커버리지 매핑

| 컴포넌트 | 정상 경로 | 엣지케이스 | 에러 경로 | 캘리브레이션 |
|----------|----------|-----------|----------|------------|
| HeuristicAnalyzer | Unit 16 | Verification 19 | - | Calibration 11 |
| LLMDescriptionOptimizer | Unit 7 | Robustness 11 | Robustness 2 | - |
| QualityGate | Unit 8 | Boundary 13 | - | - |
| OptimizationPipeline | Unit 10 | Error paths 11 | Error paths 3 | - |
| Integration (E2E) | Integration 2 | - | - | Evaluation 4 |

### GEO Score 캘리브레이션 결과

실제 MCP description 샘플로 측정한 GEO score 분포:

| Tier | Description | GEO Score |
|------|------------|-----------|
| Poor | "Search stuff" | 0.025 |
| Poor | "Read a file" | 0.025 |
| Poor | "Run command" | 0.025 |
| Medium | GitHub repos search (2문장) | 0.108 |
| Medium | Slack send message (3문장) | 0.125 |
| Good | PostgreSQL run_query (풍부한 설명) | 0.583 |
| Good | GitHub search_issues (풍부한 설명) | 0.467 |

**관찰**: poor < medium < good 순서 유지. medium tier의 GEO가 예상보다 낮음 (0.1 수준). **주의:** GEO Score는 retrieval 성능(P@1)과 직접 상관하지 않으므로, 이 캘리브레이션은 description 품질 진단 참고용이지 검색 성능 예측 지표가 아님.

---

## 수동 리뷰 가이드

### 리뷰 1: GEO 점수 캘리브레이션 직접 확인

실제 서버 데이터로 GEO 점수가 직관에 부합하는지 확인합니다.

**실행:**
```bash
uv run python -c "
import asyncio
from description_optimizer.analyzer.heuristic import HeuristicAnalyzer

async def main():
    analyzer = HeuristicAnalyzer()
    samples = [
        ('poor', 'generic::search', 'Search stuff'),
        ('poor', 'generic::read', 'Read a file'),
        ('medium', 'github::search_repos', 'Search for GitHub repositories matching a query. Returns repository name, URL, description, star count, and language.'),
        ('good', 'postgres::run_query', 'Executes read-only SQL queries against a PostgreSQL database via the wire protocol. Use when you need to retrieve structured data. Supports JSON, JSONB, and ARRAY column types. Cannot execute DDL or DML statements. Query timeout: 30 seconds. Maximum result size: 10,000 rows.'),
    ]
    for tier, tid, desc in samples:
        report = await analyzer.analyze(tid, desc)
        print(f'[{tier:6s}] {tid:30s} GEO={report.geo_score:.3f}')
        for ds in report.dimension_scores:
            print(f'         {ds.dimension:25s} {ds.score:.2f}  {ds.explanation}')
        print()

asyncio.run(main())
"
```

**확인 포인트:**
- [ ] poor 설명은 GEO < 0.25인가?
- [ ] good 설명은 GEO > 0.45인가?
- [ ] 각 차원 점수가 설명 내용과 직관적으로 매치되는가?
- [ ] precision 차원에서 기술 용어가 있는 설명이 높은 점수를 받는가?
- [x] ~~boundary 차원~~ — 제거됨 (2026-03-29). fluency 차원으로 교체.

---

### 리뷰 2: LLM 프롬프트 품질 검토

`src/description_optimizer/optimizer/prompts.py`를 직접 읽고 검토합니다.

**확인 포인트:**
- [ ] SYSTEM_PROMPT가 사실 보존 규칙을 명시하고 있는가? (Line 14: "PRESERVE all factual information")
- [ ] 차원별 가이던스가 충분히 구체적인가? (Lines 43-49)
- [ ] word limit이 적절한가? (optimized: 50-200, search: 30-80)
- [ ] JSON 출력 포맷 지시가 명확한가?
- [ ] 프롬프트에 주입 취약점이 없는가? (tool_id, description이 escape 없이 삽입됨)

---

### 리뷰 3: Quality Gate 임계값 타당성

**확인 포인트:**
- [ ] `min_similarity=0.85` — embedding cosine similarity 85%가 의미 보존에 충분히 엄격한가?
  - 참고: 같은 주제의 다른 문장은 보통 0.7-0.85, 패러프레이즈는 0.85-0.95
  - 너무 낮으면: 의미가 바뀐 설명도 통과
  - 너무 높으면: 개선된 설명도 거부
- [ ] `skip_threshold=0.75` — GEO 0.75 이상이면 이미 충분히 좋은가?
  - 참고: 현재 heuristic에서 0.75+ 받으려면 최소 4-5개 차원에서 높은 점수 필요
- [x] `allow_geo_decrease` — GEO는 diagnostic metric으로 전환됨. GEO 비회귀 gate는 제거 대상.

---

### 리뷰 4: Pipeline 안전성

`src/description_optimizer/pipeline.py`를 읽고 검토합니다.

**확인 포인트:**
- [ ] Line 42: `desc = description or ""` — None 처리가 적절한가?
- [ ] Lines 68-81: optimizer 에러 catch — 모든 Exception을 잡는 것이 적절한가?
- [ ] Lines 90-91: embedder 에러는 catch되지 않음 — 이것이 의도적인가?
  - embedder 실패 시 전체 pipeline이 죽음 → batch 중 한 tool 실패하면 나머지도 처리 안 됨
- [ ] Lines 98-107: gate rejection 시 original 보존 — search_description도 original로 설정하는 것이 맞는가?
- [ ] Line 134: `run_batch`가 sequential — 대규모 tool pool에서 성능 이슈 없는가?

---

### 리뷰 5: 데이터 모델 견고성

`src/description_optimizer/models.py`를 읽고 검토합니다.

**확인 포인트:**
- [ ] Line 26: `Field(ge=0.0, le=1.0)` — 점수 범위가 적절한가?
- [ ] Lines 44-49: 6개 차원 전부 필수 — 부분 분석 허용 여부?
- [ ] Line 56: `geo_score` = 균등 가중 평균 — 차원별 중요도가 다르지 않은가?
  - 예: clarity가 precision보다 검색 성능에 더 중요하지 않은가?
- [ ] Line 77: `improvement = after - before` — 음수 improvement가 가능 (gate rejected일 때)

---

### 리뷰 6: Heuristic Regex 품질

`src/description_optimizer/analyzer/heuristic.py`를 읽고 검토합니다.

**확인 포인트:**
- [ ] Lines 24-30: Action verb 패턴 — "gets" (HTTP GET)가 action verb인가?
- [ ] Lines 41-54: Disambiguation — "only"가 domain qualifier인데, "the only way to..."처럼 쓰이면 false positive
- [ ] Lines 81-87: Stats — `\d{2,}` 패턴이 연도(2024)를 stat으로 잡지 않는가?
- [ ] Lines 90-95: Precision — "Git"이 기술 용어인데, 일반 문맥에서의 "git"도 매치
- [ ] 전반적으로: regex 기반 한계를 인지하고 LLM-as-Judge 대안을 고려

---

### 리뷰 7: 실제 데이터로 dry-run 테스트

`data/raw/servers.jsonl`이 있다면 실제 데이터로 dry-run을 실행합니다.

**실행:**
```bash
# data/raw/servers.jsonl이 있는 경우
uv run python scripts/optimize_descriptions.py --dry-run --input data/raw/servers.jsonl

# 없는 경우, 샘플 데이터 생성 후 실행
echo '{"server_id":"github","name":"GitHub","description":"GitHub API","tools":[{"tool_name":"search_issues","description":"Search stuff"},{"tool_name":"create_pr","description":"Creates pull requests on GitHub repositories. Accepts title (string, required), body (string, optional), and base branch. Cannot create PRs across forks."}]}' > /tmp/test_servers.jsonl

uv run python scripts/optimize_descriptions.py --dry-run --input /tmp/test_servers.jsonl
```

**확인 포인트:**
- [ ] dry-run이 에러 없이 실행되는가?
- [ ] 각 tool의 GEO score와 weak dimensions가 출력되는가?
- [ ] score가 직관에 부합하는가?
