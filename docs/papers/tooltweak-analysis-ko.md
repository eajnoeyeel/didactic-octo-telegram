# ToolTweak: Understanding the Effects of Adversarial Tool Descriptions on LLM Tool Selection

> 출처: arxiv:2510.02554 (2025)
> 한 줄 요약: 도구 이름과 설명을 체계적으로 조작하면 LLM의 도구 선택률을 ~20%에서 81%까지 끌어올릴 수 있음을 실증적으로 보여준 적대적 공격 연구.

---

## 해결하려는 문제

LLM 기반 에이전트의 도구 선택이 도구 설명(description)의 표현 방식에 얼마나 취약한지를 정량적으로 측정하려 한다. 도구의 실제 기능은 동일하더라도, 이름과 설명을 전략적으로 변경하는 것만으로 LLM이 해당 도구를 선택하는 비율이 극적으로 바뀔 수 있는지를 검증한다.

## 핵심 아이디어

- 도구의 이름(name)과 설명(description)을 반복적으로(iteratively) 조작하는 적대적 공격(adversarial manipulation) 방법론을 제안한다.
- 공격자가 도구의 실제 기능을 바꾸지 않고, 오직 메타데이터(이름, 설명)만 변경하여 LLM이 해당 도구를 더 자주 선택하도록 유도한다.
- 이를 통해 description이 LLM 도구 선택에 미치는 인과적(causal) 영향을 직접 증명한다.

## 방법론

- 도구 이름과 설명을 체계적으로 변경하면서 LLM의 선택률 변화를 측정하는 반복 실험(iterative manipulation) 방식을 사용한다.
- 조작 전 baseline 선택률(~20%)과 조작 후 선택률(81%)을 비교하여 직접적인 A/B 효과를 관찰한다.

## 주요 결과

- **선택률 변화**: baseline ~20% → 조작 후 **81%** (약 4배 증가)
- description 조작만으로 도구 선택률이 극적으로 변화함을 실증
- 이름(name)과 설명(description) 모두 선택에 유의미한 영향을 미침

## 장점

- LLM 도구 선택에서 description의 인과적 영향을 직접적으로 증명한 최초의 체계적 연구
- 적대적 관점에서 도구 생태계의 보안 취약점을 명확히 드러냄
- 방어 메커니즘 설계의 필요성에 대한 정량적 근거 제공

## 한계

상세 분석 추가 예정

## 프로젝트 시사점

MCP Discovery Platform의 핵심 테제("description 품질이 높을수록 Tool 선택률이 높아진다")를 **역방향으로 이미 증명**한 논문이다. ToolTweak이 "나쁜 의도로 설명을 조작하면 선택률이 올라간다"는 것을 보였다면, 우리 프로젝트는 "좋은 방향으로 설명을 개선하면 선택률이 올라간다"는 동일한 메커니즘을 Provider에게 가치로 전달한다.

Evidence Triangulation의 Primary Evidence (8a. A/B Selection Rate Lift)의 설계가 ToolTweak의 직접적 description 조작 → selection rate 변화 관찰 방법론에 기반한다. ToolTweak은 Spearman이 아닌 직접적 A/B 조작으로 인과 관계를 증명했으며, 이것이 우리 metrics-rubric.md에서 A/B Lift를 Primary Evidence로 설정한 이유이다.

## 적용 포인트

- **Metric 8a (A/B Selection Rate Lift)**: ToolTweak 방법론을 참고하여 자체 MCP 서버의 description 조작 → 선택률 변화 측정 설계
- **Provider Analytics**: description 품질 개선이 선택률에 미치는 인과적 효과의 이론적 근거
- **Description Quality Score (DQS)**: 높은 DQS → 높은 선택률의 가설을 뒷받침하는 핵심 근거 논문
- **Spearman(DQS, Selection Rate) (Metric 8b)**: ToolTweak이 Spearman이 아닌 직접 조작으로 증명했으므로, Spearman은 Secondary Evidence로 위치

## 관련 research 문서

- [description-quality-scoring.md](../research/description-quality-scoring.md) — DQS 설계의 이론적 배경
- [evaluation-metrics.md](../research/evaluation-metrics.md) — Provider 분석용 특수 지표 (Spearman 상관계수, A/B Lift)
