# ToolScan/SpecTool: 7가지 도구 선택 오류 패턴 분류

> 출처: arxiv:2411.13547 (2024)
> 한 줄 요약: LLM의 도구 사용에서 발생하는 7가지 오류 패턴을 체계적으로 분류하고, 특히 "유사 API 혼동(similar tool confusion)"이 주요 실패 원인임을 밝힌 연구.

---

## 해결하려는 문제

LLM이 도구를 사용할 때 발생하는 오류를 "맞았다/틀렸다"로만 평가하면 개선 방향을 알 수 없다. 어떤 유형의 오류가 얼마나 자주 발생하는지, 각 오류의 원인이 무엇인지를 체계적으로 분류하고 진단하는 프레임워크가 필요하다.

## 핵심 아이디어

- LLM의 도구 사용 오류를 **7가지 패턴**으로 분류하는 taxonomy를 제안한다.
- 이 중 **"similar tool confusion"**(유사 API 간의 혼동)을 별도 카테고리로 정의: "Environments with similar APIs tend to confuse the models."
- 각 오류 패턴별 발생 빈도, 원인, 해결 방향을 제시한다.

## 방법론

상세 분석 추가 예정

## 주요 결과

- 7가지 tool-use 오류 패턴을 식별하고 분류 체계를 구축
- **Similar tool confusion**이 주요 오류 유형 중 하나임을 확인: 기능이 유사한 API들이 있는 환경에서 모델의 혼동 발생
- 오류 유형에 따라 서로 다른 개선 전략이 필요함을 시사

## 장점

- 도구 사용 오류의 최초의 체계적 분류 체계 (7가지 패턴)
- 오류 유형별 진단이 가능하여 targeted 개선이 가능
- Similar tool confusion을 독립 카테고리로 분류하여 description 품질 개선의 근거 제공

## 한계

상세 분석 추가 예정

## 프로젝트 시사점

MCP Discovery Platform의 Confusion Rate 지표(Metric #3)의 핵심 이론적 근거 중 하나이다. ToolScan/SpecTool이 식별한 "similar tool confusion" 패턴은 우리 시스템에서 직접적으로 측정하고 대응하는 핵심 오류 유형이다.

두 실패 유형은 처방이 다르다:
- **Confusion** (정답이 Top-K에 있지만 rank-1이 아님): description disambiguation 개선 → Provider에게 안내
- **Miss** (정답이 Top-K에 없음): 임베딩/검색 전략 자체를 개선

metrics-rubric.md에서 Confusion Rate 목표를 "전체 오류의 50% 이하가 confusion"으로 설정하고 있으며, 특정 Tool 쌍의 confusion count > 5이면 Provider에게 disambiguation 알림을 보내도록 설계되어 있다.

또한 ToolScan의 7가지 오류 패턴 분류는 우리 평가 하네스에서 오류 원인 분석(error analysis)의 참고 프레임워크로 활용된다.

## 적용 포인트

- **Confusion Rate (Metric #3)**: ToolScan의 similar tool confusion 패턴을 기반으로 confusion vs miss 분류
- **Provider Analytics — Confusion Matrix (D-5)**: 어떤 Tool 쌍에서 confusion이 발생하는지 시각화
- **Alert 시스템**: 특정 Tool 쌍의 confusion count > 5이면 Provider에게 disambiguation 개선 안내
- **오류 분석 프레임워크**: 7가지 오류 패턴을 참고하여 평가 하네스의 error analysis 모듈 설계

## 관련 research 문서

- [evaluation-metrics.md](../research/evaluation-metrics.md) — Confusion Rate 지표 정의 및 ToolScan 인용
