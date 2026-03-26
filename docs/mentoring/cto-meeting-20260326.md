# CTO 멘토링 피드백 분석 — 2026.03.26

> 첫 번째 멘토링 세션 피드백을 기반으로 프로젝트 반영 사항 정리

---

## 1. 핵심 피드백 요약

### CTO가 강조한 3가지 메시지

**① Description 최적화가 핵심이다 (Search MCP보다 우선)**

CTO는 "MCP를 찾아주는 MCP" 접근(Bridge/Router)도 유효하지만, **Description 최적화 쪽이 더 효과가 확실하다**고 판단. 그 이유는 Bridge MCP를 만들어도 LLM이 Bridge 자체를 선택하지 않으면 의미가 없기 때문. 반면 Description 품질을 높이면 어떤 환경에서든 선택률이 올라가므로 비즈니스 가치가 더 직접적임.

→ 프로젝트에서 **E4 (Description A/B 인과 검증)이 가장 중요한 실험**이라는 기존 설계와 완전히 일치. 다만 CTO는 여기에 **GEO 테크닉**을 접목할 것을 추가 제안.

**② GEO (Generative Engine Optimization)를 MCP에 적용하라**

SEO가 검색 엔진에서의 콘텐츠 노출을 최적화하듯, GEO는 **LLM이 콘텐츠를 잘 찾아오게 유도하는 기법**. CTO의 핵심 논점: MCP의 메타 정보(description) 검색 메커니즘이 LLM의 콘텐츠 검색 메커니즘과 본질적으로 동일하므로, GEO 테크닉이 MCP description 최적화에 직접 적용 가능.

**③ 통계적 검증으로 설득력을 높여라 (관리도 + 가설 검정)**

단순히 "좋아졌다"가 아니라, X̄-R 관리도로 품질 변동을 모니터링하고, 가설 검정(p-value < 0.05)으로 두 집단 간 차이를 증명하라는 요구. 이는 학술 수준의 엄밀성을 보여주는 차별화 포인트.

---

## 2. GEO (Generative Engine Optimization) — 프로젝트 적용 방안

### 2.1 GEO란?

GEO는 2024년 ACM SIGKDD에서 발표된 연구(Aggarwal et al.)로, LLM 기반 검색 엔진(Generative Engine)에서 콘텐츠가 더 잘 인용/노출되도록 최적화하는 기법.

**핵심 발견**: 전통적 SEO(Keyword Stuffing)는 Generative Engine에서 효과가 낮고, 오히려 **통계 추가, 출처 인용, 인용문 추가** 등이 30-40% visibility 향상을 달성.

### 2.2 GEO 논문의 9가지 최적화 기법

| # | 기법 | 설명 | 효과 |
|---|------|------|------|
| 1 | **Cite Sources** | 신뢰할 수 있는 출처 인용 추가 | 30-40% 향상 (최상위) |
| 2 | **Quotation Addition** | 권위 있는 인용문 추가 | 30-40% 향상 (최상위) |
| 3 | **Statistics Addition** | 정성적 서술을 정량적 통계로 교체 | 30-40% 향상 (최상위) |
| 4 | **Fluency Optimization** | 텍스트 유창성 개선 | 15-30% 향상 |
| 5 | **Easy-to-Understand** | 언어 단순화 | 15-30% 향상 |
| 6 | **Unique Words** | 고유한 어휘 사용 | 중간 |
| 7 | **Technical Terms** | 전문 용어 포함 | 도메인 의존적 |
| 8 | **Authoritative** | 권위적 톤으로 작성 | 중간 |
| 9 | **Keyword Stuffing** | 키워드 반복 삽입 | **효과 낮음** (전통 SEO와 다름) |

**핵심 인사이트**: 도메인별로 효과적인 전략이 다르며, LLM 모델마다 반응하는 description 스타일이 다를 수 있음 (CTO 언급: "LLM 모델마다 찾아가는 게 다 달라서 그거 별 디스크립션 만드는 게 최고 베스트").

