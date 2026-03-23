# Phase 0-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the project foundation, data collection pipeline, and embedding + vector store — enabling "query -> vector search -> similar tools" by the end of Phase 2.

**Architecture:** 3-module crawler (smithery_client / server_selector / crawler) fetches MCP tool data from Smithery Registry, OpenAI embeds tool descriptions, Qdrant stores vectors for similarity search. All async, Pydantic v2 models, TDD throughout.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic v2, pydantic-settings, httpx, openai (AsyncOpenAI), qdrant-client (AsyncQdrantClient), loguru, pytest + pytest-asyncio, ruff

**Spec:** `docs/superpowers/specs/2026-03-23-phase-0-2-design.md`

---

## Phase 0: Project Foundation

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/data/__init__.py`
- Create: `src/embedding/__init__.py`
- Create: `src/retrieval/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/evaluation/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize project with uv**

```bash
cd /Users/iyeonjae/Desktop/shockwave/mcp-discovery
uv init --no-readme
```

- [ ] **Step 2: Configure pyproject.toml**

```toml
[project]
name = "mcp-discovery"
version = "0.1.0"
description = "MCP Discovery Platform — find the best MCP tool for any query"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "qdrant-client>=1.12.0",
    "openai>=1.60.0",
    "httpx>=0.28.0",
    "python-dotenv>=1.0.0",
    "langfuse>=2.0.0",
    "wandb>=0.19.0",
    "scipy>=1.14.0",
    "numpy>=2.0.0",
    "loguru>=0.7.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.9.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
```

- [ ] **Step 3: Create directory structure and __init__.py files**

```bash
mkdir -p src/data src/embedding src/retrieval tests/unit tests/integration tests/evaluation scripts data/raw data/curation
touch src/__init__.py src/data/__init__.py src/embedding/__init__.py src/retrieval/__init__.py
touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py tests/evaluation/__init__.py
```

Create `tests/conftest.py`:
```python
"""Shared test fixtures for MCP Discovery Platform."""
```

- [ ] **Step 4: Install dependencies**

```bash
uv sync
```

Run: `uv sync`
Expected: All dependencies install without error.

- [ ] **Step 5: Verify pytest runs (empty)**

Run: `uv run pytest --co -q`
Expected: "no tests ran" — confirms pytest config is correct.

---

### Task 2: Config (TDD)

**Files:**
- Create: `tests/unit/test_config.py`
- Create: `src/config.py`
- Create: `.env.example`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_config.py`:
```python
"""Tests for Settings configuration."""

from config import Settings


class TestSettings:
    def test_default_qdrant_url(self):
        settings = Settings()
        assert settings.qdrant_url == "http://localhost:6333"

    def test_default_confidence_gap_threshold(self):
        settings = Settings()
        assert settings.confidence_gap_threshold == 0.15

    def test_default_top_k_retrieval(self):
        settings = Settings()
        assert settings.top_k_retrieval == 10

    def test_default_top_k_rerank(self):
        settings = Settings()
        assert settings.top_k_rerank == 3

    def test_default_embedding_model(self):
        settings = Settings()
        assert settings.embedding_model == "text-embedding-3-small"

    def test_default_embedding_dimension(self):
        settings = Settings()
        assert settings.embedding_dimension == 1536

    def test_default_smithery_api_base_url(self):
        settings = Settings()
        assert settings.smithery_api_base_url == "https://registry.smithery.ai"

    def test_default_qdrant_collection_name(self):
        settings = Settings()
        assert settings.qdrant_collection_name == "mcp_tools"

    def test_optional_fields_default_none(self):
        settings = Settings()
        assert settings.openai_api_key is None
        assert settings.qdrant_api_key is None
        assert settings.cohere_api_key is None
        assert settings.langfuse_public_key is None
        assert settings.langfuse_secret_key is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Implement config.py**

`src/config.py`:
```python
"""Application settings via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Smithery
    smithery_api_base_url: str = "https://registry.smithery.ai"

    # OpenAI (required for Phase 2 embedding, optional for Phase 1 crawling)
    openai_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection_name: str = "mcp_tools"

    # Cohere (Phase 3+)
    cohere_api_key: str | None = None

    # Retrieval
    top_k_retrieval: int = 10
    top_k_rerank: int = 3
    confidence_gap_threshold: float = 0.15

    # Langfuse
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: All tests PASS

- [ ] **Step 5: Create .env.example**

`.env.example`:
```bash
# Required
OPENAI_API_KEY=sk-...

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=mcp_tools

# Embedding
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# Smithery
SMITHERY_API_BASE_URL=https://registry.smithery.ai

# Cohere (Phase 3+)
COHERE_API_KEY=

# Retrieval
TOP_K_RETRIEVAL=10
TOP_K_RERANK=3
CONFIDENCE_GAP_THRESHOLD=0.15

# Langfuse (optional)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .python-version .env.example src/__init__.py src/config.py src/data/__init__.py src/embedding/__init__.py src/retrieval/__init__.py tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py tests/conftest.py tests/unit/test_config.py
git commit -m "feat(foundation): project scaffold + config with TDD"
```

---

### Task 3: Data Models (TDD)

**Files:**
- Create: `tests/unit/test_models.py`
- Create: `src/models.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_models.py`:
```python
"""Tests for data models."""

import pytest

from models import (
    TOOL_ID_SEPARATOR,
    FindBestToolRequest,
    FindBestToolResponse,
    GroundTruthEntry,
    MCPServer,
    MCPServerSummary,
    MCPTool,
    SearchResult,
)


class TestToolIdSeparator:
    def test_separator_is_double_colon(self):
        assert TOOL_ID_SEPARATOR == "::"


class TestMCPServerSummary:
    def test_create_with_defaults(self):
        summary = MCPServerSummary(
            qualified_name="@smithery-ai/github",
            display_name="GitHub MCP",
        )
        assert summary.qualified_name == "@smithery-ai/github"
        assert summary.display_name == "GitHub MCP"
        assert summary.description is None
        assert summary.use_count == 0
        assert summary.is_verified is False
        assert summary.is_deployed is False

    def test_create_full(self):
        summary = MCPServerSummary(
            qualified_name="@smithery-ai/github",
            display_name="GitHub MCP",
            description="GitHub integration",
            use_count=1500,
            is_verified=True,
            is_deployed=True,
        )
        assert summary.use_count == 1500
        assert summary.is_verified is True


class TestMCPServer:
    def test_create_with_defaults(self):
        server = MCPServer(server_id="@smithery-ai/github", name="GitHub MCP")
        assert server.server_id == "@smithery-ai/github"
        assert server.name == "GitHub MCP"
        assert server.description is None
        assert server.homepage is None
        assert server.tools == []

    def test_create_with_tools(self):
        tool = MCPTool(
            server_id="@smithery-ai/github",
            tool_name="search_issues",
            tool_id="@smithery-ai/github::search_issues",
            description="Search GitHub issues",
        )
        server = MCPServer(
            server_id="@smithery-ai/github",
            name="GitHub MCP",
            tools=[tool],
        )
        assert len(server.tools) == 1
        assert server.tools[0].tool_name == "search_issues"


