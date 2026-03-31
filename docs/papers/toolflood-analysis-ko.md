# ToolFlood: Semantic Covering Attack on Tool Selection

> 출처: arxiv:2603.13950
> 한 줄 요약: 악의적 도구가 정당한 도구의 의미적 영역을 "덮어씌우는(semantic covering)" 공격으로 LLM의 도구 선택을 교란하는 보안 위협을 분석한 연구.

---

## 해결하려는 문제

LLM 기반 에이전트가 도구를 선택할 때, 공격자가 악의적 도구(malicious tool)를 등록하여 정당한 도구의 의미적 영역을 "덮어씌우는(cover)" 방식으로 선택을 교란할 수 있는 보안 위협을 분석한다. 개방형 도구 생태계(MCP 등)에서 누구나 도구를 등록할 수 있을 때, 이러한 semantic covering 공격이 얼마나 효과적인지를 검증한다.

## 핵심 아이디어

- **Semantic Covering Attack**: 정당한 도구의 description과 의미적으로 유사하지만 악의적인 기능을 가진 도구를 전략적으로 배치하여, LLM이 정당한 도구 대신 악의적 도구를 선택하도록 유도. 단순 대량 등록이 아닌 임베딩 공간의 기하학적 배치 전략을 사용하는 2단계 공격(1단계: 도구명/설명 생성, 2단계: 탐욕적 선택)
- ToolTweak이 "단일 도구의 description을 조작"하는 것이라면, ToolFlood는 "임베딩 기하학 기반으로 악의적 도구를 전략적 배치하여 의미 공간을 covering"하는 전략
- 도구 생태계의 무결성(integrity)과 신뢰성(reliability)에 대한 근본적인 보안 위협을 제기

## 방법론

상세 분석 추가 예정

## 주요 결과

- 공격 성공률 최대 **95%** 달성
- 상세 분석 추가 예정

## 장점

- 개방형 도구 생태계의 근본적 보안 취약점을 체계적으로 분석
- 실용적인 공격 시나리오를 제시하여 방어 메커니즘 설계의 필요성을 입증
- ToolTweak(개별 도구 조작)과 상호보완적인 관점 제공

## 한계

상세 분석 추가 예정

## 프로젝트 시사점

MCP Discovery Platform은 개방형 MCP 생태계에서 도구를 추천하는 시스템이므로, ToolFlood가 경고하는 semantic covering 공격에 직접적으로 노출된다. 누구나 MCP 서버를 등록할 수 있는 환경에서, 악의적 Provider가 정당한 서버의 의미적 영역을 덮어씌우는 도구를 대량 등록할 수 있다.

이는 다음 시스템 설계에 영향을 미친다:
- **Spec Compliance 검증**: 등록 시 schema validation과 기능 검증으로 악의적 도구 필터링
- **신뢰도 기반 추천**: 검증된 Provider의 도구를 우선 추천
- **이상 탐지**: 기존 도구와 의미적으로 매우 유사한 신규 등록을 감지

architecture.md의 논문 참고 목록에서 ToolFlood를 "Semantic covering attack on tool selection" 기여로 직접 인용하고 있다.

## 적용 포인트

- **Spec Compliance (Provider 필수 기능)**: 등록 시 MCP 스펙 준수 여부 자동 검사 + 의미적 중복 도구 탐지
- **Tool Pool 관리**: 기존 도구와 description 유사도가 비정상적으로 높은 신규 등록 시 경고/심사
- **Provider 신뢰도 모델**: 검증된 Provider vs 미검증 Provider 구분, 신뢰도 기반 추천 가중치
- **보안 모니터링**: semantic covering 패턴 탐지 — 특정 카테고리에 유사 description 도구가 급증하는 이상 탐지

## 관련 research 문서

- [evaluation-metrics.md](../research/evaluation-metrics.md) — 참고 논문 목록에 ToolFlood 포함