### 2.3 MCP Description에 GEO 적용 — 구체적 매핑

GEO 기법을 MCP tool description에 적용하면:

| GEO 기법 | MCP Description 적용 | 예시 |
|----------|---------------------|------|
| Cite Sources | 지원하는 표준/프로토콜 명시 | "Implements RFC 7231 HTTP semantics" |
| Statistics Addition | 성능/커버리지 수치 포함 | "Supports 50+ languages, processes up to 10K tokens/sec" |
| Fluency Optimization | 명확하고 구조적인 설명 | 주어-동사-목적어 패턴, 모호한 표현 제거 |
| Easy-to-Understand | 첫 문장에 핵심 기능 명시 | "Converts PDF documents to searchable text" (vs "A tool for document processing") |
| Technical Terms | 도메인 키워드 정확히 사용 | "OCR", "web scraping", "sentiment analysis" |
| Unique Words | 경쟁 tool과 차별화되는 표현 | 구체적 use case 명시로 disambiguation |

### 2.4 프로젝트 반영: E4 실험 확장

기존 E4 설계 (Version A: Poor vs Version B: Good)에 **GEO 기법 적용 수준**을 독립 변인으로 추가:

```
E4 확장안:
- Version A (Baseline): Smithery 원본 description 그대로
- Version B (GEO-optimized): GEO 상위 3개 기법 적용
  - Cite Sources: 관련 표준/API 명시
  - Statistics Addition: 커버리지/성능 수치 추가
  - Fluency Optimization: 구조적 재작성

측정: Selection Rate Lift (B vs A)
목표: lift > 30%, p < 0.05
```

**추가 실험 제안 (E4-b): 모델별 GEO 효과 차이**

CTO가 "LLM 모델마다 찾아가는 게 다르다"고 언급. 이를 반영:

```
E4-b (선택적 확장):
- 동일 GEO-optimized description으로
- GPT-4o / Claude 3.5 / Gemini에서 각각 selection rate 측정
- 모델 간 차이 유무 확인
```

→ 단, 이는 scope 확대이므로 시간이 허용될 때만 진행. E4 기본 실험 우선.

---

## 3. 통계적 검증 방법론 — 프로젝트 적용

### 3.1 X̄-R 관리도 (Control Chart)

CTO가 언급한 **X̄-R 관리도**는 SPC(Statistical Process Control)의 핵심 도구로, 프로세스의 안정성을 모니터링함.

**구성**:
- **X̄ Chart (평균 관리도)**: 프로세스 평균의 변동 추적. 중심선(CL) = 전체 평균, UCL/LCL = ±3σ
- **R Chart (범위 관리도)**: 프로세스 산포의 변동 추적

**MCP Discovery 적용**:

```
적용 대상: Precision@1의 안정성 모니터링

측정 방법:
1. 동일 Ground Truth 쿼리셋으로 N회 반복 실행
2. 매 실행의 Precision@1을 기록
3. 서브그룹(5회 실행 단위)의 평균(X̄)과 범위(R) 계산
4. 관리도에 플롯

판독:
- UCL/LCL 이내: 프로세스 안정 (common cause variation만 존재)
- UCL/LCL 이탈: 특수 원인 존재 → 조사 필요
- 연속 7점 이상 한쪽으로 치우침: 시스템적 변화 감지
```

**구현 코드 예시** (src/evaluation/metrics/ 하위):