class TestMCPTool:
    def test_create_valid(self):
        tool = MCPTool(
            server_id="@smithery-ai/github",
            tool_name="search_issues",
            tool_id="@smithery-ai/github::search_issues",
            description="Search GitHub issues",
        )
        assert tool.tool_id == "@smithery-ai/github::search_issues"
        assert tool.server_id == "@smithery-ai/github"
        assert tool.tool_name == "search_issues"

    def test_tool_id_validator_rejects_wrong_format(self):
        with pytest.raises(ValueError, match="tool_id must be"):
            MCPTool(
                server_id="@smithery-ai/github",
                tool_name="search_issues",
                tool_id="wrong-format",
            )

    def test_tool_id_validator_rejects_slash_separator(self):
        with pytest.raises(ValueError, match="tool_id must be"):
            MCPTool(
                server_id="@smithery-ai/github",
                tool_name="search_issues",
                tool_id="@smithery-ai/github/search_issues",
            )

    def test_parameter_names_from_input_schema(self):
        tool = MCPTool(
            server_id="srv",
            tool_name="t",
            tool_id="srv::t",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        )
        assert tool.parameter_names == ["query", "limit"]

    def test_parameter_names_empty_when_no_schema(self):
        tool = MCPTool(
            server_id="srv",
            tool_name="t",
            tool_id="srv::t",
        )
        assert tool.parameter_names == []

    def test_parameter_names_empty_when_no_properties(self):
        tool = MCPTool(
            server_id="srv",
            tool_name="t",
            tool_id="srv::t",
            input_schema={"type": "object"},
        )
        assert tool.parameter_names == []


class TestSearchResult:
    def test_create(self):
        tool = MCPTool(
            server_id="srv", tool_name="t", tool_id="srv::t",
        )
        result = SearchResult(tool=tool, score=0.95, rank=1)
        assert result.score == 0.95
        assert result.rank == 1
        assert result.reason is None


class TestFindBestToolRequest:
    def test_defaults(self):
        req = FindBestToolRequest(query="send email")
        assert req.top_k == 3
        assert req.strategy == "sequential"


class TestFindBestToolResponse:
    def test_create(self):
        resp = FindBestToolResponse(
            query="send email",
            results=[],
            confidence=0.85,
            disambiguation_needed=False,
            strategy_used="sequential",
            latency_ms=120.5,
        )
        assert resp.confidence == 0.85


class TestGroundTruthEntry:
    def test_create(self):
        gt = GroundTruthEntry(
            query="search github issues",
            correct_server_id="@smithery-ai/github",
            correct_tool_id="@smithery-ai/github::search_issues",
        )
        assert gt.difficulty is None
        assert gt.manually_verified is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 3: Implement models.py**

`src/models.py`:
```python
"""Core data models for MCP Discovery Platform."""

from pydantic import BaseModel, Field, computed_field, field_validator


TOOL_ID_SEPARATOR = "::"


class MCPServerSummary(BaseModel):
    """Smithery list endpoint summary — no tools."""

    qualified_name: str
    display_name: str
    description: str | None = None
    use_count: int = 0
    is_verified: bool = False
    is_deployed: bool = False


class MCPTool(BaseModel):
    """A single MCP tool with validated tool_id."""

    server_id: str
    tool_name: str
    tool_id: str
    description: str | None = None
    input_schema: dict | None = None

    @computed_field
    @property
    def parameter_names(self) -> list[str]:
        if not self.input_schema:
            return []
        props = self.input_schema.get("properties", {})
        return list(props.keys())

    @field_validator("tool_id")
    @classmethod
    def validate_tool_id(cls, v: str, info) -> str:
        server_id = info.data.get("server_id", "")
        tool_name = info.data.get("tool_name", "")
        expected = f"{server_id}{TOOL_ID_SEPARATOR}{tool_name}"
        if v != expected:
            raise ValueError(f"tool_id must be '{expected}', got '{v}'")
        return v


class MCPServer(BaseModel):
    """MCP server with its tools."""

    server_id: str
    name: str
    description: str | None = None
    homepage: str | None = None
    tools: list[MCPTool] = []


class SearchResult(BaseModel):
    """A single search result from the pipeline."""

    tool: MCPTool
    score: float
    rank: int
    reason: str | None = None


class FindBestToolRequest(BaseModel):
    """API request for tool discovery."""

    query: str
    top_k: int = 3
    strategy: str = "sequential"


class FindBestToolResponse(BaseModel):
    """API response for tool discovery."""

    query: str
    results: list[SearchResult]
    confidence: float
    disambiguation_needed: bool
    strategy_used: str
    latency_ms: float


class GroundTruthEntry(BaseModel):
    """A single ground truth entry for evaluation.

    Simplified model for Phase 0-2. Phase 3+ will extend with:
    query_id, Difficulty/Ambiguity/Category enums, distractors, acceptable_alternatives.
    See docs/design/ground-truth-schema.md for the full schema.
    """

    query: str
    correct_server_id: str
    correct_tool_id: str
    difficulty: str | None = None  # Will become Difficulty enum in Phase 3+
    manually_verified: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/unit/test_models.py
git commit -m "feat(foundation): data models with tool_id :: separator + TDD"
```

---

## Phase 1: Data Collection

### Task 4: SmitheryClient (TDD)

