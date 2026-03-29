# JSPLIT: Taxonomy-Gated Retrieval for Tool Selection

> 출처: arxiv:2510.14537
> 한 줄 요약: 도구를 카테고리(taxonomy)로 사전 분류한 뒤, 쿼리 인텐트에 맞는 카테고리의 서브 인덱스만 검색하여 latency를 절감하고 정밀도를 높이는 retrieval 전략.

---

## 해결하려는 문제

대규모 도구 풀에서 쿼리에 적합한 도구를 검색할 때, 전체 인덱스를 탐색하면 검색 범위가 넓어 latency가 증가하고 정밀도가 떨어지는 문제를 해결하려 한다. 도구 수가 수백~수천 개로 늘어날 때 검색 효율과 정확도를 동시에 유지하는 방법이 필요하다.

## 핵심 아이디어

- 도구를 사전 정의된 taxonomy(카테고리 체계)로 분류한다.
- 쿼리가 들어오면 먼저 LLM 기반 분류 프롬프트가 해당 쿼리의 카테고리를 판별한다(전용 intent classifier가 아닌 LLM 프롬프트 방식).
- 판별된 카테고리에 해당하는 서브 인덱스(sub-index)만 검색하여 검색 범위를 대폭 축소한다.
- 이를 통해 토큰 비용을 줄이면서 도구 선택 정확도를 유지하거나 향상시킨다.

## 방법론

상세 분석 추가 예정

## 주요 결과

- 토큰 비용 절감과 도구 선택 정확도를 핵심 metric으로 보고하며, taxonomy-gated 접근법의 프롬프트 축소 효과를 실증
- 카테고리 분류의 정확성이 전체 파이프라인 성능에 영향을 미침을 확인

## 장점

- 검색 범위 축소 → latency 절감과 정밀도 향상을 동시에 달성
- 대규모 도구 풀에서 scalability 확보에 유리

## 한계

- 카테고리 분류(intent classification) 오류 시 전체 파이프라인이 실패할 수 있음
- 도메인 간 경계가 모호한 도구의 분류가 어려움
- Taxonomy 설계 자체가 수동 작업이 필요할 수 있음

## 프로젝트 시사점

MCP Discovery Platform의 Strategy C (Taxonomy-Gated) 전략의 직접적인 이론적 근거이다. 현재 아키텍처(architecture.md)에서 3가지 검색 전략(A: Sequential, B: Parallel, C: Taxonomy-Gated)을 비교하도록 설계되어 있으며, Strategy C가 바로 JSPLIT 논문의 접근법에 기반한다.

JSPLIT의 토큰 비용 절감 관점은 우리 아키텍처의 효율성 설계에 참고가 된다. 다만 Latency p50/p95/p99(Metric #6)는 JSPLIT 논문이 직접 다루는 지표가 아니며, 프로젝트 자체 설계이다.

## 적용 포인트

- **Strategy C (Taxonomy-Gated)**: JSPLIT의 taxonomy-gated retrieval을 MCP 서버/도구 카테고리에 적용. CTO 확인 후 구현 예정
- **토큰 비용 절감**: JSPLIT의 taxonomy-gated 접근이 프롬프트 크기를 줄여 비용 효율성을 높이는 방식 참고. Latency p50/p95/p99(Metric #6)는 논문이 직접 보고하는 지표가 아니라 프로젝트 자체 설계임에 유의
- **LLM 기반 카테고리 분류**: 쿼리 카테고리 판별 시 JSPLIT의 LLM 프롬프트 기반 분류 방식 참고 (전용 intent classifier가 아닌 LLM 분류)
- **검색 전략 비교 실험**: Strategy A/B/C의 latency + precision 트레이드오프 분석

## 관련 research 문서

- [evaluation-metrics.md](../research/evaluation-metrics.md) — 토큰 비용 절감 및 검색 전략 비교 참고
