# 세션 핸드오프 — 2026.03.26

> Claude Code에 전달하는 컨텍스트 문서.
> 오늘 CTO 멘토링 + 스터디 세션에서 결정된 사항과 남은 작업을 정리.

---

## 오늘 결정된 핵심 사항 2가지

### 1. GEO (Generative Engine Optimization)를 프로젝트 전반에 통합

CTO 피드백: "GEO 테크닉을 MCP description에 적용하면 선택률을 높일 수 있다."
LLM이 MCP 툴을 찾는 메커니즘 = LLM이 웹 콘텐츠를 찾는 메커니즘 → GEO 기법 직접 적용 가능.

GEO 논문(Aggarwal et al., ACM SIGKDD 2024, arxiv:2311.09735)의 핵심 발견:
- **효과 있음**: Cite Sources, Statistics Addition, Fluency Optimization (30-40% visibility 향상)
- **효과 없음**: Keyword Stuffing (전통 SEO와 다름)

### 2. SEO Score → GEO Score로 개념 전환

현재 프로젝트 전반에 "SEO Score"라는 용어가 사용되고 있으나, 이는 잘못된 네이밍.
우리가 측정하려는 것은 "LLM이 선택하고 싶어지는 description 품질"이므로 GEO Score가 맞음.

**기존 항목은 유효하되, 재명명 + GEO 항목 추가:**

| 기존 (SEO Score) | 변경 (GEO Score) | 비고 |
|-----------------|-----------------|------|
| specificity_score | clarity_score | 첫 문장의 핵심 기능 명확도 포함 |
| disambiguation_score | disambiguation_score | 유지 |
| parameter_coverage_score | parameter_coverage_score | 유지 |
| negative_instruction_score | boundary_score | 재명명 |
| *(없음)* | stats_score | **신규** — 수치/커버리지 포함 여부 (GEO: Statistics Addition) |
| *(없음)* | precision_score | **신규** — 표준/프로토콜/기술 용어 정확도 (GEO: Technical Terms) |

---

## 이미 반영된 변경사항

### `docs/mentoring/cto-meeting-20260326.md` (신규 생성)
- CTO 멘토링 전체 피드백 분석
- GEO 9가지 기법 및 MCP 적용 방법
- X̄-R 관리도 + 가설 검정 방법론
- Smithery 비즈니스 모델 분석

### `docs/design/experiment-design.md`
- **추가**: "통계적 검증 적용 계획" 섹션
  - X̄-R 관리도: E0 직전 1회, 측정 안정성 사전 확인
  - 가설 검정(p-value): E4 필수, E0/E1 권장, E2/E3/E5/E6 선택적

### `docs/design/experiment-details.md`
- **E4 섹션 앞에 추가**: "Version A/B 작성 기준 (GEO 기반)"
  - Version A: Smithery 원본 수준
  - Version B: GEO 상위 3기법(Statistics Addition, Fluency Optimization, Cite Sources) 적용
  - E7과의 연결 관계 명시

---

## 아직 반영 안 된 변경사항 (Claude Code 작업 필요)

### 🔴 우선순위 높음

#### 1. `docs/design/metrics-rubric.md` — Description Quality Score 섹션 업데이트

**위치**: `### 4. Description Quality Score (SEO Score)` 섹션

**변경 내용**:
- 섹션 제목: `Description Quality Score (SEO Score)` → `Description Quality Score (GEO Score)`
- 정의 업데이트: `weighted_average(specificity, disambiguation, parameter_coverage)` → 6개 항목으로 확장
- 새 항목 추가: `stats_score`, `precision_score`
- 기존 항목 재명명: `specificity_score` → `clarity_score`, `negative_instruction_score` → `boundary_score`

**참고**: `8b. Spearman` 섹션의 `quality_scores = seo_score(tool)` 주석도 `geo_score`로 교체 필요.

#### 2. `docs/design/experiment-design.md` — E7 설명 업데이트

**위치**: E0-E7 One-line Summary 테이블의 E7 행

**변경 내용**:
```
전: | **E7** | SEO 점수 방식 비교 (휴리스틱 vs LLM) | Spearman(score, selection_rate) | OQ-1 해결 |
후: | **E7** | GEO 점수 방식 비교 (휴리스틱 vs LLM) | Spearman(geo_score, selection_rate) | OQ-1 해결 |
```

#### 3. `docs/design/experiment-details.md` — E7 섹션 업데이트

**위치**: `## E7: SEO 점수 방식 비교 (OQ-1 해결)` 섹션

