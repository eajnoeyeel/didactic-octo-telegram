# Description Optimizer — 문서 변경 계획

> Date: 2026-03-30
> Branch: `feat/description-optimizer`
> Purpose: GEO-P@1 불일치 근본원인 분석 결과를 기준으로, 이번 브랜치에서 수정 가능한 문서만 대상으로 변경 계획 정리

---

## 1. 범위 규칙

이번 문서 정비는 아래 명령 결과에 포함되는 **기존 문서만** 수정 대상으로 삼는다.

```bash
git diff --name-only $(git merge-base HEAD main)..HEAD
```

정책:

- 위 목록에 없는 기존 파일은 이번 패스에서 수정하지 않는다.
- 예외는 이 계획 문서 자신뿐이다.
- root design/SOT 중 이번 브랜치에서 건드리지 않은 문서는 “영향은 있음” 정도만 기록하고 실제 수정 대상에는 넣지 않는다.

---

## 2. 이번 패스에서 수정하지 않을 문서

아래 파일은 영향은 있지만, 이번 브랜치에서 수정 이력이 없는 기존 파일이므로 본문 수정 대상에서 제외한다.

- `docs/design/metrics-rubric.md`
- `docs/design/experiment-design.md`
- `docs/design/experiment-details.md`
- `docs/mentoring/open-questions.md`
- `docs/design/evaluation.md`

이 파일들은 후속 브랜치나 별도 문서 정비 패스에서 다룬다.

---

## 3. 공통 변경 원칙

아래 원칙을 수정 대상 문서 전반에 일관되게 반영한다.

1. `search_description`은 retrieval 전용 텍스트다.
2. `optimized_description`은 사람용 설명이다.
3. GEO는 hard gate가 아니라 diagnostic metric이다.
4. P@1이 최종 판단 기준이다.
5. sibling 이름 나열과 contrast phrasing은 disambiguation “개선”이 아니라 retrieval 오염 가능성으로 취급한다.
6. “boundary 제거만으로 Goodhart 해결” 같은 결론은 최신 P@1 결과 기준으로 superseded 처리한다.

---

## 4. 수정 대상 문서

아래 파일들은 이번 브랜치에서 이미 수정된 기존 문서이므로, 이번 패스의 실제 변경 후보에 포함한다.

| 파일 | 변경 유형 | 무엇을 바꿀까 | 왜 바꿔야 하나 |
|------|-----------|--------------|----------------|
| `description_optimizer/CLAUDE.md` | `rewrite` | 프로젝트 요약, current state, pipeline, gate 정의, next steps, 참고 문서 링크 정리 | 현재 설명이 GEO 중심이고, retrieval용 `search_description`과 실제 평가 경로 불일치를 반영하지 못함 |
| `description_optimizer/docs/evaluation-design.md` | `rewrite` | primary treatment를 `search_description`으로 전환, 3-way A/B, per-query breakdown, McNemar 추가 | 현재 설계는 `optimized_description` 중심이라 최신 실패 원인을 반영하지 못함 |
| `description_optimizer/docs/progress.md` | `rewrite` | “Phase 2 완료” 이후 상태를 retrieval misalignment와 재설계 필요성 중심으로 재기록 | 현재 문서는 구현 완료 보고서에 가깝고 최신 문제 상태를 숨김 |
| `description_optimizer/docs/research-analysis.md` | `targeted update` | GEO 관련 서술을 “생성 가이드”로 축소하고 retrieval objective와의 차이를 명시 | 현재 문장 일부가 GEO를 직접 최적화 목표처럼 읽히게 만듦 |
| `description_optimizer/docs/research-phase2-synthesis.md` | `targeted update` | 최종 추천 아키텍처를 `search_description` 중심으로 정리, “boundary 제거만으로 해결” 서술 정정 | 최신 P@1 결과 이후 결론이 더 이상 충분하지 않음 |
| `description_optimizer/docs/verification-report.md` | `superseded note` | 문서 상단에 현재 기준에서 superseded 되었음을 추가 | GEO calibration / boundary / hard gate 기준이 현재 방향과 충돌 |
| `docs/analysis/description-optimizer-root-cause-analysis.md` | `targeted update` | 최신 evidence 기반 근본원인 분석으로 갱신 | 기존 버전은 grounded 이전/중간 상태 문제 분석에 치우쳐 있음 |
| `docs/analysis/grounded-ab-comparison-report.md` | `superseded note` | “Goodhart 해결” 결론 위에 superseded note 추가 | grounded가 GEO 상으로 이겼다는 사실과 retrieval 개선은 별개이기 때문 |
| `docs/progress/grounded-optimization-handoff.md` | `superseded note` | 세션 핸드오프 자체는 보존하되 최신 한계를 상단에 표기 | 기록 문서이므로 본문 재작성보다 상단 주석이 적합 |
| `docs/progress/status-report.md` | `targeted update` | 현재 상태와 다음 단계에 retrieval mismatch와 문서 정비 필요성을 반영 | 지금은 “분석 필요” 수준에서 멈춰 있고, 구조적 원인과 대응 방향이 반영되지 않음 |

