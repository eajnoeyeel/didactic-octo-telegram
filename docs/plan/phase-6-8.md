# Phase 6-8: Reranker, Hybrid Search, FastAPI

> 상위 문서: [implementation.md](implementation.md)

---

## Phase 6: Reranker

### 목표
- Cohere Rerank 3 파이프라인 통합 + 저신뢰 케이스 LLM fallback

### 산출물
- file: `src/reranking/base.py`
- file: `src/reranking/cohere_reranker.py`
- file: `src/reranking/llm_fallback.py`
- file: `tests/unit/test_reranker.py`

### 구현 단계

1. 실패 테스트 (`test_reranker.py`):
   - `Reranker`는 ABC
   - Cohere mock: `rerank()` 호출 시 index 기준 재정렬 검증
     - mock response: index=1 score=0.95, index=0 score=0.72 → 첫 번째 결과가 c/d
2. `src/reranking/base.py`:
   - `Reranker(ABC)`: `rerank(query, results, top_n) -> list[SearchResult]`
3. `src/reranking/cohere_reranker.py`:
   - `CohereReranker(client, api_key)`
   - `AsyncClientV2`, model=`rerank-v3.5`
   - docs = `"{tool_name}: {description}"` 형식
   - `model_copy(update={"score": relevance_score, "rank": i+1})`
4. `src/reranking/llm_fallback.py`:
   - `LLMFallbackReranker(client, model="gpt-4o-mini")`
   - 저신뢰 케이스 전용 (Cross-Encoder gap 작을 때)
   - 프롬프트: 후보 번호 나열 > LLM이 relevance 순서 출력 (쉼표 구분)
5. **SequentialStrategy에 Reranker 연결** (`src/pipeline/sequential.py` 수정):
   - `__init__`에 `reranker: Optional[Reranker]` 추가
   - `execute()`에서 store.search 후: reranker 있으면 rerank, 없으면 slice

### 완료 기준
- [ ] `uv run pytest tests/unit/test_reranker.py -v` PASS
- [ ] SequentialStrategy에 reranker 주입 시 정상 동작
- [ ] 커밋: `feat: Cohere Rerank 3 + LLM fallback reranker`

### 의존성
- Phase 3 완료 필요 (SequentialStrategy)

---

## Phase 7: Hybrid Search (RRF + BGE-M3)

### 목표
- RRF 기반 dense+sparse 하이브리드 검색 + Strategy B (Parallel) 추가

### 산출물
- file: `src/retrieval/hybrid.py`
- file: `src/pipeline/parallel.py`
- file: `tests/unit/test_hybrid.py`

### 구현 단계

1. 실패 테스트 (`test_hybrid.py`):
   - `rrf_score(rank=1, k=60)` == 1/61
   - `merge_results(dense, sparse)`: 양쪽 리스트에 모두 등장하는 "b"가 최상위
2. `src/retrieval/hybrid.py`:
   - `rrf_score(rank, k=60) -> float`: `1.0 / (k + rank)`
   - `merge_results(*result_lists, k=60, top_n=10) -> list[SearchResult]`
     - tool_id별 RRF score 합산 > 정렬 > top_n 반환
3. `src/pipeline/parallel.py` (Strategy B):
   - `ParallelStrategy(embedder, store, reranker=None)`
   - `execute()`:
     - embed query
     - `asyncio.gather`: server index 검색 (top_k=5) + tool index 검색 (top_k_retrieval)
     - `merge_results()` 로 RRF 합산
     - reranker 있으면 rerank
     - confidence 계산 + 응답 반환

### 완료 기준
- [ ] `uv run pytest tests/unit/test_hybrid.py -v` PASS
- [ ] ParallelStrategy가 StrategyRegistry에 등록 가능
- [ ] 커밋: `feat: RRF fusion + Strategy B (parallel dual-index)`

### 의존성
- Phase 2 완료 필요 (qdrant_store, embedder)
- Phase 6 완료 필요 (reranker — optional이지만 통합 권장)

---

## Phase 8: FastAPI + MCP Tool Server

### 목표
- `find_best_tool` REST endpoint 실행 가능, MCP Tool 인터페이스

### 산출물
- file: `src/api/main.py`
- file: `src/api/routes/search.py`
- file: `tests/integration/test_api.py`

### 구현 단계

1. 실패 테스트 (`tests/integration/test_api.py`):
   - `strategy_registry` patch > mock strategy > `TestClient(app)`
   - `POST /search` with `{"query": "search the web", "top_k": 3}` → 200, query/results/confidence 필드 존재
2. `src/api/routes/search.py`:
   - `APIRouter()`, `POST /search`
   - `StrategyRegistry.get(request.strategy)` > `strategy.execute(request)`
3. `src/api/main.py`:
   - `FastAPI(title="MCP Discovery API", version="0.1.0")`
   - `search_router` include
   - `GET /health` → `{"status": "ok"}`
   - `strategy_registry = StrategyRegistry` (module-level ref for test patching)
4. 서버 시작 검증:

```bash
uv run uvicorn src.api.main:app --reload --port 8000
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "search the web", "top_k": 3}'
```

### 완료 기준
- [ ] `uv run pytest tests/integration/test_api.py -v` PASS
- [ ] `GET /health` → 200
- [ ] `POST /search` → 200 with 올바른 response schema
- [ ] 커밋: `feat: FastAPI search endpoint`

### 의존성
- Phase 3 완료 필요 (PipelineStrategy, StrategyRegistry)