**변경 내용**:
- 섹션 제목: `SEO 점수 방식 비교` → `GEO 점수 방식 비교`
- 조건 테이블의 `정규식 휴리스틱 (seo_score.py 현재)` → `정규식 휴리스틱 (geo_score.py)` 로 파일명 예고
- 측정 항목: `Spearman(score, selection_rate)` → `Spearman(geo_score, selection_rate)`
- 다음 설명 문장 추가:
  > E4의 Version B는 GEO 기법으로 작성되므로, E7에서 검증된 GEO Score 채점 방식이 Version B에 실제로 높은 점수를 부여하는지 교차 확인 가능.


#### 4. `docs/` 내 description 품질 점수의 정의가 문서마다 서로 다르게 적혀 있어 정합성 필요

- 연구 문서는 DQS를 5차원으로 정의하고, 가중치도 0.2로 동일하게 설정
- 계획 문서는 SEO Score를 3차원으로 정의하고, 가중치도 다르게 설정
  - Purpose Clarity와 Negative Instruction이 3차원 버전에서는 사라진다.
  - Parameter Description은 parameter_coverage로 이름과 의미가 약간 바뀐다.
- 정합성이 맞지 않는 부분에 대한 전반적인 확인/검토 필요
- 관리도와 가설 검정 등 새로 추가된 내용도 전체 `docs/` 내 관련된 모든 문서에 충실히 반영되었는지 확인/검토 필요


### 🟡 우선순위 중간

#### 5. `.claude/rules/architecture.md` — 파일명 예고 업데이트

**위치**: Module Structure의 `analytics/` 섹션

**변경 내용**:
```
전: ├── seo_score.py       # Description SEO score
후: ├── geo_score.py       # Description GEO score (GEO 기법 기반 품질 평가)
```

#### 5. `.claude/rules/eval-workflow.md` — Model Grader 섹션 업데이트

**위치**: `### 2. Model Grader` 섹션의 주석

**변경 내용**:
```
전: 복잡한 품질 평가에만 사용 (Description SEO score 등)
후: 복잡한 품질 평가에만 사용 (Description GEO score 등)
```

#### 6. `docs/design/experiment-details.md` — E4의 Regression 코드 업데이트

**위치**: `### 4-3. Regression R-squared` 코드 블록

**변경 내용**:
```python
# 전
X = df[['specificity_score', 'disambiguation_score',
        'parameter_coverage_score', 'negative_instruction_score']]

# 후
X = df[['clarity_score', 'disambiguation_score',
        'parameter_coverage_score', 'boundary_score',
        'stats_score', 'precision_score']]
```

### 🟢 낮은 우선순위 (코드 작업 시 함께)

#### 7. `src/analytics/seo_score.py` → `geo_score.py` 파일 리네임 (코드 구현 시점에)
- 아직 파일이 없거나 초기 단계라면 처음부터 `geo_score.py`로 만들 것
- 이미 구현되어 있다면 rename + 내부 클래스/함수명도 `SeoScore` → `GeoScore`로 변경

#### 8. `docs/plan/checklist.md` 확인
- SEO Score 관련 체크 항목이 있다면 GEO Score로 업데이트

---

## E4 + E7의 관계 (코드 작성 시 참고)

```
GEO 기법 (논문 근거)
  ├─→ E4 Version B 작성 레시피 (이미 반영)
  └─→ GEO Score 루브릭 항목 (위 작업 후 반영)

E7 (GEO Score 채점 방식 검증)
  ├── E7-A: 정규식 휴리스틱으로 GEO Score 채점
  └── E7-B: LLM-based로 GEO Score 채점
  → 어느 방식이 selection_rate와 더 상관 있는가 → 검증된 방식을 E4 분석에 사용

E4 (핵심 테제 검증)
  ├── Primary: A/B Lift (McNemar's test, p < 0.05)
  ├── Secondary: Spearman(geo_score, selection_rate), r > 0.6
  └── Supplementary: OLS Regression, R² > 0.4
```

---

## 통계 적용 계획 (이미 experiment-design.md에 반영됨, 참고용)

| 도구 | 적용 시점 | 목적 |
|------|-----------|------|
| X̄-R 관리도 | E0 직전 1회 | 측정 안정성 확인 |
| p-value (McNemar) | E4 필수 | 핵심 테제 통계 증명 |
| p-value (Mann-Whitney) | E0, E1 권장 | 전략 비교 근거 |
| Spearman, OLS | E4 필수 | Evidence triangulation |

구현 파일: `src/evaluation/metrics/control_chart.py` (미구현)

---

## 참고 문서

- 오늘 멘토링 전체 분석: `docs/mentoring/cto-meeting-20260326.md`
- GEO 논문: arxiv:2311.09735 (ACM SIGKDD 2024)
- 현재 실험 설계: `docs/design/experiment-design.md`
- 현재 실험 상세: `docs/design/experiment-details.md`
- 현재 지표 루브릭: `docs/design/metrics-rubric.md`
