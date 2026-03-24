# ADR-0006: 평가 지표 세트 — Option B

**Date**: 2026-03-24
**Status**: accepted
**Deciders**: 프로젝트 설계 단계

## Context

MCP Tool 추천 파이프라인의 품질을 측정할 지표 세트를 선택해야 한다.
지표가 너무 적으면 파이프라인의 실제 동작을 충분히 설명하지 못하고, 너무 많으면 5주 프로젝트에서 구현 비용이 과도해진다.
CTO에게 "모니터링 → 개선 루프" 스토리를 수치로 증명해야 한다.

## Decision

Precision@1, Recall@K, Confusion Rate, ECE(Expected Calibration Error)를 핵심 지표로 채택한다 (Option B). Latency는 부가 지표로 기록한다.

## Alternatives Considered

### Alternative A: 핵심만 (Precision@1, Recall@K, Latency)
- **Pros**: 구현 최소, TREC 표준 + RAG-MCP 논문 동일 사용
- **Cons**: Confidence 분기(ADR-0005)의 품질을 측정하는 지표 없음
- **Why not**: ECE 없이는 Confidence 분기 효과 검증 불가

### Alternative C: 풀 세트 (B + MRR, Cost/Correct, DQS 상관관계)
- **Pros**: 가장 포괄적, RAGAS(EACL 2024) 기준
- **Cons**: 5주 프로젝트에서 구현 비용 대비 추가 설득력 낮음
- **Why not**: MRR은 Top-K 전체 순위 품질 측정으로 현 scope 초과

## Consequences

### Positive
- Precision@1: North Star 지표(≥50% 목표) — CTO 핵심 관심사
- Recall@K: Top-K에 정답이 포함되는지 — 파이프라인 상한선 확인
- Confusion Rate: 유사 Tool 간 혼동 빈도 — "왜 틀렸나" 분석
- ECE: Confidence 점수 신뢰도 — gap 기반 분기(ADR-0005) 품질 검증

### Negative
- ECE 계산에 Ground Truth Confidence label 추가 필요
- Option A보다 구현 공수 증가

### Risks
- ECE calibration 데이터가 부족하면 신뢰할 수 없는 수치 → Ground Truth 설계 시 Confidence label 포함 필수