```python
import numpy as np
from dataclasses import dataclass

@dataclass
class ControlChartResult:
    x_bar: float          # 전체 평균
    r_bar: float          # 평균 범위
    ucl_x: float          # X̄ 상한
    lcl_x: float          # X̄ 하한
    ucl_r: float          # R 상한
    lcl_r: float          # R 하한
    subgroup_means: list[float]
    subgroup_ranges: list[float]
    is_stable: bool       # 모든 점이 관리 한계 이내

def compute_control_chart(
    measurements: list[float],
    subgroup_size: int = 5,
) -> ControlChartResult:
    """X̄-R 관리도 계산.

    Args:
        measurements: Precision@1 반복 측정값 리스트
        subgroup_size: 서브그룹 크기 (2-10, 기본 5)
    """
    # A2, D3, D4 상수 (subgroup_size별)
    constants = {
        2: (1.880, 0, 3.267),
        3: (1.023, 0, 2.575),
        4: (0.729, 0, 2.282),
        5: (0.577, 0, 2.115),
    }
    A2, D3, D4 = constants[subgroup_size]

    # 서브그룹 분할
    n_groups = len(measurements) // subgroup_size
    groups = [
        measurements[i * subgroup_size:(i + 1) * subgroup_size]
        for i in range(n_groups)
    ]

    means = [np.mean(g) for g in groups]
    ranges = [max(g) - min(g) for g in groups]

    x_bar = np.mean(means)
    r_bar = np.mean(ranges)

    return ControlChartResult(
        x_bar=x_bar,
        r_bar=r_bar,
        ucl_x=x_bar + A2 * r_bar,
        lcl_x=x_bar - A2 * r_bar,
        ucl_r=D4 * r_bar,
        lcl_r=D3 * r_bar,
        subgroup_means=means,
        subgroup_ranges=ranges,
        is_stable=all(
            (x_bar - A2 * r_bar) <= m <= (x_bar + A2 * r_bar)
            for m in means
        ),
    )
```

### 3.2 가설 검정 (Hypothesis Testing)

CTO가 강조한 **두 집단 비교의 통계적 유의성 검증**:

**E4에서의 적용**:

```
귀무가설 H₀: Description A(Poor)와 B(Good)의 Selection Rate에 차이 없음
대립가설 H₁: Description B(Good)의 Selection Rate가 유의하게 높음

검정 방법: McNemar's test (paired, binary outcome)
 - 동일 쿼리셋에 대해 A/B 각각 정답 여부 측정
 - paired binary → McNemar's test 적합

유의 수준: α = 0.05
판정: p < 0.05이면 H₀ 기각 → Description 품질이 선택률에 유의한 영향
```

**기존 설계와의 정합성**: project-overview.md에 이미 `McNemar's test, p < 0.05`가 명시되어 있음. CTO 피드백은 이 접근을 재확인하고 강조한 것.

**추가 검정 (CTO 제안 반영)**:

| 비교 대상 | 검정 방법 | 적용 실험 |
|-----------|-----------|-----------|
| A/B Description (paired binary) | McNemar's test | E4 |
| 전략 A vs B vs C (3그룹 비교) | Cochran's Q test → post-hoc McNemar | E1 |
| SEO score ↔ Selection Rate (상관) | Spearman rank correlation | E4, E7 |
| Description 하위 요소별 기여도 | OLS Regression | E4 |
| 반복 측정 안정성 | X̄-R 관리도 | 전 실험 |

### 3.3 Evidence Triangulation 강화

CTO의 통계 강조를 반영하여 기존 3-증거 구조를 유지하되, 각 증거의 통계적 엄밀성을 높임:

```
Evidence 1 (Causal): McNemar's test → p < 0.05, lift > 30%
Evidence 2 (Correlational): Spearman r > 0.6, p < 0.05
Evidence 3 (Explanatory): OLS R² > 0.4, 계수 p < 0.05

+ 추가: X̄-R 관리도로 측정 안정성 사전 확인
  → 관리도 불안정 시 실험 결과 신뢰 불가, 원인 조사 우선
```

---

## 4. Smithery 비즈니스 모델 인사이트 (CTO 분석)

CTO가 Smithery의 비즈니스 모델을 분석한 내용:

**Smithery는 MCP 호스팅이 아니라 래퍼(wrapper) 호스팅**:
- 다른 사람이 만든 MCP 서버의 URL을 받아서 프록시로 감싸는 구조
- 이를 통해 모든 호출 통계(어떤 tool이 얼마나 불리는지)를 수집 가능

