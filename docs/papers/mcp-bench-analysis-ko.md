# MCP-Bench: MCP 특화 벤치마크

> 출처: arxiv:2508.20453 (2025)
> 한 줄 요약: MCP(Model Context Protocol) 환경에 특화된 도구 선택 및 실행 벤치마크로, MCP 서버/도구의 추천 및 사용 품질을 체계적으로 평가하기 위한 프레임워크.

---

## 해결하려는 문제

기존 도구 사용(tool-use) 벤치마크들은 일반 API나 REST endpoint를 대상으로 하여, MCP 프로토콜 고유의 특성(서버-도구 계층 구조, 스키마 기반 파라미터, 프록시 실행 등)을 반영하지 못한다. MCP 생태계가 성장함에 따라 MCP에 특화된 평가 체계가 필요하다.

## 핵심 아이디어

- MCP 서버와 도구의 계층적 구조를 반영한 벤치마크를 설계한다.
- 도구 선택(tool selection)뿐 아니라 파라미터 생성, 실행 성공률까지 포함하는 종합적 평가를 수행한다.
- Recall@K 등 표준 IR 지표를 MCP 환경에 맞게 적용한다.

## 방법론

상세 분석 추가 예정

## 주요 결과

상세 분석 추가 예정

## 장점

- MCP 프로토콜의 고유한 특성을 반영한 특화 벤치마크 (선행 MCP 벤치마크 유무는 추가 확인 필요)
- 서버 레벨과 도구 레벨을 분리하여 평가할 수 있는 구조

## 한계

상세 분석 추가 예정

## 프로젝트 시사점

MCP Discovery Platform의 2-Layer 추천 구조(Layer 1: 서버, Layer 2: 도구)와 직접적으로 대응하는 벤치마크이다. ToolBench/ToolLLM이 일반 API 검색을 다뤘다면, MCP-Bench는 MCP 프로토콜 환경에서의 도구 선택 품질을 특화하여 평가한다.

우리 metrics-rubric.md의 Layer 2 Tool Recall@K(K=10) 지표에서 MCP-Bench를 직접 논문 근거로 참조하고 있으며, Ground Truth 설계와 실험 설계에서 MCP-Bench의 평가 방식을 참고한다.

## 적용 포인트

- **Tool Recall@K (Metric #2)**: MCP-Bench의 Recall@K 측정 방식을 Layer 2 평가에 적용. K=10으로 Reranker 입력 품질 측정
- **Ground Truth 설계**: MCP-Bench의 쿼리-정답 쌍 형식을 참고하여 seed_set.jsonl 구조 설계
- **실험 설계**: MCP 특화 시나리오(서버 계층 구조, 스키마 기반 매칭)를 포함한 테스트 케이스 설계
- **벤치마크 비교**: 우리 시스템의 성능을 MCP-Bench 결과와 간접적으로 비교 가능

## 관련 research 문서

- [evaluation-metrics.md](../research/evaluation-metrics.md) — Tool Recall@K 논문 근거
