# MCP Tool Description 품질 점수 (DQS) — 리서치 요약

> 작성: 2026-03-21 | 최종 업데이트: 2026-03-22
> 맥락: OQ-1 (SEO 점수 산정 방식) 해결

---

## 결정

**5-dimension DQS 채택** (동등 가중치 0.2x5, E7 calibration)

- 차원: Purpose Clarity, Specificity, Disambiguation, Negative Instruction, Parameter Description
- 초기 가중치: 동등(0.2x5) — 리서치에 명시적 가중치 근거 없으므로 E7 파일럿에서 calibration
- 스코어링 방식: E7에서 휴리스틱 vs LLM-as-Judge 비교 후 결정

---

## 논문 핵심 발견

### Paper A: "MCP Tool Descriptions Are Smelly!" (Hasan et al., 2025)

- 856개 도구/103개 서버 분석 — **97.1%** 최소 1개 quality defect 보유
- 목적 미명확 56%, 사용 가이드 부재 89.3%
- 설명 augmentation → **+5.85pp 작업 성공률**
- Examples 제거 ablation에서 성능 저하 없음 → scoring에서 제외 가능

### Paper B: "From Docs to Descriptions" (Wang et al., 2025)

- 10,831개 MCP 서버 분석 — 표준 준수 설명 선택률 72% vs 비준수 20% (**260% 증가**)
- 18가지 문제 카테고리 (Accuracy, Functionality, Completeness, Conciseness)
- Functionality 차원이 선택률에 가장 큰 영향 (+11.6%)

### Paper F: "Tool Preferences in Agentic LLMs are Unreliable" (EMNLP 2025)

- 설명의 작은 편집 → 선택 도구의 큰 변화
- 설명은 "설득 입력(persuasive input)" — 핵심 테제의 타당성 증명

### Paper G: CallNavi (2025)

- GPT-4o 라우팅 정확도 91.9% — 목적 명확성 + "언제 사용" 가이드가 최우선
- 파라미터 세부사항은 상대적으로 덜 중요

### Paper L: LLM-Rubric (Microsoft, ACL 2024)

- LLM 확률 분포 위에 calibration layer → 비보정 대비 **2배 향상**
- E4 후 calibration 모델 학습 가능

---

## 5-차원 DQS 정의

| # | 차원 | 정의 | 근거 |
| --- | ------ | ------ | ------ |
| 1 | **Purpose Clarity** | 이 도구가 정확히 무엇을 하고 언제 사용하는가? | Paper A (56% 실패), Paper G (라우팅 최우선) |
| 2 | **Specificity** | 구체적 데이터 소스, 출력 형식, 범위 경계가 있는가? | Paper B (Accuracy +11.6%) |
| 3 | **Disambiguation** | 유사 도구와 명확히 구분되는가? | Confusion Rate 지표, MetaTool |
| 4 | **Negative Instruction** | 이 도구가 NOT 하는 것이 명확한가? | Paper A (Limitations 89.3% 부재) |
| 5 | **Parameter Description** | 입력값이 타입/제약/예제와 함께 설명되는가? | Paper A, Paper G (낮은 우선도) |

**복합 점수**: `DQS = 0.2 x (purpose + specificity + disambiguation + negative_instruction + param_desc)`

---

## 스코어링 방식 비교 (E7 파일럿에서 결정)

### 방식 A: 휴리스틱 (`seo_score.py`)

- Purpose: 행동 동사 시작, "what"+"when-to-use" — Regex 패턴
- Specificity: 플랫폼명, 출력 형식, 수치 제약 — 명칭 사전
- Disambiguation: "unlike", "only", domain qualifier — Contrast regex
- Negative Instruction: "NOT for", "cannot" — 부정 패턴
- Parameter Description: 파라미터명, 타입명, inputSchema 완성도
- 장점: 무료, 결정론적, 즉시 실행

### 방식 B: LLM-as-Judge (`llm_scorer.py`)

- GPT-4o-mini, 3-judge ensemble (Paper A 기법), 5-차원 rubric 1-5점
- 출력: JSON, [0.0, 1.0] 정규화 — 비용 ~$0.03 (30개)
- 장점: 의미론적 이해, 미묘한 차이 감지

---

## E7 파일럿 실험 설계

- **샘플**: 30개 설명 (자체 서버 6 + Smithery 12 + 다양 카테고리 12)
- **인간 레이블**: 5개 차원별 1-5점 (동일 rubric)
- **비교**: Spearman (인간 vs 휴리스틱/LLM), MAE, Williams' test

### 결정 기준

- 둘 다 r_s >= 0.7 → **휴리스틱** (무료, 빠름)
- LLM >= 0.7, 휴리스틱 < 0.5 → **LLM**
- LLM >= 0.7, 휴리스틱 0.5-0.7 → **하이브리드**
- 둘 다 < 0.5 → rubric 차원 재검토

---

## Evidence Triangulation 연결

### Metric 8b: Spearman(DQS, Selection Rate)

- `r_s = Spearman(DQS_i, Precision@1_i)` for all tools
- 목표: r_s > 0.6, p < 0.05

### Metric 8c: Regression R²

- `OLS(selection_rate ~ purpose + specificity + disambiguation + negative_instruction + param_desc)`
- 목표: R² > 0.4, 최소 1개 요소 p < 0.05
- Provider에게 "설명의 어떤 부분이 선택률에 가장 기여하는가" actionable 피드백

---

## E7 파일럿에서 답해야 할 질문

1. 동등 가중치로도 인간 평가와 r_s >= 0.6 상관이 나오는가?
2. 특히 높은/낮은 상관을 보이는 차원은?
3. 휴리스틱 vs LLM 어느 방식이 인간 평가와 더 일치하는가?

---

## 관련 papers

- [`../papers/mcp-descriptions-smelly-analysis-ko.md`](../papers/mcp-descriptions-smelly-analysis-ko.md) — Paper A
- [`../papers/from-docs-to-descriptions-analysis-ko.md`](../papers/from-docs-to-descriptions-analysis-ko.md) — Paper B
- [`../papers/tool-preferences-unreliable-analysis-ko.md`](../papers/tool-preferences-unreliable-analysis-ko.md) — Paper F
- [`../papers/callnavi-analysis-ko.md`](../papers/callnavi-analysis-ko.md) — Paper G
- [`../papers/llm-rubric-analysis-ko.md`](../papers/llm-rubric-analysis-ko.md) — Paper L
