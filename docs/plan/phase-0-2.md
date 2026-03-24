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
5. `src/models.py` 구현 (실제 구현 기준):
   - `TOOL_ID_SEPARATOR = "::"` — qualifiedName에 `/` 포함되므로 `::` 사용
   - `MCPServerSummary`: qualified_name, display_name, description, use_count, is_verified, is_deployed
   - `MCPTool`: tool_id (`server_id::tool_name`), server_id, tool_name, description, input_schema
     - `@computed_field parameter_names` — input_schema에서 추출
     - `@field_validator tool_id` — f"{server_id}{TOOL_ID_SEPARATOR}{tool_name}" 강제
   - `MCPServer`: server_id, name, description, homepage, tools
   - `SearchResult`: tool, score, rank, reason
   - `FindBestToolRequest`: query, top_k=3, strategy="sequential"
   - `FindBestToolResponse`: query, results, confidence, disambiguation_needed, strategy_used, latency_ms
   - `GroundTruthEntry`: query, correct_server_id, correct_tool_id, difficulty, manually_verified
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

### 산출물 (실제 구현 — 3모듈로 분리)
- file: `src/data/smithery_client.py`  — Smithery API HTTP 클라이언트 (async context manager)
- file: `src/data/server_selector.py`  — 필터링 + 정렬 + 큐레이션 유틸리티
- file: `src/data/crawler.py`          — SmitheryCrawler 오케스트레이터 (save/load JSONL)
- file: `src/data/mcp_connector.py`   — Direct MCP 연결 (인터페이스만, Phase 4+)
- file: `tests/unit/test_smithery_client.py`
- file: `tests/unit/test_server_selector.py`
- file: `tests/unit/test_crawler.py`
- file: `tests/unit/test_mcp_connector.py`
- file: `scripts/collect_data.py`

### 구현 단계 (실제 구현)

**Task 1.1: SmitheryClient** — Smithery API 2단계 fetch (List API에 tools 없음)
1. `src/data/smithery_client.py`:
   - `async with SmitheryClient(base_url) as client:` (httpx.AsyncClient 공유)
   - `fetch_server_list(page, page_size=50)` → summaries + pagination meta
   - `fetch_all_summaries(max_pages=10)` → `list[MCPServerSummary]`
   - `fetch_server_detail(qualified_name)` → `MCPServer` (tools 포함)
   - 429/5xx 재시도 (max 3, exponential backoff)
   - `parse_server_summary(raw)`, `parse_server_detail(raw)` static methods

**Task 1.2: ServerSelector** — 크롤링 대상 선정 로직
1. `src/data/server_selector.py`:
   - `filter_deployed(summaries)` — is_deployed=True만
   - `sort_by_popularity(summaries)` — use_count desc
   - `load_curated_list(path)` — 빈 줄 + `#` 주석 무시
   - `select_servers(summaries, curated_list, max_servers, require_deployed)`

**Task 1.3: SmitheryCrawler** — 오케스트레이터
1. `src/data/crawler.py`:
   - `crawl(max_pages, curated_list, max_servers)` → `list[MCPServer]`
   - `save(servers, output_dir)` → JSONL (model_dump_json)
   - `load(path)` static → `list[MCPServer]` (model_validate_json)

**Task 1.4: MCPDirectConnector** — 인터페이스만 (Phase 4+에서 활성화)
1. `src/data/mcp_connector.py`: `fetch_tools()` raises NotImplementedError

**Task 1.5: collect_data.py**

### 완료 기준
- [x] `uv run pytest tests/unit/test_smithery_client.py tests/unit/test_server_selector.py tests/unit/test_crawler.py tests/unit/test_mcp_connector.py -v` PASS
- [x] 커밋: `feat: Smithery crawler with staged fetching` + `feat: MCP direct connector interface`

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
   - `ensure_collection(dimension)` — COSINE distance, 이미 존재하면 skip
   - `upsert_tools(tools, vectors)` — id = `uuid.uuid5(MCP_DISCOVERY_NAMESPACE, tool_id)` (결정적, Python hash() 비결정적 문제 해결)
   - `search(query_vector, top_k, server_id_filter)` → `list[SearchResult]`
   - `generate_point_id(tool_id)` — UUID v5 기반, 고정 namespace `7f1b3d4e-2a5c-4b8f-9e6d-1c0a3f5b7d9e`
3. `src/data/indexer.py`:
   - `index_tools(tools, batch_size=50)` — embed_batch > upsert_tools
4. `scripts/build_index.py`:
   - `data/raw/servers.jsonl` 로드 > embedder 선택 > indexer.index_tools()

### 완료 기준
- [x] `uv run pytest tests/unit/test_embedder.py -v` PASS
- [x] `uv run pytest tests/unit/test_qdrant_store.py -v` PASS
- [x] `uv run pytest tests/ -v` 전체 80개 PASS
- [x] 커밋: `feat: Embedder abstraction + OpenAI embedder` + `feat: Qdrant vector store + indexer`

### 의존성
- Phase 0 완료 필요 (config, models)
- Phase 1 완료 필요 (data/raw/ 데이터)