**Files:**
- Create: `tests/unit/test_smithery_client.py`
- Create: `src/data/smithery_client.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_smithery_client.py`:
```python
"""Tests for SmitheryClient — HTTP client for Smithery Registry API."""

import pytest

from data.smithery_client import SmitheryClient
from models import MCPServerSummary, MCPServer, TOOL_ID_SEPARATOR


# --- Fixtures: raw API responses ---

SAMPLE_LIST_ITEM = {
    "qualifiedName": "@anthropic/claude-code",
    "displayName": "Claude Code",
    "description": "AI coding assistant",
    "useCount": 5000,
    "createdAt": "2025-01-01T00:00:00Z",
    "verified": True,
    "isDeployed": True,
}

SAMPLE_LIST_ITEM_MINIMAL = {
    "qualifiedName": "@test/minimal",
    "displayName": "Minimal Server",
}

SAMPLE_DETAIL_RESPONSE = {
    "qualifiedName": "@anthropic/claude-code",
    "displayName": "Claude Code",
    "description": "AI coding assistant",
    "homepage": "https://claude.ai",
    "tools": [
        {
            "name": "run_command",
            "description": "Run a shell command",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                },
            },
        },
        {
            "name": "edit_file",
            "description": "Edit a file",
            "inputSchema": None,
        },
    ],
}

SAMPLE_DETAIL_NO_TOOLS = {
    "qualifiedName": "@test/empty",
    "displayName": "Empty Server",
    "description": "No tools",
}


class TestParseServerSummary:
    def test_full_fields(self):
        result = SmitheryClient.parse_server_summary(SAMPLE_LIST_ITEM)
        assert isinstance(result, MCPServerSummary)
        assert result.qualified_name == "@anthropic/claude-code"
        assert result.display_name == "Claude Code"
        assert result.description == "AI coding assistant"
        assert result.use_count == 5000
        assert result.is_verified is True
        assert result.is_deployed is True

    def test_minimal_fields(self):
        result = SmitheryClient.parse_server_summary(SAMPLE_LIST_ITEM_MINIMAL)
        assert result.qualified_name == "@test/minimal"
        assert result.use_count == 0
        assert result.is_verified is False
        assert result.is_deployed is False


class TestParseServerDetail:
    def test_with_tools(self):
        result = SmitheryClient.parse_server_detail(SAMPLE_DETAIL_RESPONSE)
        assert isinstance(result, MCPServer)
        assert result.server_id == "@anthropic/claude-code"
        assert result.name == "Claude Code"
        assert result.homepage == "https://claude.ai"
        assert len(result.tools) == 2

        tool0 = result.tools[0]
        assert tool0.tool_id == f"@anthropic/claude-code{TOOL_ID_SEPARATOR}run_command"
        assert tool0.tool_name == "run_command"
        assert tool0.description == "Run a shell command"
        assert tool0.input_schema is not None

        tool1 = result.tools[1]
        assert tool1.tool_id == f"@anthropic/claude-code{TOOL_ID_SEPARATOR}edit_file"
        assert tool1.input_schema is None

    def test_no_tools(self):
        result = SmitheryClient.parse_server_detail(SAMPLE_DETAIL_NO_TOOLS)
        assert result.server_id == "@test/empty"
        assert result.tools == []

    def test_tool_id_uses_separator_constant(self):
        result = SmitheryClient.parse_server_detail(SAMPLE_DETAIL_RESPONSE)
        for tool in result.tools:
            assert TOOL_ID_SEPARATOR in tool.tool_id
            parts = tool.tool_id.split(TOOL_ID_SEPARATOR)
            assert len(parts) == 2
            assert parts[0] == "@anthropic/claude-code"


class TestSmitheryClientInit:
    def test_default_rate_limit(self):
        client = SmitheryClient(base_url="https://example.com")
        assert client.rate_limit_seconds == 0.5

    def test_custom_rate_limit(self):
        client = SmitheryClient(base_url="https://example.com", rate_limit_seconds=1.0)
        assert client.rate_limit_seconds == 1.0


class TestFetchAllSummaries:
    async def test_stops_on_empty_page(self):
        client = SmitheryClient(base_url="https://example.com", rate_limit_seconds=0.0)
        # Page 1 returns 2 summaries, page 2 returns empty -> stop
        calls = 0

        async def mock_fetch(page, page_size=50):
            nonlocal calls
            calls += 1
            if page == 1:
                return [
                    SmitheryClient.parse_server_summary(SAMPLE_LIST_ITEM),
                    SmitheryClient.parse_server_summary(SAMPLE_LIST_ITEM_MINIMAL),
                ], {"currentPage": 1, "totalPages": 5}
            return [], {}

        client.fetch_server_list = mock_fetch
        result = await client.fetch_all_summaries(max_pages=10)
        assert len(result) == 2
        assert calls == 2

    async def test_stops_on_max_pages(self):
        client = SmitheryClient(base_url="https://example.com", rate_limit_seconds=0.0)

        async def mock_fetch(page, page_size=50):
            return [SmitheryClient.parse_server_summary(SAMPLE_LIST_ITEM)], {
                "currentPage": page, "totalPages": 100,
            }

        client.fetch_server_list = mock_fetch
        result = await client.fetch_all_summaries(max_pages=3)
        assert len(result) == 3

    async def test_stops_on_last_page(self):
        client = SmitheryClient(base_url="https://example.com", rate_limit_seconds=0.0)

        async def mock_fetch(page, page_size=50):
            return [SmitheryClient.parse_server_summary(SAMPLE_LIST_ITEM)], {
                "currentPage": 2, "totalPages": 2,
            }

        client.fetch_server_list = mock_fetch
        result = await client.fetch_all_summaries(max_pages=10)
        assert len(result) == 1  # Only 1 page fetched (stops at totalPages)


class TestRetryLogic:
    async def test_retries_on_429(self, respx_mock=None):
        """_request_with_retry retries on 429 status code."""
        import httpx
        from respx import MockRouter

        # Integration-style: validate retry behavior conceptually
        # (full integration test requires respx, skip if not installed)
        client = SmitheryClient(base_url="https://example.com", rate_limit_seconds=0.0)
        attempt_count = 0

        async def mock_request(method, url, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise httpx.HTTPStatusError(
                    "Too Many Requests",
                    request=httpx.Request(method, url),
                    response=httpx.Response(429),
                )
            response = httpx.Response(200, json={"servers": [], "pagination": {}})
            return response

        client._get_client().request = mock_request
        await client._request_with_retry("GET", "https://example.com/test")
        assert attempt_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_smithery_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'data.smithery_client'`

- [ ] **Step 3: Implement smithery_client.py**

`src/data/smithery_client.py`:
```python
"""HTTP client for Smithery Registry API."""

import asyncio
import time

import httpx
from loguru import logger

from models import MCPServer, MCPServerSummary, MCPTool, TOOL_ID_SEPARATOR


class SmitheryClient:
    """Smithery Registry API client with rate limiting and retry.

    Use as async context manager to manage httpx client lifecycle:
        async with SmitheryClient(base_url="...") as client:
            summaries = await client.fetch_all_summaries()
    """

    def __init__(self, base_url: str, rate_limit_seconds: float = 0.5) -> None:
        self.base_url = base_url.rstrip("/")
        self.rate_limit_seconds = rate_limit_seconds
        self._last_request_time: float = 0.0
        self._http_client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SmitheryClient":
        self._http_client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args) -> None:
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def _rate_limit(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit_seconds:
            await asyncio.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_time = time.monotonic()

    async def _request_with_retry(
        self, method: str, url: str, max_retries: int = 3, **kwargs
    ) -> httpx.Response:
        client = self._get_client()
        for attempt in range(max_retries):
            await self._rate_limit()
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    delay = (2**attempt) * 1.0
                    logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s: HTTP {e.response.status_code}")
                    await asyncio.sleep(delay)
                else:
                    raise
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < max_retries - 1:
                    delay = (2**attempt) * 1.0
                    logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s: {type(e).__name__}")
                    await asyncio.sleep(delay)
                else:
                    raise

    async def fetch_server_list(
        self, page: int = 1, page_size: int = 50
    ) -> tuple[list[MCPServerSummary], dict]:
        response = await self._request_with_retry(
            "GET", f"{self.base_url}/servers",
            params={"page": page, "pageSize": page_size},
        )
        data = response.json()
        servers = [
            self.parse_server_summary(item) for item in data.get("servers", [])
        ]
        pagination = data.get("pagination", {})
        return servers, pagination

    async def fetch_all_summaries(self, max_pages: int = 10) -> list[MCPServerSummary]:
        all_summaries: list[MCPServerSummary] = []
        for page in range(1, max_pages + 1):
            summaries, pagination = await self.fetch_server_list(page=page)
            if not summaries:
                break
            all_summaries.extend(summaries)
            logger.info(f"Fetched page {page}: {len(summaries)} servers (total: {len(all_summaries)})")
            current = pagination.get("currentPage", page)
            total_pages = pagination.get("totalPages", max_pages)
            if current >= total_pages:
                break
        return all_summaries

    async def fetch_server_detail(self, qualified_name: str) -> MCPServer:
        response = await self._request_with_retry(
            "GET", f"{self.base_url}/servers/{qualified_name}",
        )
        data = response.json()
        return self.parse_server_detail(data)

    @staticmethod
    def parse_server_summary(raw: dict) -> MCPServerSummary:
        return MCPServerSummary(
            qualified_name=raw["qualifiedName"],
            display_name=raw["displayName"],
            description=raw.get("description"),
            use_count=raw.get("useCount", 0),
            is_verified=raw.get("verified", False),
            is_deployed=raw.get("isDeployed", False),
        )

    @staticmethod
    def parse_server_detail(raw: dict) -> MCPServer:
        qualified_name = raw["qualifiedName"]
        raw_tools = raw.get("tools") or []
        tools = [
            MCPTool(
                server_id=qualified_name,
                tool_name=t["name"],
                tool_id=f"{qualified_name}{TOOL_ID_SEPARATOR}{t['name']}",
                description=t.get("description"),
                input_schema=t.get("inputSchema"),
            )
            for t in raw_tools
        ]
        return MCPServer(
            server_id=qualified_name,
            name=raw["displayName"],
            description=raw.get("description"),
            homepage=raw.get("homepage"),
            tools=tools,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_smithery_client.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/data/smithery_client.py tests/unit/test_smithery_client.py
git commit -m "feat(data): SmitheryClient with 2-stage API + rate limiting"
```

---

### Task 5: ServerSelector (TDD)

