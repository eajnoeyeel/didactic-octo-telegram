# Coding Standards — MCP Discovery Platform

## Tech Stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.12 (type hints 필수) |
| Package Manager | uv |
| Web Framework | FastAPI |
| Vector Store | Qdrant Cloud (free tier) |
| Embedding | BGE-M3 or OpenAI text-embedding-3-small |
| Reranker | Cohere Rerank 3 |
| Validation | Pydantic v2 |
| Testing | pytest + pytest-asyncio (asyncio_mode="auto") |
| Linter/Formatter | ruff |
| LLM Tracing | Langfuse |
| Experiment Tracking | Weights & Biases |

## Mandatory Requirements

### 1. Tests Are Required

NO CODE WITHOUT TESTS. TDD mandatory.

```bash
uv run pytest tests/ -v
uv run pytest tests/ --cov=src -v
```

```
tests/
├── conftest.py
├── unit/              # 모듈별 단위 테스트
├── integration/       # Qdrant + Cohere 실제 연동 (API key 없으면 skip)
└── evaluation/        # E2E 평가 하네스 테스트
```

Integration tests with external APIs: `@pytest.mark.skipif(not os.getenv("COHERE_API_KEY"))`.

### 2. Type Hints on All Functions

```python
async def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
    ...

def compute_precision_at_k(results: list[SearchResult], ground_truth: GroundTruth, k: int = 1) -> float:
    ...
```

### 3. Pydantic v2 for All Data Models

```python
from pydantic import BaseModel, Field

class MCPTool(BaseModel):
    tool_id: str = Field(..., description="서버ID/도구명 형식")
    server_id: str
    tool_name: str
    description: str
    input_schema: dict | None = None
```

Config via `pydantic-settings`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    qdrant_url: str = "http://localhost:6333"
    confidence_gap_threshold: float = 0.15
    top_k_retrieval: int = 10
    top_k_rerank: int = 3
```

### 4. Async/Await for All I/O

```python
# Qdrant
from qdrant_client import AsyncQdrantClient

# OpenAI
from openai import AsyncOpenAI

# HTTP
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get(url)

# WRONG: Blocking I/O
import requests
result = requests.get(url)  # NEVER in async context
```

### 5. Logging: loguru Only

```python
from loguru import logger

logger.info(f"Indexed {count} tools to Qdrant")
logger.warning(f"Low confidence gap: {gap:.3f}")
logger.error(f"Cohere rerank failed: {e}", exc_info=True)

# FORBIDDEN
print(f"debug: {data}")          # NEVER
import logging                   # NEVER
logger.debug(f"...")             # Remove after fix
```

Never log: API keys, embedding vectors, full query payloads.

### 6. No Lazy Imports

ALL imports at file top. Only exception: `TYPE_CHECKING` block.

### 7. Error Handling

```python
# Qdrant errors
try:
    results = await qdrant.search(query_vector, collection, top_k)
except Exception as e:
    logger.error(f"Qdrant search failed: {e}")
    raise

# Cohere errors
try:
    reranked = await cohere_client.rerank(query=query, documents=docs)
except Exception as e:
    logger.warning(f"Cohere rerank failed, using LLM fallback: {e}")
    reranked = await llm_fallback.rerank(query, docs)

# External API (Smithery crawler)
async with httpx.AsyncClient() as client:
    response = await client.get(url, timeout=10.0)
    response.raise_for_status()
```

## Naming Conventions

| Target | Convention | Example |
|--------|-----------|---------|
| Variables/Functions | snake_case | `search_results`, `compute_precision_at_k` |
| Classes | PascalCase | `PipelineStrategy`, `CohereReranker` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_TOP_K`, `CONFIDENCE_THRESHOLD` |
| Files | snake_case | `qdrant_store.py`, `cohere_reranker.py` |
| Test files | `test_` prefix | `test_qdrant_store.py` |

## Commands

```bash
# Package management
uv sync                          # Install dependencies
uv add <package>                 # Add dependency

# Run server
uv run uvicorn src.api.main:app --reload

# Tests
uv run pytest tests/ -v
uv run pytest tests/unit/ -v
uv run pytest tests/ --cov=src -v

# Lint/Format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Scripts
uv run python scripts/collect_data.py
uv run python scripts/build_index.py --pool-size 50
uv run python scripts/generate_ground_truth.py
uv run python scripts/run_experiments.py --experiment E1
```

## Code Review Checklist

- [ ] Tests written and passing
- [ ] Type hints on all functions
- [ ] Pydantic models for data boundaries
- [ ] Async/await for all I/O
- [ ] loguru only (no print, no logging, no debug left)
- [ ] ABC patterns followed (Embedder, Reranker, PipelineStrategy, Evaluator)
- [ ] No hardcoded values (use config.py)
- [ ] No sensitive data in logs
- [ ] Error handling for external APIs (Qdrant, Cohere, OpenAI)
- [ ] No blocking I/O in async functions
