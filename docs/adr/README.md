# Architecture Decision Records

이 디렉토리는 MCP Discovery Platform의 주요 아키텍처 결정을 기록한다.
새로운 결정을 추가할 때는 `template.md`를 복사해 사용한다.

| ADR | 제목 | 상태 | 날짜 |
|-----|------|------|------|
| [0001](0001-bridge-mcp-server-static-2-tool-proxy.md) | Bridge MCP Server — Static 2-Tool Proxy | accepted | 2026-03-24 |
| [0002](0002-2-layer-recommendation-architecture.md) | 2-Layer 추천 아키텍처 (서버 → Tool) | accepted | 2026-03-24 |
| [0003](0003-pipeline-strategy-pattern.md) | Pipeline Strategy Pattern 적용 | accepted | 2026-03-24 |
| [0004](0004-qdrant-cloud-vector-store.md) | 벡터 스토어 — Qdrant Cloud Free Tier | accepted | 2026-03-24 |
| [0005](0005-gap-based-confidence-branching.md) | Gap 기반 Confidence 분기 방식 | accepted | 2026-03-24 |
| [0006](0006-evaluation-metric-set.md) | 평가 지표 세트 — Option B | accepted | 2026-03-24 |
| [0007](0007-tool-id-separator.md) | Tool ID 구분자 — `::` | accepted | 2026-03-24 |
| [0008](0008-data-source-strategy.md) | 데이터 소스 전략 — 큐레이션 + Synthetic | partially superseded by 0011 | 2026-03-24 |
| [0009](0009-auxiliary-tool-stack.md) | 보조 도구 스택 | accepted | 2026-03-24 |
| [0010](0010-server-description-source-for-embedding.md) | 서버 Description 소스 — 임베딩용 | accepted (data source updated by 0011, core concern open) | 2026-03-27 |
| [0011](0011-external-dataset-strategy.md) | 외부 데이터셋(MCP-Zero, MCP-Atlas) 활용 전략 | accepted | 2026-03-28 |
| [0012](0012-per-step-ground-truth-decomposition.md) | MCP-Atlas Per-Step Single-Tool GT 분해 | accepted | 2026-03-29 |

## 상속/대체 관계

- **ADR-0008 → ADR-0011**: 데이터 소스 전략이 Smithery 큐레이션에서 MCP-Zero + MCP-Atlas로 전환. 0008의 Pool/GT 부분은 0011로 대체됨.
- **ADR-0011 → ADR-0012**: MCP-Atlas 활용 방식을 multi-label에서 per-step single-tool 분해로 구체화.

## 실험 결과 후 추가 예정

| 결정 사항 | 관련 실험 | 예상 ADR 번호 |
|----------|----------|-------------|
| Pipeline 전략 선택 (A/B/C) | E1 | 0013 |
| 임베딩 모델 선택 | E2 | 0014 |
| Reranker 선택 | E3 | 0015 |
| Confidence 임계값 최종값 | E2/E3 | ADR-0005 갱신 |