**Files:**
- Create: `tests/unit/test_server_selector.py`
- Create: `src/data/server_selector.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_server_selector.py`:
```python
"""Tests for server selection and filtering logic."""

from pathlib import Path

import pytest

from data.server_selector import (
    filter_deployed,
    load_curated_list,
    select_servers,
    sort_by_popularity,
)
from models import MCPServerSummary


@pytest.fixture
def sample_summaries() -> list[MCPServerSummary]:
    return [
        MCPServerSummary(
            qualified_name="@a/deployed-popular",
            display_name="A",
            use_count=1000,
            is_deployed=True,
        ),
        MCPServerSummary(
            qualified_name="@b/deployed-less",
            display_name="B",
            use_count=500,
            is_deployed=True,
        ),
        MCPServerSummary(
            qualified_name="@c/not-deployed",
            display_name="C",
            use_count=2000,
            is_deployed=False,
        ),
        MCPServerSummary(
            qualified_name="@d/deployed-least",
            display_name="D",
            use_count=100,
            is_deployed=True,
        ),
    ]


class TestFilterDeployed:
    def test_filters_non_deployed(self, sample_summaries):
        result = filter_deployed(sample_summaries)
        assert len(result) == 3
        assert all(s.is_deployed for s in result)

    def test_empty_input(self):
        assert filter_deployed([]) == []


class TestSortByPopularity:
    def test_sorts_descending(self, sample_summaries):
        result = sort_by_popularity(sample_summaries)
        use_counts = [s.use_count for s in result]
        assert use_counts == sorted(use_counts, reverse=True)


class TestLoadCuratedList:
    def test_loads_from_file(self, tmp_path):
        f = tmp_path / "servers.txt"
        f.write_text("@a/server\n@b/server\n\n# comment\n  \n@c/server\n")
        result = load_curated_list(f)
        assert result == ["@a/server", "@b/server", "@c/server"]

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        assert load_curated_list(f) == []


class TestSelectServers:
    def test_default_filters_and_sorts(self, sample_summaries):
        result = select_servers(sample_summaries, max_servers=2)
        assert len(result) == 2
        assert result[0].qualified_name == "@a/deployed-popular"
        assert result[1].qualified_name == "@b/deployed-less"

    def test_curated_list_overrides(self, sample_summaries, tmp_path):
        f = tmp_path / "curated.txt"
        f.write_text("@d/deployed-least\n@c/not-deployed\n")
        result = select_servers(sample_summaries, curated_list=f)
        names = [s.qualified_name for s in result]
        assert "@d/deployed-least" in names
        assert "@c/not-deployed" in names

    def test_max_servers_limit(self, sample_summaries):
        result = select_servers(sample_summaries, max_servers=1)
        assert len(result) == 1

    def test_skip_deployed_filter(self, sample_summaries):
        result = select_servers(sample_summaries, require_deployed=False, max_servers=10)
        assert len(result) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_server_selector.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement server_selector.py**

`src/data/server_selector.py`:
```python
"""Server selection and filtering logic for crawling targets."""

from pathlib import Path

from loguru import logger

from models import MCPServerSummary


def filter_deployed(summaries: list[MCPServerSummary]) -> list[MCPServerSummary]:
    """Return only deployed servers."""
    return [s for s in summaries if s.is_deployed]


def sort_by_popularity(summaries: list[MCPServerSummary]) -> list[MCPServerSummary]:
    """Sort by use_count descending."""
    return sorted(summaries, key=lambda s: s.use_count, reverse=True)


def load_curated_list(path: Path) -> list[str]:
    """Load qualified names from a text file (one per line, # comments ignored)."""
    names: list[str] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            names.append(stripped)
    return names


def select_servers(
    summaries: list[MCPServerSummary],
    curated_list: Path | None = None,
    max_servers: int = 100,
    require_deployed: bool = True,
) -> list[MCPServerSummary]:
    """Select servers for crawling.

    If curated_list is provided, filter to those names only.
    Otherwise: deployed filter -> popularity sort -> truncate.
    """
    if curated_list is not None:
        curated_names = set(load_curated_list(curated_list))
        result = [s for s in summaries if s.qualified_name in curated_names]
        logger.info(f"Curated list: {len(result)}/{len(curated_names)} servers matched")
        return result[:max_servers]

    result = summaries
    if require_deployed:
        result = filter_deployed(result)
    result = sort_by_popularity(result)
    result = result[:max_servers]
    logger.info(f"Selected {len(result)} servers (deployed={require_deployed}, max={max_servers})")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_server_selector.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/data/server_selector.py tests/unit/test_server_selector.py
