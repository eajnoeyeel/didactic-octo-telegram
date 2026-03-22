# Tool Selection & Retrieval 전략 조사

> 최종 업데이트: 2026-03-22
> 조사 목적: 2-Stage Retrieval Pipeline의 검색 전략 결정 (DP3)

---

## 해결하려는 기능/문제

`find_best_tool(query)` — 수천 개 MCP Tool 중 최적 Tool을 추천하는 검색 파이프라인 설계. 핵심 질문: "어떤 검색 전략이 Precision@1을 가장 높이는가?"

## 검토한 논문/자료 목록

| 논문 | 파일 | 핵심 기여 |
|------|------|-----------|
| RAG-MCP | [rag-mcp-analysis-ko.md](../papers/rag-mcp-analysis-ko.md) | Dense vector retrieval로 Tool 선택 정확도 13% → 43% 향상. 우리 파이프라인의 primary baseline |
| ToolLLM | [toolllm-analysis-ko.md](../papers/toolllm-analysis-ko.md) | 16,464개 실제 API 규모에서 Neural API Retriever + Recall@K 평가. 대규모 검색 방법론 참고 |
| JSPLIT | [jsplit-analysis-ko.md](../papers/jsplit-analysis-ko.md) | Taxonomy-gated retrieval — 인텐트 분류 후 카테고리 내 검색. Latency 절감 효과 |
| ART | [art-analysis-ko.md](../papers/art-analysis-ko.md) | 자동 추론 + 도구 선택 — 태스크 라이브러리 기반 멀티스텝 추론 |
| Toolformer | [toolformer-analysis-ko.md](../papers/toolformer-analysis-ko.md) | 모델 내부 도구 사용 정책 — 외부 검색 기반 접근과의 대비 참고 |

## 각 자료에서 가져온 핵심 포인트

- **RAG-MCP**: Dense embedding + Qdrant 기반 retrieval이 baseline keyword 검색 대비 3배 정확. MCP 메타데이터(서버명, Tool명, description)를 임베딩 입력으로 사용하는 구조 직접 참고.
- **ToolLLM**: API Retriever를 Recall@K로 독립 평가하는 방법론. 16K 규모에서 검증된 retrieval → reranking 2단계 구조.
- **JSPLIT**: 인텐트 분류 → 카테고리별 서브인덱스 검색. 검색 범위 축소로 latency 절감. 단, 카테고리 경계가 모호한 쿼리에서 치명적 오류 가능.
- **ART**: 검색이 아닌 추론 기반 접근. 태스크 라이브러리에서 유사 사례를 찾아 실행 계획 생성. 우리 프로젝트와 직접 적용보다는 "검색 실패 시 대안" 관점에서 참고.
- **Toolformer**: 모델이 자체적으로 도구 사용 시점을 결정. 외부 retrieval 파이프라인과의 근본적 차이점 이해용.

## 후보 접근 방식 비교

| 전략 | 방법 | 장점 | 단점 | 논문 근거 |
|------|------|------|------|-----------|
| **A: Sequential** | 서버 인덱스 → 필터 → Tool 검색 | 직관적, 서버 수준 분석 가능 | Layer 1 누락 시 복구 불가 | RAG-MCP 파이프라인 구조 참고 |
| **B: Parallel** | 서버 + Tool 병렬 검색 → RRF 합산 | Layer 1 실패에 강건 | 검색 범위 넓음, Latency↑ | ToolLLM의 dual-retrieval 참고 |
| **C: Taxonomy-gated** | 인텐트 분류 → 카테고리 내 검색 | 검색 범위 축소, 정밀도↑ | 분류 오류 시 전체 실패 | JSPLIT 직접 적용 |

## 채택안 / 제외안

**채택**: Strategy Pattern — 3개 전략 모두 구현하되 `PipelineStrategy` ABC 뒤에 놓고, E1 실험으로 최적 전략 결정
- 우선순위: A(Sequential) → B(Parallel) → C(Taxonomy-gated, CTO 확인 후)

**제외**: 단일 전략 하드코딩 — 규모(50-100 서버)에서 어떤 전략이 최적인지 사전에 판단 불가

## 판단 근거

1. RAG-MCP의 43% 정확도가 baseline이지만, 우리 2-Layer 구조(서버→Tool)에서 직접 재현 필요
2. JSPLIT의 latency 이점은 매력적이나, 인텐트 분류기 훈련 데이터/시간 부족 → CTO 확인 후 결정
3. 50-100 서버 규모에서는 1-Layer도 충분할 수 있음 → E0 실험으로 2-Layer 유효성 먼저 검증 (OQ-5)

## 프로젝트 반영 방식

- `src/pipeline/strategy.py`: PipelineStrategy ABC + StrategyRegistry
- `src/pipeline/sequential.py`: Strategy A (Phase 3)
- `src/pipeline/parallel.py`: Strategy B (Phase 7)
- `src/pipeline/taxonomy_gated.py`: Strategy C (Phase 13, gated)
- E0 실험: 1-Layer vs 2-Layer 아키텍처 검증 → E1 전략 비교의 전제 조건

## 관련 papers

- [RAG-MCP](../papers/rag-mcp-analysis-ko.md)
- [ToolLLM](../papers/toolllm-analysis-ko.md)
- [JSPLIT](../papers/jsplit-analysis-ko.md)
- [ART](../papers/art-analysis-ko.md)
- [Toolformer](../papers/toolformer-analysis-ko.md)
