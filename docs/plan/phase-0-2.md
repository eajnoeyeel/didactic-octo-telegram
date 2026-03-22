# Phase 0-2: Foundation, Data Collection, Embedding & Vector Store

> 상위 문서: [implementation.md](implementation.md)

---

## Phase 0: Project Foundation

### 목표
- 실행 가능한 프로젝트 스켈레톤 (config, models, smoke test 통과)

### 산출물
- file: `pyproject.toml`
- file: `src/config.py`
- file: `src/models.py`
- file: `.env.example`
- file: `tests/unit/test_config.py`

### 구현 단계

1. `uv init --no-readme` 후 `pyproject.toml` 설정
   - dependencies: fastapi, uvicorn, pydantic, pydantic-settings, qdrant-client, cohere, openai, httpx, python-dotenv, langfuse, wandb, scipy, numpy
   - dev: pytest, pytest-asyncio, pytest-cov, ruff
   - `[tool.pytest.ini_options]`: asyncio_mode="auto", testpaths=["tests"], pythonpath=["src"]
2. `uv sync --extra dev`
3. 실패 테스트 작성 (`tests/unit/test_config.py`):
   - `Settings()` defaults 검증: `qdrant_url`, `confidence_gap_threshold=0.15`, `top_k_retrieval=10`, `top_k_rerank=3`
4. `src/config.py` 구현: `BaseSettings` + `SettingsConfigDict(env_file=".env", extra="ignore")`
   - 필드: qdrant_url/api_key, collection names, openai/cohere/langfuse keys, embedding_model, top_k_*, confidence_gap_threshold
5. `src/models.py` 구현:
   - `MCPTool`: tool_id, server_id, tool_name, description, parameters, input_schema
   - `MCPServer`: server_id, name, description, homepage, tools
   - `SearchResult`: tool, score, rank, reason
   - `FindBestToolRequest`: query, top_k=3, strategy="sequential"
   - `FindBestToolResponse`: query, results, confidence, disambiguation_needed, strategy_used, latency_ms
   - `GroundTruth`: query, correct_server_id, correct_tool_id, difficulty, manually_verified
6. `touch src/__init__.py`
7. `.env.example` 작성

### 완료 기준
- [ ] `uv run pytest tests/unit/test_config.py -v` PASS
- [ ] `src/models.py`의 모든 모델 import 가능
- [ ] 커밋: `feat: project foundation — config, models, deps`

---

## Phase 1: Data Collection

### 목표
- `data/raw/` 에 MCP server + tool JSON 수집. 재수집 스크립트 포함.

### 산출물
- file: `src/data/crawler.py`
- file: `src/data/mcp_connector.py`
- file: `tests/unit/test_crawler.py`
- file: `tests/unit/test_mcp_connector.py`
- file: `scripts/collect_data.py`

### 구현 단계

**Task 1.1: Smithery Crawler**
1. 실패 테스트 (`test_crawler.py`): `SmitheryCrawler.parse_server(raw)` → `MCPServer` 검증
2. `src/data/crawler.py` 구현:
   - `SMITHERY_API = "https://registry.smithery.ai/servers"`
   - `parse_server(raw: dict) -> MCPServer`
   - `fetch_page(client, page, page_size=50) -> list[dict]`
   - `crawl(max_pages=10) -> list[MCPServer]` (0.5s rate limit)
   - `save(servers) -> Path` (JSONL 형식)

**Task 1.2: Direct MCP Connector**
1. 실패 테스트 (`test_mcp_connector.py`): `parse_tools(server_id, response)` → `list[MCPTool]` 검증
   - tool_id = `"{server_id}/{tool_name}"` 형식 확인
2. `src/data/mcp_connector.py` 구현:
   - `parse_tools(server_id, response) -> list[MCPTool]`
   - `fetch_tools(server_id, endpoint_url) -> list[MCPTool]` (JSON-RPC `tools/list` 호출)
3. `scripts/collect_data.py`: crawler.crawl() > crawler.save()

### 완료 기준
- [ ] `uv run pytest tests/unit/test_crawler.py -v` PASS
- [ ] `uv run pytest tests/unit/test_mcp_connector.py -v` PASS
- [ ] 커밋: `feat: Smithery registry crawler` + `feat: MCP direct connector + data collection script`

---

## Phase 2: Embedding & Vector Store

### 목표
- Tool description 임베딩 + Qdrant 인덱스 구축 + 검색 가능

### 산출물
- file: `src/embedding/base.py`
- file: `src/embedding/openai_embedder.py`
- file: `src/retrieval/qdrant_store.py`
- file: `src/data/indexer.py`
- file: `tests/unit/test_embedder.py`
- file: `tests/unit/test_qdrant_store.py`
- file: `scripts/build_index.py`

### 구현 단계

**Task 2.1: Embedder 추상화**
1. 실패 테스트 (`test_embedder.py`):
   - `Embedder`는 ABC (`inspect.isabstract(Embedder)`)
   - `OpenAIEmbedder(api_key="fake")` 인스턴스화, model/dimension 검증
2. `src/embedding/base.py`: ABC with `embed_one(text) -> np.ndarray`, `embed_batch(texts) -> list[np.ndarray]`
3. `src/embedding/openai_embedder.py`:
   - `dimension = 1536`, model = `text-embedding-3-small`
   - `AsyncOpenAI` 사용

**Task 2.2: Qdrant Vector Store**
1. 실패 테스트 (`test_qdrant_store.py`):
   - `_tool_to_payload(tool)` → dict 필드 검증
   - `_build_tool_text(tool)` → `"{tool_name}: {description}"` 형식 검증
2. `src/retrieval/qdrant_store.py` 구현:
   - `AsyncQdrantClient` 사용
   - `ensure_collection(collection, dim)` — COSINE distance
   - `upsert_tools(tools, vectors, collection)` — id = `abs(hash(tool_id)) % (2**63)`
   - `search(query_vector, collection, top_k, server_id_filter)` → `list[SearchResult]`
3. `src/data/indexer.py`:
   - `index_tools(tools, batch_size=50)` — embed_batch > upsert_tools
4. `scripts/build_index.py`:
   - `data/raw/servers.jsonl` 로드 > embedder 선택 > indexer.index_tools()

### 완료 기준
- [ ] `uv run pytest tests/unit/test_embedder.py -v` PASS
- [ ] `uv run pytest tests/unit/test_qdrant_store.py -v` PASS
- [ ] 커밋: `feat: Embedder abstraction + OpenAI embedder` + `feat: Qdrant vector store + indexer`

### 의존성
- Phase 0 완료 필요 (config, models)
- Phase 1 완료 필요 (data/raw/ 데이터)