git commit -m "feat(data): ServerSelector with deployed filter + curation"
```

---

### Task 6: SmitheryCrawler (TDD)

**Files:**
- Create: `tests/unit/test_crawler.py`
- Create: `src/data/crawler.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_crawler.py`:
```python
"""Tests for SmitheryCrawler — orchestrates the crawling pipeline."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from data.crawler import SmitheryCrawler
from data.smithery_client import SmitheryClient
from models import MCPServer, MCPServerSummary, MCPTool


@pytest.fixture
def mock_client() -> SmitheryClient:
    client = AsyncMock(spec=SmitheryClient)
    client.rate_limit_seconds = 0.5

    summaries = [
        MCPServerSummary(
            qualified_name="@a/server",
            display_name="Server A",
            use_count=100,
            is_deployed=True,
        ),
        MCPServerSummary(
            qualified_name="@b/server",
            display_name="Server B",
            use_count=50,
            is_deployed=True,
        ),
    ]
    client.fetch_all_summaries = AsyncMock(return_value=summaries)

    servers = {
        "@a/server": MCPServer(
            server_id="@a/server",
            name="Server A",
            tools=[
                MCPTool(
                    server_id="@a/server",
                    tool_name="tool1",
                    tool_id="@a/server::tool1",
                    description="Tool 1",
                ),
            ],
        ),
        "@b/server": MCPServer(
            server_id="@b/server",
            name="Server B",
            tools=[],
        ),
    }
    client.fetch_server_detail = AsyncMock(side_effect=lambda qn: servers[qn])
    return client


class TestSmitheryCrawler:
    async def test_crawl_returns_servers(self, mock_client):
        crawler = SmitheryCrawler(client=mock_client)
        servers = await crawler.crawl(max_pages=1, max_servers=10)
        assert len(servers) == 2
        assert servers[0].server_id == "@a/server"
        assert len(servers[0].tools) == 1

    async def test_crawl_respects_max_servers(self, mock_client):
        crawler = SmitheryCrawler(client=mock_client)
        servers = await crawler.crawl(max_pages=1, max_servers=1)
        assert len(servers) == 1

    async def test_crawl_calls_detail_for_each(self, mock_client):
        crawler = SmitheryCrawler(client=mock_client)
        await crawler.crawl(max_pages=1, max_servers=10)
        assert mock_client.fetch_server_detail.call_count == 2

    async def test_crawl_skips_failed_detail(self, mock_client):
        mock_client.fetch_server_detail = AsyncMock(
            side_effect=[
                MCPServer(server_id="@a/server", name="A", tools=[]),
                Exception("API error"),
            ]
        )
        crawler = SmitheryCrawler(client=mock_client)
        servers = await crawler.crawl(max_pages=1, max_servers=10)
        assert len(servers) == 1


class TestSaveLoad:
    def test_save_and_load_roundtrip(self, tmp_path):
        server = MCPServer(
            server_id="@test/srv",
            name="Test",
            description="Test server",
            tools=[
                MCPTool(
                    server_id="@test/srv",
                    tool_name="my_tool",
                    tool_id="@test/srv::my_tool",
                    description="A tool",
                    input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
                ),
            ],
        )
        crawler = SmitheryCrawler(client=AsyncMock())
        path = crawler.save([server], output_dir=tmp_path)
        assert path.exists()
        assert path.suffix == ".jsonl"

        loaded = SmitheryCrawler.load(path)
        assert len(loaded) == 1
        assert loaded[0].server_id == "@test/srv"
        assert len(loaded[0].tools) == 1
        assert loaded[0].tools[0].tool_id == "@test/srv::my_tool"

    def test_save_creates_directory(self, tmp_path):
        new_dir = tmp_path / "sub" / "dir"
        crawler = SmitheryCrawler(client=AsyncMock())
        path = crawler.save([], output_dir=new_dir)
        assert path.exists()

    def test_load_empty_file(self, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text("")
        loaded = SmitheryCrawler.load(f)
        assert loaded == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_crawler.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement crawler.py**

`src/data/crawler.py`:
```python
"""Crawling orchestrator — combines SmitheryClient + ServerSelector."""

import json
from pathlib import Path

from loguru import logger

from data.server_selector import select_servers
from data.smithery_client import SmitheryClient
from models import MCPServer


class SmitheryCrawler:
    """Orchestrates server list fetch -> selection -> detail fetch."""

    def __init__(self, client: SmitheryClient) -> None:
        self.client = client

    async def crawl(
        self,
        max_pages: int = 10,
        curated_list: Path | None = None,
        max_servers: int = 100,
    ) -> list[MCPServer]:
        summaries = await self.client.fetch_all_summaries(max_pages=max_pages)
        logger.info(f"Fetched {len(summaries)} server summaries")

        selected = select_servers(
            summaries, curated_list=curated_list, max_servers=max_servers,
        )
        logger.info(f"Selected {len(selected)} servers for detail fetch")

        servers: list[MCPServer] = []
        for i, summary in enumerate(selected, 1):
            try:
                server = await self.client.fetch_server_detail(summary.qualified_name)
                servers.append(server)
                logger.info(
                    f"Fetched {i}/{len(selected)}: {summary.qualified_name} "
                    f"({len(server.tools)} tools)"
                )
            except Exception as e:
                logger.warning(
                    f"Failed {i}/{len(selected)}: {summary.qualified_name} — {e}"
                )
        return servers

    def save(
        self, servers: list[MCPServer], output_dir: Path = Path("data/raw"),
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "servers.jsonl"
        with path.open("w") as f:
            for server in servers:
                f.write(server.model_dump_json() + "\n")
        logger.info(f"Saved {len(servers)} servers to {path}")
        return path

    @staticmethod
    def load(path: Path) -> list[MCPServer]:
        servers: list[MCPServer] = []
        text = path.read_text().strip()
        if not text:
            return servers
        for line in text.splitlines():
            if line.strip():
                servers.append(MCPServer.model_validate_json(line))
        return servers
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_crawler.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/data/crawler.py tests/unit/test_crawler.py
git commit -m "feat(data): SmitheryCrawler orchestrator with save/load JSONL"
```

---

### Task 7: MCPDirectConnector Interface (TDD)

**Files:**
- Create: `tests/unit/test_mcp_connector.py`
- Create: `src/data/mcp_connector.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_mcp_connector.py`:
```python
"""Tests for MCPDirectConnector — interface only for Phase 1."""

import pytest

from data.mcp_connector import MCPDirectConnector
from models import TOOL_ID_SEPARATOR


SAMPLE_TOOLS_RESPONSE = {
    "tools": [
        {
            "name": "search",
            "description": "Search for items",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
        },
        {
            "name": "create",
            "description": "Create an item",
            "inputSchema": None,
        },
    ]
}


class TestParseTools:
    def test_parse_tools(self):
        tools = MCPDirectConnector.parse_tools("@test/server", SAMPLE_TOOLS_RESPONSE)
        assert len(tools) == 2
        assert tools[0].tool_id == f"@test/server{TOOL_ID_SEPARATOR}search"
        assert tools[0].tool_name == "search"
        assert tools[0].server_id == "@test/server"
        assert tools[0].description == "Search for items"

    def test_tool_id_format(self):
        tools = MCPDirectConnector.parse_tools("@my/srv", SAMPLE_TOOLS_RESPONSE)
        for tool in tools:
            assert TOOL_ID_SEPARATOR in tool.tool_id

    def test_empty_response(self):
        tools = MCPDirectConnector.parse_tools("@test/server", {"tools": []})
        assert tools == []

    def test_missing_tools_key(self):
        tools = MCPDirectConnector.parse_tools("@test/server", {})
        assert tools == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_mcp_connector.py -v`
Expected: FAIL

- [ ] **Step 3: Implement mcp_connector.py**

`src/data/mcp_connector.py`:
```python
"""Direct MCP connector — interface only for Phase 1. Full implementation in Phase 4+."""

from models import MCPTool, TOOL_ID_SEPARATOR


class MCPDirectConnector:
    """Connects directly to MCP servers via JSON-RPC tools/list.

    Phase 1: only parse_tools is implemented.
    Phase 4+: fetch_tools will make actual JSON-RPC calls.
    """

    async def fetch_tools(self, server_id: str, endpoint_url: str) -> list[MCPTool]:
        raise NotImplementedError("Direct MCP connection is planned for Phase 4+")

    @staticmethod
    def parse_tools(server_id: str, response: dict) -> list[MCPTool]:
        raw_tools = response.get("tools", [])
        return [
            MCPTool(
                server_id=server_id,
                tool_name=t["name"],
                tool_id=f"{server_id}{TOOL_ID_SEPARATOR}{t['name']}",
                description=t.get("description"),
                input_schema=t.get("inputSchema"),
            )
            for t in raw_tools
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_mcp_connector.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/data/mcp_connector.py tests/unit/test_mcp_connector.py
git commit -m "feat(data): MCPDirectConnector interface + parse_tools"
```

---

### Task 8: Collection Script

**Files:**
- Create: `scripts/collect_data.py`

- [ ] **Step 1: Create the collection script**

`scripts/collect_data.py`:
```python
"""CLI script for crawling MCP servers from Smithery Registry.

Usage:
    uv run scripts/collect_data.py                          # top 100 deployed
    uv run scripts/collect_data.py --max-servers 50
    uv run scripts/collect_data.py --server-list path.txt   # curated list
    uv run scripts/collect_data.py --max-pages 5