**향후 비즈니스 방향 예측**:
- Smithery는 메타 정보를 보유하고 있으므로, **Description 커스터마이징 서비스**로 발전할 것
- "돈 받고 너희 MCP 더 잘 찾게 해줄게" → 이것이 곧 우리 프로젝트의 Provider Analytics + Description 개선 가이드

**프로젝트 시사점**: 우리가 구축하는 Analytics + SEO Score + 개선 가이드 기능은 Smithery가 아직 제공하지 않는 가치이며, 이 방향성이 시장의 실제 니즈와 일치함을 CTO가 확인해 준 것.

---

## 5. 클라우드 에지 코딩 (Boto3 + Lambda) — 향후 확장

CTO가 언급한 대규모 MCP 운영 구조:

**핵심 아이디어**:
- MCP 서버를 Lambda로 동적 배포 (서버리스, 비용 효율적)
- MCP 인터페이스가 고정되어 있으므로, 하나의 Lambda 이미지 + DB 기반 설정으로 수만 개 MCP 운영 가능
- Boto3로 Lambda 인스턴스를 프로그래밍 방식으로 생성/소멸

**프로젝트 반영**: 현재 아키텍처 문서(DP8)에 "로컬 FastAPI → Lambda + API Gateway" 배포 경로가 이미 계획됨. CTO 피드백은 이 방향이 맞다는 확인이며, Lambda 제한(동시 실행 수 ~200개)을 넘어서는 스케일에 대한 설계도 고려하라는 추가 제안.

→ **현재 Phase에서는 scope 밖**. docs/plan/deferred.md에 기록하여 향후 확장 포인트로 관리.

---

## 6. 액션 아이템 정리

### 즉시 반영 (이번 주)

| # | 항목 | 반영 위치 | 우선순위 |
|---|------|-----------|----------|
| 1 | E4 Description A/B에 GEO 상위 3기법 적용 | experiment-details.md | **높음** |
| 2 | GEO 논문 정독 (arxiv:2311.09735) | research/ | **높음** |
| 3 | X̄-R 관리도 유틸리티 구현 | src/evaluation/metrics/ | 중간 |
| 4 | 가설 검정 코드 정비 (McNemar, Spearman) | src/analytics/ab_test.py | 중간 |

### 설계 문서 업데이트

| # | 항목 | 반영 위치 |
|---|------|-----------|
| 5 | E4 실험 스펙에 GEO 기법 명시 | experiment-details.md |
| 6 | Description Quality Score 산정에 GEO 요소 반영 | metrics-rubric.md (SEO Score → GEO-aware Score) |
| 7 | 통계적 검증 파이프라인 문서화 | evaluation.md |
| 8 | Lambda/Boto3 확장 계획 | deferred.md |

### 다음 멘토링까지 (Week 2)

| # | 목표 | 산출물 |
|---|------|--------|
| 9 | E0 실험 완료 (1-Layer vs 2-Layer) | E0 결과 리포트 |
| 10 | E1 실험 진행 (전략 비교) | 중간 결과 |
| 11 | GEO 기법 기반 Description Version B 초안 | data/descriptions/ |
| 12 | X̄-R 관리도 + McNemar 테스트 코드 PR | src/evaluation/ |

---

## 7. CTO 평가 요약

- 리서치 수준에 대해 **"대학원생 스타일", "리서치를 너무 잘하셨다"** 긍정 평가
- 문제 인식(prompt bloating, selection complexity)이 정확하다고 확인
- 실험 설계의 통제 변인 관리, ABC 패턴 접근에 대해 긍정
- **핵심 테제 "Description 품질 → 선택률" 방향이 맞다**고 확인
- Bridge MCP + Description 최적화 **두 축을 모두 다루면 200% 수준**이라는 평가

---

## 참고 문헌

- Aggarwal et al., "GEO: Generative Engine Optimization", ACM SIGKDD 2024 (arxiv:2311.09735)
- X̄-R Control Charts: NIST Engineering Statistics Handbook §6.3.2.1
