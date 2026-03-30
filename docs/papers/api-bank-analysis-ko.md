# API-Bank 분석 노트

> 73개 API 도구와 314개 대화로 구성된 실행 가능한 벤치마크를 통해, 도구 사용 능력을 planning/retrieval/calling 3단계로 분리 평가하는 체계를 제시한 연구.

## 기본 정보

- 논문: [API-Bank: A Comprehensive Benchmark for Tool-Augmented LLMs](https://arxiv.org/abs/2304.08244)
- 최초 제출일: 2023-04-14
- 최신 arXiv 개정 확인일: v2, 2023-10-25
- 저자: Minghao Li 외

## 무엇을 해결하려는가

API-Bank는 tool-augmented LLM을 평가할 때 표준 benchmark가 부족하다는 문제를 다룬다. 논문이 직접 제시한 핵심 질문은 아래 3개다.

1. 현재 LLM은 도구 사용을 얼마나 잘하는가
2. 어떻게 더 잘하게 만들 수 있는가
3. 어떤 장애물이 남아 있는가

## 핵심 아이디어

- 73개 API 도구로 실행 가능한 평가 시스템을 만든다.
- 314개 dialogue, 753개 API call을 수작업으로 정리해 `planning`, `retrieving`, `calling`을 평가한다.
- 추가로 2,138개 API와 1,888개 tool-use dialogue로 학습 데이터도 제공한다.
- Alpaca 기반 도구 사용 모델 `Lynx`를 훈련해 benchmark와 training set을 함께 제시한다.

API-Bank의 강점은 “도구 사용 능력”을 `planning / retrieval / calling`으로 분리해 본다는 점이다.

## 우리 프로젝트에 중요한 이유

이 논문은 우리 프로젝트 1번 축인 `선택 기준 정의 및 평가 체계 구축`에 가장 직접적으로 연결된다.

- 추천 문제를 단순 accuracy 하나로 보지 않는다.
- retrieval과 calling을 따로 본다.
- 실행 가능한 benchmark 구조를 제공한다.

MCP 추천 최적화에서도 아래 분리가 필요하다.

- 후보를 잘 찾았는가
- 올바른 MCP를 골랐는가
- 인자와 호출이 맞았는가
- 전체 task가 성공했는가

## 4대 프로젝트 축에 주는 시사점

### 1. 선택 기준/평가 체계

- 평가 지표는 최소한 `planning`, `retrieval`, `calling`, `task success`로 나눠야 한다.
- 정답 기준도 `단일 정답`보다 단계별 정답을 허용하는 구조가 바람직하다.

### 2. 추천 최적화

- metadata 검색만으로는 부족하고, 호출 가능성과 인자 적합성까지 봐야 한다.

### 3. 로그 기반 개선

- 실제 로그에서도 planning error, retrieval error, invocation error를 따로 레이블링할 필요가 있다.

### 4. 운영/품질 게이트

- 도구 등록 시 runnable spec과 schema 정합성 검사가 필요하다는 시사점을 준다.

## 한계

- MCP 고유의 registry, deployment, compatibility 문제는 다루지 않는다.
- 운영 자동화보다 benchmark 설계에 집중한다.
- 실제 프로덕션 로그 기반 feedback loop는 범위 밖이다.

## 현재 판단

- 분류: `평가 체계 핵심 논문`
- 프로젝트 활용도: 매우 높음
- 역할: `MCP 추천 benchmark 분해 구조`의 직접 참고자료
- 최종 프로젝트 반영 포인트:
  - 평가 축 분리
  - runnable benchmark 설계
  - tool-use 오류 taxonomy 초안 (논문이 명시적 오류 taxonomy를 제공하는지는 본문 확인 필요 — abstract에서는 planning/retrieval/calling 분리 평가만 확인됨)

## 관련 research 문서

- [Evaluation & Benchmark Design 조사](../research/evaluation-benchmark-design.md)