"""

import argparse
import asyncio
from pathlib import Path

from loguru import logger

from config import Settings
from data.crawler import SmitheryCrawler
from data.smithery_client import SmitheryClient


async def main(args: argparse.Namespace) -> None:
    settings = Settings()
    curated_list = Path(args.server_list) if args.server_list else None

    async with SmitheryClient(base_url=settings.smithery_api_base_url) as client:
        crawler = SmitheryCrawler(client=client)
        servers = await crawler.crawl(
            max_pages=args.max_pages,
            curated_list=curated_list,
            max_servers=args.max_servers,
        )

    path = crawler.save(servers, output_dir=Path(args.output_dir))
    total_tools = sum(len(s.tools) for s in servers)
    logger.info(f"Done: {len(servers)} servers, {total_tools} tools -> {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl MCP servers from Smithery Registry")
    parser.add_argument("--max-servers", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--server-list", type=str, default=None, help="Path to curated server list")
    parser.add_argument("--output-dir", type=str, default="data/raw")
    args = parser.parse_args()
    asyncio.run(main(args))
```

- [ ] **Step 2: Verify script is importable**

Run: `uv run python -c "import scripts.collect_data; print('OK')"` or just check syntax:
Run: `uv run python -c "import ast; ast.parse(open('scripts/collect_data.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/collect_data.py
git commit -m "feat(data): collect_data.py CLI for Smithery crawling"
```

---

## Phase 2: Embedding & Vector Store

### Task 9: Embedder ABC (TDD)

**Files:**
- Create: `tests/unit/test_embedder.py`
- Create: `src/embedding/base.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_embedder.py`:
```python
"""Tests for Embedder ABC and OpenAIEmbedder."""

import inspect

import numpy as np
import pytest

from embedding.base import Embedder


class TestEmbedderABC:
    def test_is_abstract(self):
        assert inspect.isabstract(Embedder)

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Embedder()

    def test_has_embed_one(self):
        assert hasattr(Embedder, "embed_one")

    def test_has_embed_batch(self):
        assert hasattr(Embedder, "embed_batch")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_embedder.py -v`
Expected: FAIL

- [ ] **Step 3: Implement base.py**

`src/embedding/base.py`:
```python
"""Abstract base class for embedding providers."""

from abc import ABC, abstractmethod

import numpy as np


class Embedder(ABC):
    """ABC for text embedding. All implementations must be async."""

    model: str
    dimension: int

    @abstractmethod
    async def embed_one(self, text: str) -> np.ndarray:
        """Embed a single text string."""

    @abstractmethod
    async def embed_batch(self, texts: list[str], batch_size: int = 50) -> list[np.ndarray]:
        """Embed a batch of texts, chunked by batch_size."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_embedder.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/embedding/base.py tests/unit/test_embedder.py
git commit -m "feat(embedding): Embedder ABC with embed_one/embed_batch"
```

---

### Task 10: OpenAIEmbedder (TDD)

**Files:**
- Create: `src/embedding/openai_embedder.py`
- Modify: `tests/unit/test_embedder.py`

- [ ] **Step 1: Add OpenAIEmbedder tests**

Append to `tests/unit/test_embedder.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

from embedding.openai_embedder import OpenAIEmbedder


class TestOpenAIEmbedder:
    def test_model_and_dimension(self):
        embedder = OpenAIEmbedder(api_key="fake-key")
        assert embedder.model == "text-embedding-3-small"
        assert embedder.dimension == 1536

    def test_custom_model(self):
        embedder = OpenAIEmbedder(
            api_key="fake-key", model="text-embedding-3-large", dimension=3072,
        )
        assert embedder.model == "text-embedding-3-large"
        assert embedder.dimension == 3072

    def test_is_embedder_subclass(self):
        assert issubclass(OpenAIEmbedder, Embedder)

    async def test_embed_one(self):
        embedder = OpenAIEmbedder(api_key="fake-key")
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        embedder._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await embedder.embed_one("test text")
        assert isinstance(result, np.ndarray)
        assert result.shape == (1536,)

    async def test_embed_batch(self):
        embedder = OpenAIEmbedder(api_key="fake-key")
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1] * 1536),
            MagicMock(embedding=[0.2] * 1536),
        ]
        embedder._client.embeddings.create = AsyncMock(return_value=mock_response)

        results = await embedder.embed_batch(["text1", "text2"], batch_size=10)
        assert len(results) == 2
        assert all(isinstance(r, np.ndarray) for r in results)

    async def test_embed_batch_chunking(self):
        embedder = OpenAIEmbedder(api_key="fake-key")
        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            texts = kwargs["input"]
            mock_resp = MagicMock()
            mock_resp.data = [MagicMock(embedding=[0.1] * 1536) for _ in texts]
            return mock_resp

        embedder._client.embeddings.create = mock_create

        results = await embedder.embed_batch(["t"] * 5, batch_size=2)
        assert len(results) == 5
        assert call_count == 3  # ceil(5/2) = 3 batches
```

- [ ] **Step 2: Run test to verify new tests fail**

Run: `uv run pytest tests/unit/test_embedder.py::TestOpenAIEmbedder -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement openai_embedder.py**

`src/embedding/openai_embedder.py`:
```python
"""OpenAI text-embedding-3-small embedder implementation."""

import numpy as np
from openai import AsyncOpenAI

from embedding.base import Embedder


class OpenAIEmbedder(Embedder):
    """Embedder using OpenAI's text-embedding API."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
    ) -> None:
        self.model = model
        self.dimension = dimension
        self._client = AsyncOpenAI(api_key=api_key)

    async def embed_one(self, text: str) -> np.ndarray:
        response = await self._client.embeddings.create(
            input=[text], model=self.model,
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    async def embed_batch(self, texts: list[str], batch_size: int = 50) -> list[np.ndarray]:
        all_vectors: list[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self._client.embeddings.create(
                input=batch, model=self.model,
            )
            vectors = [
                np.array(item.embedding, dtype=np.float32) for item in response.data
            ]
            all_vectors.extend(vectors)
        return all_vectors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_embedder.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/embedding/openai_embedder.py tests/unit/test_embedder.py
git commit -m "feat(embedding): OpenAIEmbedder with batch chunking"
```

---

### Task 11: QdrantStore (TDD)

**Files:**
- Create: `tests/unit/test_qdrant_store.py`
- Create: `src/retrieval/qdrant_store.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_qdrant_store.py`:
```python
"""Tests for QdrantStore — Qdrant Cloud wrapper."""

import uuid

import pytest

from models import MCPTool, TOOL_ID_SEPARATOR
from retrieval.qdrant_store import MCP_DISCOVERY_NAMESPACE, QdrantStore


@pytest.fixture
def sample_tool() -> MCPTool:
    return MCPTool(
        server_id="@smithery-ai/github",
        tool_name="search_issues",
        tool_id="@smithery-ai/github::search_issues",
        description="Search GitHub issues by query",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
        },
    )


@pytest.fixture
def tool_no_description() -> MCPTool:
    return MCPTool(
        server_id="@test/srv",
        tool_name="no_desc",
        tool_id="@test/srv::no_desc",
    )


class TestBuildToolText:
    def test_with_description(self, sample_tool):
        text = QdrantStore.build_tool_text(sample_tool)
        assert text == "search_issues: Search GitHub issues by query"

    def test_without_description(self, tool_no_description):
        text = QdrantStore.build_tool_text(tool_no_description)
        assert text == "no_desc"


class TestToolToPayload:
    def test_contains_required_fields(self, sample_tool):
        payload = QdrantStore.tool_to_payload(sample_tool)
        assert payload["tool_id"] == "@smithery-ai/github::search_issues"
        assert payload["server_id"] == "@smithery-ai/github"
        assert payload["tool_name"] == "search_issues"
        assert payload["description"] == "Search GitHub issues by query"
        assert payload["input_schema"] is not None

    def test_none_description(self, tool_no_description):
        payload = QdrantStore.tool_to_payload(tool_no_description)
        assert payload["description"] is None


class TestPayloadToTool:
    def test_roundtrip(self, sample_tool):
        payload = QdrantStore.tool_to_payload(sample_tool)
        restored = QdrantStore.payload_to_tool(payload)
        assert restored.tool_id == sample_tool.tool_id
        assert restored.server_id == sample_tool.server_id
        assert restored.tool_name == sample_tool.tool_name
        assert restored.description == sample_tool.description


class TestGeneratePointId:
    def test_deterministic(self):
        id1 = QdrantStore.generate_point_id("@test/srv::tool")
        id2 = QdrantStore.generate_point_id("@test/srv::tool")
        assert id1 == id2

    def test_different_ids_for_different_tools(self):
        id1 = QdrantStore.generate_point_id("@a/srv::tool1")
        id2 = QdrantStore.generate_point_id("@a/srv::tool2")
        assert id1 != id2

    def test_returns_valid_uuid_string(self):
        result = QdrantStore.generate_point_id("@test/srv::tool")
        parsed = uuid.UUID(result)
        assert str(parsed) == result

    def test_uses_uuid5(self):
        tool_id = "@test/srv::tool"
        expected = str(uuid.uuid5(MCP_DISCOVERY_NAMESPACE, tool_id))
        assert QdrantStore.generate_point_id(tool_id) == expected


class TestMCPDiscoveryNamespace:
    def test_is_valid_uuid(self):
        assert isinstance(MCP_DISCOVERY_NAMESPACE, uuid.UUID)

    def test_is_fixed_value(self):
        assert str(MCP_DISCOVERY_NAMESPACE) == "7f1b3d4e-2a5c-4b8f-9e6d-1c0a3f5b7d9e"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_qdrant_store.py -v`