---

## 5. 문서별 세부 메모

### `description_optimizer/CLAUDE.md`

- `Quality Gate` 설명에서 `GEO 비회귀`를 hard gate처럼 쓰지 않도록 수정
- `search_description (embedding용)`가 실제로 retrieval 주경로여야 한다는 점 명시
- 깨진 분석 문서 참조나 오래된 다음 단계 서술 정리

### `description_optimizer/docs/evaluation-design.md`

- “Control vs Treatment”를 `original` vs `search_description` 기본 비교로 수정
- `optimized_description`은 보조 조건으로만 다룸
- 성공 기준에 `no regression on degraded 3 cases` 추가

### `description_optimizer/docs/progress.md`

- 완료 보고서 구조는 유지하되, 상단에 현재 상태 요약 추가
- grounded optimization이 hallucination 완화에는 성공했지만 retrieval alignment는 미해결이라는 점 명시

### `description_optimizer/docs/research-analysis.md`

- GEO 기법은 “아이디어 원천”으로 유지
- 다만 selection metric과 직접 동치인 것처럼 읽히는 표현은 제거

### `description_optimizer/docs/research-phase2-synthesis.md`

- 최종 추천안이 `search_description` 우선, GEO diagnostic-only라는 점을 명시
- 길이 팽창과 sibling contamination을 독립 리스크로 추가

### `description_optimizer/docs/verification-report.md`

- 문서 상단에 “historical verification artifact” 성격과 superseded 이유 기록
- 본문 전체를 최신 기준으로 다시 쓰지는 않음

### `docs/analysis/description-optimizer-root-cause-analysis.md`

- 탐색 가설 나열이 아니라 원인 우선순위가 있는 문서로 유지
- evaluator mismatch와 heuristic misalignment를 핵심 결론으로 고정

### `docs/analysis/grounded-ab-comparison-report.md`

- 본문 데이터는 보존
- 다만 상단에 “GEO 기준 비교 결과이며 retrieval 성공을 의미하지 않는다”는 note 추가

### `docs/progress/grounded-optimization-handoff.md`

- 이미 지나간 세션 기록이므로 본문은 유지
- 상단 note로 “후속 P@1 평가에서 retrieval regression 확인”만 표기

### `docs/progress/status-report.md`

- 현재 상태 표에 “GEO-P@1 불일치 원인 정리 완료 / 문서 정렬 필요” 반영
- 다음 단계에 root-cause-driven docs sync 포함

---

## 6. 후속 실행 순서

문서 수정은 아래 순서로 진행한다.

1. `docs/analysis/description-optimizer-root-cause-analysis.md`
2. `description_optimizer/CLAUDE.md`
3. `description_optimizer/docs/evaluation-design.md`
4. `description_optimizer/docs/progress.md`
5. `description_optimizer/docs/research-analysis.md`
6. `description_optimizer/docs/research-phase2-synthesis.md`
7. `docs/progress/status-report.md`
8. superseded note 대상 문서들

이 순서를 쓰는 이유는, **분석 결론을 먼저 고정한 뒤 나머지 문서가 그 결론을 따라가도록 하기 위해서**다.

---

## 7. 완료 기준

이번 문서 정비 패스가 끝났다고 볼 조건:

- 수정 대상 문서마다 `무엇을`, `왜`, `어떻게`가 결정되어 있음
- 수정 금지 문서와 수정 대상 문서가 명확히 분리되어 있음
- 모든 문서가 동일한 핵심 원칙(`search_description` retrieval, GEO diagnostic-only, P@1 최종 판단)을 공유함
- 기록 문서에는 본문 재작성 대신 superseded note만 사용함