Expected: FAIL

- [ ] **Step 3: Implement qdrant_store.py**

`src/retrieval/qdrant_store.py`:
```python
"""Qdrant Cloud vector store wrapper."""

import uuid

import numpy as np
from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from models import MCPTool, SearchResult, TOOL_ID_SEPARATOR

MCP_DISCOVERY_NAMESPACE = uuid.UUID("7f1b3d4e-2a5c-4b8f-9e6d-1c0a3f5b7d9e")


class QdrantStore:
    """Qdrant Cloud wrapper for MCP tool vectors."""

    def __init__(self, client: AsyncQdrantClient, collection_name: str = "mcp_tools") -> None:
        self.client = client
        self.collection_name = collection_name

    async def ensure_collection(self, dimension: int) -> None:
        collections = await self.client.get_collections()
        existing = [c.name for c in collections.collections]
        if self.collection_name in existing:
            logger.info(f"Collection '{self.collection_name}' already exists")
            return
        await self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
        )
        logger.info(f"Created collection '{self.collection_name}' (dim={dimension})")

    async def upsert_tools(self, tools: list[MCPTool], vectors: list[np.ndarray]) -> None:
        points = [
            PointStruct(
                id=self.generate_point_id(tool.tool_id),
                vector=vector.tolist(),
                payload=self.tool_to_payload(tool),
            )
            for tool, vector in zip(tools, vectors)
        ]
        await self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f"Upserted {len(points)} points to '{self.collection_name}'")

    async def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        server_id_filter: str | None = None,
    ) -> list[SearchResult]:
        query_filter = None
        if server_id_filter:
            query_filter = Filter(
                must=[FieldCondition(key="server_id", match=MatchValue(value=server_id_filter))]
            )
        results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector.tolist(),
            limit=top_k,
            query_filter=query_filter,
        )
        return [
            SearchResult(
                tool=self.payload_to_tool(hit.payload),
                score=hit.score,
                rank=i + 1,
            )
            for i, hit in enumerate(results)
        ]

    @staticmethod
    def build_tool_text(tool: MCPTool) -> str:
        if tool.description:
            return f"{tool.tool_name}: {tool.description}"
        return tool.tool_name

    @staticmethod
    def tool_to_payload(tool: MCPTool) -> dict:
        return {
            "tool_id": tool.tool_id,
            "server_id": tool.server_id,
            "tool_name": tool.tool_name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }

    @staticmethod
    def payload_to_tool(payload: dict) -> MCPTool:
        return MCPTool(
            server_id=payload["server_id"],
            tool_name=payload["tool_name"],
            tool_id=payload["tool_id"],
            description=payload.get("description"),
            input_schema=payload.get("input_schema"),
        )

    @staticmethod
    def generate_point_id(tool_id: str) -> str:
        return str(uuid.uuid5(MCP_DISCOVERY_NAMESPACE, tool_id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_qdrant_store.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/retrieval/qdrant_store.py tests/unit/test_qdrant_store.py
git commit -m "feat(retrieval): QdrantStore with UUID v5 point IDs + COSINE"
```

---

### Task 12: ToolIndexer (TDD)

**Files:**
- Create: `tests/unit/test_indexer.py`
- Create: `src/data/indexer.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_indexer.py`:
```python
"""Tests for ToolIndexer — embed + upsert orchestrator."""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from data.indexer import ToolIndexer
from embedding.base import Embedder
from models import MCPTool
from retrieval.qdrant_store import QdrantStore


@pytest.fixture
def sample_tools() -> list[MCPTool]:
    return [
        MCPTool(
            server_id="@a/srv",
            tool_name="tool1",
            tool_id="@a/srv::tool1",
            description="First tool",
        ),
        MCPTool(
            server_id="@a/srv",
            tool_name="tool2",
            tool_id="@a/srv::tool2",
            description="Second tool",
        ),
        MCPTool(
            server_id="@b/srv",
            tool_name="tool3",
            tool_id="@b/srv::tool3",
        ),
    ]


@pytest.fixture
def mock_embedder() -> Embedder:
    embedder = AsyncMock(spec=Embedder)
    embedder.model = "test-model"
    embedder.dimension = 4

    async def mock_embed_batch(texts, batch_size=50):
        return [np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32) for _ in texts]

    embedder.embed_batch = mock_embed_batch
    return embedder


@pytest.fixture
def mock_store() -> QdrantStore:
    store = AsyncMock(spec=QdrantStore)
    store.build_tool_text = QdrantStore.build_tool_text  # use real static method
    store.upsert_tools = AsyncMock()
    return store


class TestToolIndexer:
    async def test_index_tools_returns_count(self, sample_tools, mock_embedder, mock_store):
        indexer = ToolIndexer(embedder=mock_embedder, store=mock_store)
        count = await indexer.index_tools(sample_tools)
        assert count == 3

    async def test_index_tools_calls_upsert(self, sample_tools, mock_embedder, mock_store):
        indexer = ToolIndexer(embedder=mock_embedder, store=mock_store)
        await indexer.index_tools(sample_tools)
        mock_store.upsert_tools.assert_called_once()
        call_args = mock_store.upsert_tools.call_args
        assert len(call_args[0][0]) == 3  # tools
        assert len(call_args[0][1]) == 3  # vectors

    async def test_index_tools_batching(self, sample_tools, mock_embedder, mock_store):
        indexer = ToolIndexer(embedder=mock_embedder, store=mock_store)
        await indexer.index_tools(sample_tools, batch_size=2)
        # With batch_size=2 and 3 tools: 2 upsert calls (2 + 1)
        assert mock_store.upsert_tools.call_count == 2

    async def test_index_empty_list(self, mock_embedder, mock_store):
        indexer = ToolIndexer(embedder=mock_embedder, store=mock_store)
        count = await indexer.index_tools([])
        assert count == 0
        mock_store.upsert_tools.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_indexer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement indexer.py**

`src/data/indexer.py`:
```python
"""Batch embed + upsert orchestrator."""

from loguru import logger

from embedding.base import Embedder
from models import MCPTool
from retrieval.qdrant_store import QdrantStore


class ToolIndexer:
    """Orchestrates embedding and upserting tools to Qdrant."""

    def __init__(self, embedder: Embedder, store: QdrantStore) -> None:
        self.embedder = embedder
        self.store = store

    async def index_tools(self, tools: list[MCPTool], batch_size: int = 50) -> int:
        if not tools:
            return 0

        for i in range(0, len(tools), batch_size):
            batch = tools[i : i + batch_size]
            texts = [QdrantStore.build_tool_text(tool) for tool in batch]
            vectors = await self.embedder.embed_batch(texts, batch_size=batch_size)
            await self.store.upsert_tools(batch, vectors)
            logger.info(f"Indexed batch {i // batch_size + 1}: {len(batch)} tools")

        logger.info(f"Indexing complete: {len(tools)} tools")
        return len(tools)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_indexer.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/data/indexer.py tests/unit/test_indexer.py
git commit -m "feat(data): ToolIndexer — batch embed + upsert orchestrator"
```

---

### Task 13: Build Index Script

**Files:**
- Create: `scripts/build_index.py`

- [ ] **Step 1: Create the build index script**

`scripts/build_index.py`:
```python
"""CLI script for building the Qdrant vector index from crawled data.

Usage:
    uv run scripts/build_index.py
    uv run scripts/build_index.py --input data/raw/servers.jsonl
    uv run scripts/build_index.py --pool-size 50     # max tools to index
    uv run scripts/build_index.py --batch-size 100   # embedding batch size
"""

import argparse
import asyncio
from pathlib import Path

from loguru import logger
from qdrant_client import AsyncQdrantClient

from config import Settings
from data.crawler import SmitheryCrawler
from data.indexer import ToolIndexer
from embedding.openai_embedder import OpenAIEmbedder
from models import MCPTool
from retrieval.qdrant_store import QdrantStore


async def main(args: argparse.Namespace) -> None:
    settings = Settings()

    # Load servers
    input_path = Path(args.input)
    servers = SmitheryCrawler.load(input_path)
    logger.info(f"Loaded {len(servers)} servers from {input_path}")

    # Flatten tools
    tools: list[MCPTool] = []
    no_desc_count = 0
    for server in servers:
        for tool in server.tools:
            if tool.description is None:
                no_desc_count += 1
                logger.warning(f"Tool without description: {tool.tool_id}")
            tools.append(tool)
    logger.info(f"Total tools: {len(tools)} ({no_desc_count} without description)")

    if not tools:
        logger.warning("No tools to index. Exiting.")
        return

    # Truncate to pool_size if specified
    if args.pool_size and args.pool_size < len(tools):
        logger.info(f"Truncating to --pool-size={args.pool_size} tools")
        tools = tools[:args.pool_size]

    # Validate required API key
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is required for embedding. Set it in .env")
        raise SystemExit(1)

    # Setup components
    embedder = OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
    )
    qdrant_client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )
    store = QdrantStore(client=qdrant_client, collection_name=settings.qdrant_collection_name)

    # Ensure collection exists
    await store.ensure_collection(dimension=settings.embedding_dimension)

    # Index
    indexer = ToolIndexer(embedder=embedder, store=store)
    count = await indexer.index_tools(tools, batch_size=args.batch_size)

    logger.info(f"Done: Indexed {count} tools from {len(servers)} servers")
    await qdrant_client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Qdrant vector index from crawled data")
    parser.add_argument("--input", type=str, default="data/raw/servers.jsonl")
    parser.add_argument("--pool-size", type=int, default=None, help="Max number of tools to index")
    parser.add_argument("--batch-size", type=int, default=50, help="Embedding API batch size")
    args = parser.parse_args()
    asyncio.run(main(args))
```

- [ ] **Step 2: Verify syntax**

Run: `uv run python -c "import ast; ast.parse(open('scripts/build_index.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/build_index.py
git commit -m "feat(scripts): build_index.py CLI for Qdrant index building"
```

---

## Post-Implementation

### Task 14: Run Full Test Suite

- [ ] **Step 1: Run all unit tests**

Run: `uv run pytest tests/unit/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run with coverage**

Run: `uv run pytest tests/unit/ --cov=src -v`
Expected: Coverage report shown, all PASS

- [ ] **Step 3: Run linter**

Run: `uv run ruff check src/ tests/`
Expected: No errors (or fix any that appear)

- [ ] **Step 4: Run formatter**

Run: `uv run ruff format src/ tests/`
Expected: Files formatted

- [ ] **Step 5: Fix any issues and commit**

```bash
git add -u
git commit -m "chore: lint and format fixes"
```

---

### Task 15: Update Design Documents

**Files:**
- Modify: `docs/plan/phase-0-2.md`
- Modify: `docs/design/code-structure.md`
- Modify: `docs/design/architecture.md`
- Modify: `docs/design/ground-truth-schema.md`
- Modify: `docs/design/ground-truth-design.md`
- Modify: `docs/plan/implementation.md`

Apply the 6 changes from the spec (Section 7):

- [ ] **Step 1: Update `docs/plan/phase-0-2.md`**

Changes:
- crawler.py single file -> smithery_client.py + server_selector.py + crawler.py (3 files)
- tool_id separator: `/` -> `::`
- Qdrant ID: `abs(hash())` -> `uuid.uuid5()`
- Crawling scope: deployed filter + popularity sort + curation list
- mcp_connector.py: interface only in Phase 1
- MCPTool: `input_schema` only, remove `parameters`

- [ ] **Step 2: Update `docs/design/code-structure.md`**

Add `smithery_client.py`, `server_selector.py` to `src/data/`. Add `MCPServerSummary` to models description.

- [ ] **Step 3: Update `docs/design/architecture.md`**

Add crawling selection criteria to DP7. Add `tool_id` separator `::` note to relevant DPs.

- [ ] **Step 4: Update `docs/design/ground-truth-schema.md`**

Change `tool_id` format from `{server_id}/{tool_name}` to `{server_id}::{tool_name}`. Update all JSON examples.

- [ ] **Step 5: Update `docs/design/ground-truth-design.md`**

Change `correct_tool_id` examples to use `::` separator.

- [ ] **Step 6: Update `docs/plan/implementation.md`**

Change common conventions section: tool_id format `{server_id}/{tool_name}` -> `{server_id}::{tool_name}`.

- [ ] **Step 7: Commit**

```bash
git add docs/plan/phase-0-2.md docs/design/code-structure.md docs/design/architecture.md docs/design/ground-truth-schema.md docs/design/ground-truth-design.md docs/plan/implementation.md
git commit -m "docs: reflect Phase 0-2 design changes (:: separator, UUID v5, 3-module crawler)"
```

---

### Task 16: E2E Smoke Test (Crawling Only)

This tests the crawling pipeline end-to-end against the real Smithery API.

- [ ] **Step 1: Run smoke test with 3 servers**

Run: `uv run python scripts/collect_data.py --max-servers 3 --max-pages 1`
Expected: `data/raw/servers.jsonl` created with 3 server entries

- [ ] **Step 2: Verify JSONL content**

Run: `uv run python -c "from data.crawler import SmitheryCrawler; from pathlib import Path; servers = SmitheryCrawler.load(Path('data/raw/servers.jsonl')); print(f'{len(servers)} servers, {sum(len(s.tools) for s in servers)} tools'); [print(f'  {s.server_id}: {len(s.tools)} tools') for s in servers]"`
Expected: 3 servers with tool counts printed

- [ ] **Step 3: Commit crawled data as cache**

```bash
git add data/raw/servers.jsonl
git commit -m "data: initial Smithery crawl (smoke test, 3 servers)"
```

---

## Summary

| Phase | Tasks | Commits |
|-------|-------|---------|
| Phase 0 | Task 1-3 | 3 commits |
| Phase 1 | Task 4-8 | 5 commits |
| Phase 2 | Task 9-13 | 5 commits |
| Post | Task 14-16 | 3 commits |
| **Total** | **16 tasks** | **~16 commits** |

**Dependency chain:**
```
Task 1 (scaffold) → Task 2 (config) → Task 3 (models)
                                            ↓
                    Task 4 (client) → Task 5 (selector) → Task 6 (crawler) → Task 8 (CLI)
                    Task 7 (connector) — parallel with Task 5-6
                                            ↓
                    Task 9 (ABC) → Task 10 (OpenAI) → Task 11 (Qdrant) → Task 12 (indexer) → Task 13 (CLI)
                                                                                                    ↓
                                                                            Task 14 (tests) → Task 15 (docs) → Task 16 (E2E)
```
