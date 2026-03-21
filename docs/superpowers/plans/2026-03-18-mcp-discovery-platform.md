# MCP Discovery Platform — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-sided MCP Discovery & Optimization Platform: LLM/Agent customers get `find_best_tool(query)` that returns the best MCP tool from thousands; MCP Provider customers get an analytics dashboard that shows why their tool isn't being selected and how to fix it.

**Architecture:** A single 2-stage retrieval pipeline (Embedding → Vector Search → Reranker → Confidence branching) serves as the core engine. Two output channels branch from it: one returns the best tool to LLM/Agents, the other feeds a logging pipeline that powers Provider analytics. Three search strategy variants (Sequential, Parallel, Taxonomy-gated) are built behind a common `PipelineStrategy` interface so they can be compared experimentally.

**Tech Stack:** Python 3.12, FastAPI, Qdrant Cloud (free tier), BGE-M3 or OpenAI `text-embedding-3-small` (experiment decides — do NOT use voyage-code-2, it is code-specialized and MCP descriptions are natural language), Cohere Rerank 3, Langfuse (LLM tracing), Weights & Biases (experiment tracking), pytest, pydantic v2, uv (dependency management).

---

## Deferred Features (Out of Scope for This Plan)

These features are confirmed requirements but deferred to a follow-up plan after the core pipeline is stable:

| Feature | Rationale for deferral |
|---------|------------------------|
| **Distribution** (MCP server registration, install page) | Requires UI/frontend layer. Implement after backend analytics API is stable. |
| **Spec Compliance** (MCP protocol validation, quality gate) | Needs MCP spec parsing. Implement after data collection pipeline is built. |
| **OAuth UI** (auth modal for credentialed servers) | Requires frontend + auth flow. Lowest priority per DP0 depth allocation. |
| **Live Query Sandbox** (D-1, real-time "does my tool get selected?") | Depends on working search endpoint (Phase 8). Build as provider dashboard feature after Phase 9. |
| **Description Diff & Impact Preview** (D-2) | Requires A/B test infra (Phase 9) + UI. Post-core. |
| **Guided Description Onboarding** (D-4) | Requires SEO scorer (Phase 9) + UI wizard. Post-core. |
| **Feedback Loop Dashboard** (PM-3) | Requires aggregator (Phase 9) + UI. Post-core. |
| **Strategy C: Taxonomy-gated** | Pending CTO mentoring confirmation (2026-03-25). `taxonomy_gated.py` stub file is in the structure map; implementation task added as Phase 13 (gated). |
| **MCP Tool Server** (`find_best_tool` as MCP protocol Tool) | DP1 confirmed dual-exposure (REST + MCP). REST implemented in Phase 8. MCP Tool server is Phase 13 (after REST is stable). |

All features above WILL be implemented. This plan produces the core pipeline + Provider Analytics backend. UI and additional features ship in the next plan iteration.

---

## Scope Note

This plan covers 4 independent subsystems. Each phase produces working, testable software on its own. If the plan gets too large to execute in one session, split at phase boundaries:
- **Sub-plan A**: Phases 0–3 (Foundation + Data + Core Pipeline)
- **Sub-plan B**: Phases 4–5 (Ground Truth + Evaluation)
- **Sub-plan C**: Phases 6–7 (Hybrid Search + API)
- **Sub-plan D**: Phases 8–9 (Provider Analytics + Deploy)

---

## File Structure

```
mcp-discovery/
├── src/
│   ├── models.py                    # Shared Pydantic models (Tool, Server, Query, Result)
│   ├── config.py                    # Env-based config (Qdrant URL, API keys, thresholds)
│   ├── pipeline/
│   │   ├── strategy.py              # PipelineStrategy ABC + StrategyRegistry
│   │   ├── sequential.py            # Strategy A: 2-layer sequential search
│   │   ├── parallel.py              # Strategy B: parallel dual-index
│   │   ├── taxonomy_gated.py        # Strategy C: intent classify → category search
│   │   └── confidence.py            # Gap-based confidence branching logic
│   ├── embedding/
│   │   ├── base.py                  # Embedder ABC
│   │   ├── bge_m3.py                # BGE-M3 (Dense + Sparse unified)
│   │   └── openai_embedder.py       # OpenAI text-embedding-3-small
│   ├── retrieval/
│   │   ├── qdrant_store.py          # Qdrant Cloud wrapper (upsert, search, delete)
│   │   └── hybrid.py                # RRF fusion (bm25_rank + dense_rank)
│   ├── reranking/
│   │   ├── base.py                  # Reranker ABC
│   │   ├── cohere_reranker.py       # Cohere Rerank 3 (free 1000 req/month)
│   │   └── llm_fallback.py          # LLM reranker for low-confidence cases
│   ├── data/
│   │   ├── crawler.py               # Smithery registry crawler
│   │   ├── mcp_connector.py         # Direct tools/list MCP connection
│   │   ├── ground_truth.py          # LLM synthetic query generator + validator
│   │   └── indexer.py               # Batch embed + upsert to Qdrant
│   ├── evaluation/
│   │   ├── harness.py               # evaluate(strategy, queries, gt) → Metrics
│   │   ├── evaluator.py             # Evaluator ABC
│   │   ├── experiment.py            # Controlled variable experiment runner
│   │   └── metrics/
│   │       ├── precision.py         # Precision@1
│   │       ├── recall.py            # Recall@K
│   │       ├── latency.py           # p50/p95/p99 latency
│   │       ├── confusion_rate.py    # Confusion Rate (arxiv:2601.16280)
│   │       ├── calibration.py       # ECE (Naeini et al. AAAI 2015)
│   │       └── description_correlation.py  # Spearman(quality_score, selection_rate) ← core thesis
│   ├── analytics/
│   │   ├── logger.py                # Log every find_best_tool call to file/CloudWatch
│   │   ├── aggregator.py            # Aggregate logs → per-tool stats
│   │   ├── seo_score.py             # Description quality scorer (Specificity, Disambiguation, Coverage)
│   │   ├── ab_test.py               # A/B test runner (variant A vs B on synthetic queries)
│   │   ├── similarity_heatmap.py    # Pairwise cosine similarity between tools
│   │   └── confusion_matrix.py      # Per-tool confusion matrix from logs
│   └── api/
│       ├── main.py                  # FastAPI app entry point
│       ├── mcp_server.py            # MCP Tool server exposing find_best_tool
│       └── routes/
│           ├── search.py            # POST /search → find_best_tool
│           └── provider.py          # Provider analytics REST endpoints
├── data/
│   ├── raw/                         # Raw MCP server JSON from Smithery/direct
│   ├── ground_truth/                # (query, server_id, tool_name) JSONL
│   └── experiments/                 # Experiment results (CSV/JSON)
├── tests/
│   ├── unit/                        # Per-module unit tests
│   ├── integration/                 # Qdrant + Cohere live tests (skipped if no keys)
│   └── evaluation/                  # End-to-end eval harness tests
├── scripts/
│   ├── collect_data.py              # Run crawler + direct connectors → data/raw/
│   ├── build_index.py               # Embed data/raw/ → Qdrant
│   ├── generate_ground_truth.py     # Generate + validate synthetic queries
│   └── run_experiments.py           # Compare all 3 strategies → data/experiments/
├── docs/
│   └── superpowers/
│       └── plans/
│           └── 2026-03-18-mcp-discovery-platform.md  ← this file
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Phase 0: Project Foundation

**Produces:** Runnable project skeleton with config, models, and passing smoke tests.

### Task 0.1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `src/config.py`
- Create: `src/models.py`
- Create: `.env.example`

- [ ] **Step 1: Create pyproject.toml with uv**

```bash
cd /Users/iyeonjae/Desktop/shockwave/mcp-discovery
uv init --no-readme
```

Then set `pyproject.toml`:

```toml
[project]
name = "mcp-discovery"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "qdrant-client>=1.12",
    "cohere>=5.0",
    "openai>=1.0",
    "httpx>=0.27",
    "python-dotenv>=1.0",
    "langfuse>=2.0",
    "wandb>=0.18",
    "scipy>=1.13",
    "numpy>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24", "pytest-cov>=5.0", "ruff>=0.7"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff.lint]
select = ["E", "F", "I"]
```

- [ ] **Step 2: Install dependencies**

```bash
uv sync --extra dev
```

Expected: All packages installed, `uv.lock` created.

- [ ] **Step 3: Write failing test for config**

Create `tests/unit/test_config.py`:

```python
from src.config import Settings

def test_settings_defaults():
    s = Settings()
    assert s.qdrant_url == "http://localhost:6333"
    assert s.confidence_gap_threshold == 0.15
    assert s.top_k_retrieval == 10
    assert s.top_k_rerank == 3
```

- [ ] **Step 4: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src'`

- [ ] **Step 5: Create `src/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection_servers: str = "mcp_servers"
    qdrant_collection_tools: str = "mcp_tools"

    openai_api_key: str = ""
    cohere_api_key: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    embedding_model: str = "openai"  # "openai" | "bge_m3"
    top_k_retrieval: int = 10
    top_k_rerank: int = 3
    confidence_gap_threshold: float = 0.15

settings = Settings()
```

- [ ] **Step 6: Create `src/models.py`**

```python
from pydantic import BaseModel, Field
from typing import Optional

class MCPTool(BaseModel):
    tool_id: str                    # "{server_id}/{tool_name}"
    server_id: str
    tool_name: str
    description: str
    parameters: dict = Field(default_factory=dict)
    input_schema: Optional[dict] = None

class MCPServer(BaseModel):
    server_id: str
    name: str
    description: str
    homepage: Optional[str] = None
    tools: list[MCPTool] = Field(default_factory=list)

class SearchResult(BaseModel):
    tool: MCPTool
    score: float
    rank: int
    reason: Optional[str] = None

class FindBestToolRequest(BaseModel):
    query: str
    top_k: int = 3
    strategy: str = "sequential"

class FindBestToolResponse(BaseModel):
    query: str
    results: list[SearchResult]
    confidence: float              # gap between rank-1 and rank-2 scores
    disambiguation_needed: bool
    strategy_used: str
    latency_ms: float

class GroundTruth(BaseModel):
    query: str
    correct_server_id: str
    correct_tool_id: str
    difficulty: str = "medium"     # "easy" | "medium" | "hard"
    manually_verified: bool = False
```

- [ ] **Step 7: Create `src/__init__.py`**

```bash
touch src/__init__.py
```

This makes `src/` a package and ensures `pythonpath = ["src"]` in pyproject.toml resolves imports correctly.

- [ ] **Step 8: Create `.env.example`**

```
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_key
OPENAI_API_KEY=sk-...
COHERE_API_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
EMBEDDING_MODEL=openai
```

- [ ] **Step 9: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: PASS

- [ ] **Step 10: Commit**

```bash
git init
git add pyproject.toml uv.lock src/ tests/ .env.example
git commit -m "feat: project foundation — config, models, deps"
```

---

## Phase 1: Data Collection

**Produces:** `data/raw/` populated with MCP server + tool JSON. Scripts to re-collect.

### Task 1.1: Smithery Crawler

**Files:**
- Create: `src/data/crawler.py`
- Create: `tests/unit/test_crawler.py`
- Create: `scripts/collect_data.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_crawler.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock
from src.data.crawler import SmitheryCrawler

def test_parse_server_page():
    crawler = SmitheryCrawler()
    # Minimal Smithery-like JSON structure
    raw = {
        "qualifiedName": "test/server",
        "displayName": "Test Server",
        "description": "A test MCP server",
        "homepage": "https://example.com",
    }
    server = crawler.parse_server(raw)
    assert server.server_id == "test/server"
    assert server.description == "A test MCP server"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_crawler.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/data/crawler.py`**

```python
import httpx
import asyncio
import json
from pathlib import Path
from src.models import MCPServer, MCPTool

SMITHERY_API = "https://registry.smithery.ai/servers"

class SmitheryCrawler:
    def __init__(self, output_dir: str = "data/raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def parse_server(self, raw: dict) -> MCPServer:
        return MCPServer(
            server_id=raw.get("qualifiedName", raw.get("name", "unknown")),
            name=raw.get("displayName", raw.get("name", "")),
            description=raw.get("description", ""),
            homepage=raw.get("homepage"),
        )

    async def fetch_page(self, client: httpx.AsyncClient, page: int, page_size: int = 50) -> list[dict]:
        resp = await client.get(
            SMITHERY_API,
            params={"page": page, "pageSize": page_size},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("servers", data) if isinstance(data, dict) else data

    async def crawl(self, max_pages: int = 10) -> list[MCPServer]:
        servers = []
        async with httpx.AsyncClient() as client:
            for page in range(1, max_pages + 1):
                items = await self.fetch_page(client, page)
                if not items:
                    break
                for item in items:
                    servers.append(self.parse_server(item))
                print(f"Page {page}: {len(items)} servers (total: {len(servers)})")
                await asyncio.sleep(0.5)  # rate limit
        return servers

    def save(self, servers: list[MCPServer]) -> Path:
        out = self.output_dir / "servers.jsonl"
        with open(out, "w") as f:
            for s in servers:
                f.write(s.model_dump_json() + "\n")
        print(f"Saved {len(servers)} servers → {out}")
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_crawler.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/data/crawler.py tests/unit/test_crawler.py
git commit -m "feat: Smithery registry crawler"
```

---

### Task 1.2: Direct MCP Connector (tools/list)

**Files:**
- Create: `src/data/mcp_connector.py`
- Create: `tests/unit/test_mcp_connector.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_mcp_connector.py`:

```python
from unittest.mock import AsyncMock, patch
from src.data.mcp_connector import MCPConnector
from src.models import MCPTool

def test_parse_tools_list():
    connector = MCPConnector()
    raw_response = {
        "tools": [
            {
                "name": "search_papers",
                "description": "Search academic papers using Semantic Scholar",
                "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}
            }
        ]
    }
    server_id = "semantic_scholar"
    tools = connector.parse_tools(server_id, raw_response)
    assert len(tools) == 1
    assert tools[0].tool_id == "semantic_scholar/search_papers"
    assert tools[0].tool_name == "search_papers"
    assert tools[0].server_id == "semantic_scholar"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_mcp_connector.py -v
```

- [ ] **Step 3: Implement `src/data/mcp_connector.py`**

```python
import httpx
import json
from src.models import MCPTool, MCPServer

class MCPConnector:
    """Connects to individual MCP servers and calls tools/list."""

    def parse_tools(self, server_id: str, response: dict) -> list[MCPTool]:
        tools = []
        for t in response.get("tools", []):
            tools.append(MCPTool(
                tool_id=f"{server_id}/{t['name']}",
                server_id=server_id,
                tool_name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema"),
            ))
        return tools

    async def fetch_tools(self, server_id: str, endpoint_url: str) -> list[MCPTool]:
        """
        Calls tools/list on a running MCP server.
        endpoint_url: e.g. "http://localhost:3000"
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{endpoint_url}/tools/list",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result", data)
            return self.parse_tools(server_id, result)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_mcp_connector.py -v
```

- [ ] **Step 5: Create `scripts/collect_data.py`**

```python
#!/usr/bin/env python3
"""Collect MCP server data from Smithery and direct connections."""
import asyncio
import json
from pathlib import Path
from src.data.crawler import SmitheryCrawler

async def main():
    crawler = SmitheryCrawler()
    print("Crawling Smithery registry...")
    servers = await crawler.crawl(max_pages=5)
    crawler.save(servers)
    print(f"Done. {len(servers)} servers saved to data/raw/servers.jsonl")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Commit**

```bash
git add src/data/mcp_connector.py tests/unit/test_mcp_connector.py scripts/collect_data.py
git commit -m "feat: MCP direct connector + data collection script"
```

---

## Phase 2: Embedding & Vector Store

**Produces:** Embeddable tools + searchable Qdrant index.

### Task 2.1: Embedder Abstraction

**Files:**
- Create: `src/embedding/base.py`
- Create: `src/embedding/openai_embedder.py`
- Create: `tests/unit/test_embedder.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_embedder.py`:

```python
from src.embedding.base import Embedder

def test_embedder_is_abstract():
    import inspect
    assert inspect.isabstract(Embedder)

def test_openai_embedder_interface():
    from src.embedding.openai_embedder import OpenAIEmbedder
    # Should be instantiable (no API call in __init__)
    e = OpenAIEmbedder(api_key="fake")
    assert e.model == "text-embedding-3-small"
    assert e.dimension == 1536
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_embedder.py -v
```

- [ ] **Step 3: Implement `src/embedding/base.py`**

```python
from abc import ABC, abstractmethod
import numpy as np

class Embedder(ABC):
    dimension: int

    @abstractmethod
    async def embed_one(self, text: str) -> np.ndarray:
        """Embed a single text string."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed a batch of texts."""
        ...
```

- [ ] **Step 4: Implement `src/embedding/openai_embedder.py`**

```python
import numpy as np
from openai import AsyncOpenAI
from src.embedding.base import Embedder

class OpenAIEmbedder(Embedder):
    dimension = 1536

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key)

    async def embed_one(self, text: str) -> np.ndarray:
        response = await self._client.embeddings.create(
            model=self.model,
            input=text,
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        response = await self._client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [np.array(d.embedding, dtype=np.float32) for d in response.data]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_embedder.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/embedding/ tests/unit/test_embedder.py
git commit -m "feat: Embedder abstraction + OpenAI embedder"
```

---

### Task 2.2: Qdrant Vector Store

**Files:**
- Create: `src/retrieval/qdrant_store.py`
- Create: `tests/unit/test_qdrant_store.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_qdrant_store.py`:

```python
from unittest.mock import MagicMock, patch
from src.retrieval.qdrant_store import QdrantStore
from src.models import MCPTool

def test_tool_to_payload():
    store = QdrantStore.__new__(QdrantStore)  # skip __init__
    tool = MCPTool(
        tool_id="test/search",
        server_id="test",
        tool_name="search",
        description="A search tool",
    )
    payload = store._tool_to_payload(tool)
    assert payload["tool_id"] == "test/search"
    assert payload["server_id"] == "test"
    assert payload["description"] == "A search tool"

def test_build_tool_text():
    store = QdrantStore.__new__(QdrantStore)
    tool = MCPTool(
        tool_id="brave/search",
        server_id="brave",
        tool_name="brave_web_search",
        description="Search the web using Brave",
    )
    text = store._build_tool_text(tool)
    assert "brave_web_search" in text
    assert "Search the web" in text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_qdrant_store.py -v
```

- [ ] **Step 3: Implement `src/retrieval/qdrant_store.py`**

```python
import numpy as np
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
)
from src.models import MCPTool, MCPServer, SearchResult
from src.config import settings

class QdrantStore:
    def __init__(self):
        self._client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )

    def _tool_to_payload(self, tool: MCPTool) -> dict:
        return {
            "tool_id": tool.tool_id,
            "server_id": tool.server_id,
            "tool_name": tool.tool_name,
            "description": tool.description,
        }

    def _build_tool_text(self, tool: MCPTool) -> str:
        """Construct the text that gets embedded for a tool."""
        return f"{tool.tool_name}: {tool.description}"

    async def ensure_collection(self, collection: str, dim: int):
        existing = await self._client.get_collections()
        names = [c.name for c in existing.collections]
        if collection not in names:
            await self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    async def upsert_tools(self, tools: list[MCPTool], vectors: list[np.ndarray], collection: str):
        points = [
            PointStruct(
                id=abs(hash(t.tool_id)) % (2**63),
                vector=v.tolist(),
                payload=self._tool_to_payload(t),
            )
            for t, v in zip(tools, vectors)
        ]
        await self._client.upsert(collection_name=collection, points=points)

    async def search(
        self,
        query_vector: np.ndarray,
        collection: str,
        top_k: int = 10,
        server_id_filter: str | None = None,
    ) -> list[SearchResult]:
        filt = None
        if server_id_filter:
            filt = Filter(
                must=[FieldCondition(key="server_id", match=MatchValue(value=server_id_filter))]
            )
        hits = await self._client.search(
            collection_name=collection,
            query_vector=query_vector.tolist(),
            limit=top_k,
            query_filter=filt,
            with_payload=True,
        )
        from src.models import MCPTool
        results = []
        for i, hit in enumerate(hits):
            p = hit.payload
            results.append(SearchResult(
                tool=MCPTool(
                    tool_id=p["tool_id"],
                    server_id=p["server_id"],
                    tool_name=p["tool_name"],
                    description=p["description"],
                ),
                score=hit.score,
                rank=i + 1,
            ))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_qdrant_store.py -v
```

- [ ] **Step 5: Create `src/data/indexer.py`**

```python
import asyncio
from pathlib import Path
from src.models import MCPTool
from src.retrieval.qdrant_store import QdrantStore
from src.embedding.base import Embedder
from src.config import settings

class Indexer:
    def __init__(self, embedder: Embedder, store: QdrantStore):
        self.embedder = embedder
        self.store = store

    async def index_tools(self, tools: list[MCPTool], batch_size: int = 50):
        collection = settings.qdrant_collection_tools
        await self.store.ensure_collection(collection, self.embedder.dimension)
        for i in range(0, len(tools), batch_size):
            batch = tools[i:i + batch_size]
            texts = [self.store._build_tool_text(t) for t in batch]
            vectors = await self.embedder.embed_batch(texts)
            await self.store.upsert_tools(batch, vectors, collection)
            print(f"Indexed {min(i + batch_size, len(tools))}/{len(tools)} tools")
```

- [ ] **Step 6: Create `scripts/build_index.py`**

```python
#!/usr/bin/env python3
"""Embed data/raw/servers.jsonl and upsert into Qdrant."""
import asyncio
import json
from pathlib import Path
from src.models import MCPTool
from src.retrieval.qdrant_store import QdrantStore
from src.data.indexer import Indexer
from src.config import settings

async def main():
    raw_path = Path("data/raw/servers.jsonl")
    if not raw_path.exists():
        print("ERROR: data/raw/servers.jsonl not found. Run scripts/collect_data.py first.")
        return
    tools = []
    with open(raw_path) as f:
        for line in f:
            # Servers JSONL — extract tools from each server
            from src.models import MCPServer
            server = MCPServer.model_validate_json(line)
            tools.extend(server.tools)
    print(f"Loaded {len(tools)} tools from {raw_path}")

    if settings.embedding_model == "openai":
        from openai import AsyncOpenAI
        from src.embedding.openai_embedder import OpenAIEmbedder
        embedder = OpenAIEmbedder(api_key=settings.openai_api_key)
    else:
        raise ValueError(f"Unknown embedding_model: {settings.embedding_model}")

    store = QdrantStore()
    indexer = Indexer(embedder=embedder, store=store)
    await indexer.index_tools(tools)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 7: Commit**

```bash
git add src/retrieval/qdrant_store.py src/data/indexer.py tests/unit/test_qdrant_store.py scripts/build_index.py
git commit -m "feat: Qdrant vector store + indexer + build_index script"
```

---

## Phase 3: Core Pipeline — Strategy A (Sequential 2-Layer)

**Produces:** Working `find_best_tool` with sequential search + confidence branching.

### Task 3.1: PipelineStrategy Interface + Confidence

**Files:**
- Create: `src/pipeline/strategy.py`
- Create: `src/pipeline/confidence.py`
- Create: `tests/unit/test_confidence.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_confidence.py`:

```python
import pytest
from src.pipeline.confidence import compute_confidence, should_disambiguate

def test_high_confidence_gap():
    # rank-1 score 0.92, rank-2 score 0.61 → gap 0.31 > threshold 0.15
    assert compute_confidence(0.92, 0.61) == pytest.approx(0.31)
    assert should_disambiguate(0.92, 0.61, threshold=0.15) is False

def test_low_confidence_gap():
    # rank-1 score 0.85, rank-2 score 0.82 → gap 0.03 < threshold 0.15
    assert should_disambiguate(0.85, 0.82, threshold=0.15) is True

def test_single_result_no_disambiguate():
    assert should_disambiguate(0.90, None, threshold=0.15) is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_confidence.py -v
```

- [ ] **Step 3: Implement `src/pipeline/confidence.py`**

```python
def compute_confidence(rank1_score: float, rank2_score: float | None) -> float:
    """Gap between rank-1 and rank-2 scores as confidence proxy."""
    if rank2_score is None:
        return 1.0
    return rank1_score - rank2_score

def should_disambiguate(
    rank1_score: float,
    rank2_score: float | None,
    threshold: float = 0.15,
) -> bool:
    """True if scores are too close → needs disambiguation."""
    return compute_confidence(rank1_score, rank2_score) < threshold
```

- [ ] **Step 4: Implement `src/pipeline/strategy.py`**

```python
from abc import ABC, abstractmethod
from src.models import FindBestToolRequest, FindBestToolResponse

class PipelineStrategy(ABC):
    name: str

    @abstractmethod
    async def execute(self, request: FindBestToolRequest) -> FindBestToolResponse:
        ...

class StrategyRegistry:
    _strategies: dict[str, PipelineStrategy] = {}

    @classmethod
    def register(cls, strategy: PipelineStrategy):
        cls._strategies[strategy.name] = strategy

    @classmethod
    def get(cls, name: str) -> PipelineStrategy:
        if name not in cls._strategies:
            raise ValueError(f"Unknown strategy: {name}. Available: {list(cls._strategies)}")
        return cls._strategies[name]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_confidence.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/pipeline/ tests/unit/test_confidence.py
git commit -m "feat: PipelineStrategy interface + gap-based confidence"
```

---

### Task 3.2: Strategy A — Sequential 2-Layer Search

**Files:**
- Create: `src/pipeline/sequential.py`
- Create: `tests/unit/test_sequential.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_sequential.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.pipeline.sequential import SequentialStrategy
from src.models import FindBestToolRequest, SearchResult, MCPTool

@pytest.fixture
def mock_store():
    store = AsyncMock()
    tool = MCPTool(
        tool_id="brave/search", server_id="brave",
        tool_name="brave_web_search", description="Search the web"
    )
    store.search.return_value = [SearchResult(tool=tool, score=0.9, rank=1)]
    return store

@pytest.fixture
def mock_embedder():
    e = AsyncMock()
    import numpy as np
    e.embed_one.return_value = np.zeros(1536, dtype=np.float32)
    return e

@pytest.mark.asyncio
async def test_sequential_returns_response(mock_store, mock_embedder):
    strategy = SequentialStrategy(embedder=mock_embedder, store=mock_store)
    req = FindBestToolRequest(query="search the web", top_k=3)
    resp = await strategy.execute(req)
    assert resp.strategy_used == "sequential"
    assert len(resp.results) >= 1
    assert resp.latency_ms > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_sequential.py -v
```

- [ ] **Step 3: Implement `src/pipeline/sequential.py`**

```python
import time
from src.pipeline.strategy import PipelineStrategy
from src.pipeline.confidence import compute_confidence, should_disambiguate
from src.retrieval.qdrant_store import QdrantStore
from src.embedding.base import Embedder
from src.models import FindBestToolRequest, FindBestToolResponse
from src.config import settings

class SequentialStrategy(PipelineStrategy):
    name = "sequential"

    def __init__(self, embedder: Embedder, store: QdrantStore):
        self.embedder = embedder
        self.store = store

    async def execute(self, request: FindBestToolRequest) -> FindBestToolResponse:
        start = time.perf_counter()

        # Layer 1: Embed query, search tool index
        query_vec = await self.embedder.embed_one(request.query)
        results = await self.store.search(
            query_vec,
            collection=settings.qdrant_collection_tools,
            top_k=settings.top_k_retrieval,
        )

        # Layer 2: Re-rank top results (placeholder — Reranker injected in Phase 5)
        results = results[:request.top_k]

        # Confidence branching
        rank1_score = results[0].score if results else 0.0
        rank2_score = results[1].score if len(results) > 1 else None
        confidence = compute_confidence(rank1_score, rank2_score)
        disambig = should_disambiguate(rank1_score, rank2_score, settings.confidence_gap_threshold)

        latency_ms = (time.perf_counter() - start) * 1000
        return FindBestToolResponse(
            query=request.query,
            results=results,
            confidence=confidence,
            disambiguation_needed=disambig,
            strategy_used=self.name,
            latency_ms=latency_ms,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_sequential.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/sequential.py tests/unit/test_sequential.py
git commit -m "feat: Strategy A — sequential 2-layer pipeline"
```

---

## Phase 4: Ground Truth Generation

**Produces:** `data/ground_truth/` JSONL with (query, server_id, tool_id) triples. 50+ manually verified.

### Task 4.1: Synthetic Query Generator

**Files:**
- Create: `src/data/ground_truth.py`
- Create: `tests/unit/test_ground_truth.py`
- Create: `scripts/generate_ground_truth.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_ground_truth.py`:

```python
from unittest.mock import AsyncMock, patch
from src.data.ground_truth import GroundTruthGenerator
from src.models import MCPTool, GroundTruth

def test_parse_generated_queries():
    gen = GroundTruthGenerator(llm_client=None)
    tool = MCPTool(
        tool_id="semantic/search", server_id="semantic",
        tool_name="search_papers", description="Search academic papers"
    )
    raw_output = "find papers on transformers\nsearch for NLP research\nlook up LLM citations"
    queries = gen.parse_queries(raw_output, tool)
    assert len(queries) == 3
    assert queries[0].correct_tool_id == "semantic/search"
    assert queries[0].query == "find papers on transformers"
    assert queries[0].manually_verified is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_ground_truth.py -v
```

- [ ] **Step 3: Implement `src/data/ground_truth.py`**

```python
import json
from pathlib import Path
from openai import AsyncOpenAI
from src.models import MCPTool, GroundTruth

QUERY_GEN_PROMPT = """\
You are generating realistic user queries for evaluating an MCP tool recommender.
Given the tool below, generate {n} diverse queries that a user might ask when they need this tool.
Rules:
- Each query on a new line, no numbering
- Vary phrasing: natural language, abbreviated, cross-domain
- Include ambiguous queries where this tool is the best but not obvious choice
- Do NOT generate queries that only match this tool by exact name

Tool: {tool_name}
Description: {description}

Generate {n} queries:"""

class GroundTruthGenerator:
    def __init__(self, llm_client: AsyncOpenAI | None, model: str = "gpt-4o-mini"):
        self.client = llm_client
        self.model = model

    def parse_queries(self, raw: str, tool: MCPTool) -> list[GroundTruth]:
        lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
        return [
            GroundTruth(
                query=line,
                correct_server_id=tool.server_id,
                correct_tool_id=tool.tool_id,
            )
            for line in lines
        ]

    async def generate_for_tool(self, tool: MCPTool, n: int = 10) -> list[GroundTruth]:
        prompt = QUERY_GEN_PROMPT.format(
            n=n, tool_name=tool.tool_name, description=tool.description
        )
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )
        return self.parse_queries(resp.choices[0].message.content, tool)

    def save(self, ground_truth: list[GroundTruth], output_dir: str = "data/ground_truth"):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "synthetic.jsonl"
        with open(path, "w") as f:
            for gt in ground_truth:
                f.write(gt.model_dump_json() + "\n")
        print(f"Saved {len(ground_truth)} ground truth entries → {path}")
        return path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_ground_truth.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/data/ground_truth.py tests/unit/test_ground_truth.py
git commit -m "feat: synthetic ground truth generator"
```

---

## Phase 5: Evaluation Harness

**Produces:** `evaluate(strategy, queries, gt) → Metrics` with all 6 core metrics.

### Task 5.1: Evaluator Abstraction + Core Metrics

**Files:**
- Create: `src/evaluation/evaluator.py`
- Create: `src/evaluation/metrics/precision.py`
- Create: `src/evaluation/metrics/recall.py`
- Create: `src/evaluation/metrics/latency.py`
- Create: `src/evaluation/metrics/confusion_rate.py`
- Create: `src/evaluation/metrics/description_correlation.py`
- Create: `tests/evaluation/test_metrics.py`

- [ ] **Step 1: Write failing tests for all metrics**

Create `tests/evaluation/test_metrics.py`:

```python
import pytest
from src.evaluation.metrics.precision import PrecisionAt1
from src.evaluation.metrics.recall import RecallAtK
from src.evaluation.metrics.latency import LatencyMetric
from src.evaluation.metrics.confusion_rate import ConfusionRate
from src.evaluation.metrics.description_correlation import DescriptionQualityCorrelation
from src.models import SearchResult, MCPTool, FindBestToolResponse, GroundTruth

def make_tool(tool_id):
    return MCPTool(tool_id=tool_id, server_id="s", tool_name="t", description="d")

def make_response(tool_ids, query="test", latency_ms=50.0):
    results = [SearchResult(tool=make_tool(tid), score=1.0 - i*0.1, rank=i+1)
               for i, tid in enumerate(tool_ids)]
    return FindBestToolResponse(
        query=query, results=results,
        confidence=0.5, disambiguation_needed=False,
        strategy_used="sequential", latency_ms=latency_ms,
    )

def test_precision_at_1_correct():
    metric = PrecisionAt1()
    resp = make_response(["brave/search", "other/tool"])
    gt = GroundTruth(query="q", correct_server_id="brave", correct_tool_id="brave/search")
    assert metric.score(resp, gt) == 1.0

def test_precision_at_1_wrong():
    metric = PrecisionAt1()
    resp = make_response(["wrong/tool", "brave/search"])
    gt = GroundTruth(query="q", correct_server_id="brave", correct_tool_id="brave/search")
    assert metric.score(resp, gt) == 0.0

def test_recall_at_k():
    metric = RecallAtK(k=3)
    resp = make_response(["a/b", "brave/search", "c/d"])
    gt = GroundTruth(query="q", correct_server_id="brave", correct_tool_id="brave/search")
    assert metric.score(resp, gt) == 1.0

def test_recall_at_k_miss():
    metric = RecallAtK(k=3)
    resp = make_response(["a/b", "c/d", "e/f"])
    gt = GroundTruth(query="q", correct_server_id="brave", correct_tool_id="brave/search")
    assert metric.score(resp, gt) == 0.0

def test_latency_metric():
    metric = LatencyMetric()
    responses = [make_response([], latency_ms=50), make_response([], latency_ms=150)]
    stats = metric.aggregate(responses)
    assert stats["p50_ms"] == pytest.approx(50.0)
    assert stats["p95_ms"] == pytest.approx(150.0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/evaluation/test_metrics.py -v
```

- [ ] **Step 3: Implement evaluator base + precision + recall + latency**

Create `src/evaluation/evaluator.py`:

```python
from abc import ABC, abstractmethod
from src.models import FindBestToolResponse, GroundTruth

class Evaluator(ABC):
    name: str

    @abstractmethod
    def score(self, response: FindBestToolResponse, ground_truth: GroundTruth) -> float:
        ...
```

Create `src/evaluation/metrics/precision.py`:

```python
from src.evaluation.evaluator import Evaluator
from src.models import FindBestToolResponse, GroundTruth

class PrecisionAt1(Evaluator):
    name = "precision@1"

    def score(self, response: FindBestToolResponse, ground_truth: GroundTruth) -> float:
        if not response.results:
            return 0.0
        return 1.0 if response.results[0].tool.tool_id == ground_truth.correct_tool_id else 0.0
```

Create `src/evaluation/metrics/recall.py`:

```python
from src.evaluation.evaluator import Evaluator
from src.models import FindBestToolResponse, GroundTruth

class RecallAtK(Evaluator):
    def __init__(self, k: int = 10):
        self.k = k
        self.name = f"recall@{k}"

    def score(self, response: FindBestToolResponse, ground_truth: GroundTruth) -> float:
        top_k = response.results[:self.k]
        return 1.0 if any(r.tool.tool_id == ground_truth.correct_tool_id for r in top_k) else 0.0
```

Create `src/evaluation/metrics/latency.py`:

```python
import numpy as np
from src.models import FindBestToolResponse

class LatencyMetric:
    name = "latency"

    def aggregate(self, responses: list[FindBestToolResponse]) -> dict:
        latencies = sorted(r.latency_ms for r in responses)
        return {
            "p50_ms": float(np.percentile(latencies, 50)),
            "p95_ms": float(np.percentile(latencies, 95)),
            "p99_ms": float(np.percentile(latencies, 99)),
            "mean_ms": float(np.mean(latencies)),
        }
```

Create `src/evaluation/metrics/confusion_rate.py`:

```python
# Confusion Rate: fraction of errors where wrong tool is semantically similar to correct tool
# Reference: arxiv:2601.16280
from src.evaluation.evaluator import Evaluator
from src.models import FindBestToolResponse, GroundTruth

class ConfusionRate(Evaluator):
    """
    Score 1.0 if top-1 is wrong AND the correct tool appears in top-k (confused with similar tool).
    Score 0.0 if top-1 is correct, or correct tool not in top-k at all.
    """
    name = "confusion_rate"

    def __init__(self, k: int = 5):
        self.k = k

    def score(self, response: FindBestToolResponse, ground_truth: GroundTruth) -> float:
        if not response.results:
            return 0.0
        top1_correct = response.results[0].tool.tool_id == ground_truth.correct_tool_id
        if top1_correct:
            return 0.0
        # Wrong top-1. Is correct tool in top-k (confusion) or completely missed?
        in_topk = any(r.tool.tool_id == ground_truth.correct_tool_id for r in response.results[:self.k])
        return 1.0 if in_topk else 0.0
```

Create `src/evaluation/metrics/description_correlation.py`:

```python
"""
Core thesis metric: Spearman correlation between description quality score and selection rate.
Higher correlation proves "better description → more selections".
"""
from scipy.stats import spearmanr
import numpy as np

class DescriptionQualityCorrelation:
    name = "description_quality_correlation"

    def compute(
        self,
        quality_scores: list[float],   # SEO score per tool
        selection_rates: list[float],   # Precision@1 per tool across queries
    ) -> dict:
        if len(quality_scores) < 3:
            return {"spearman_r": None, "p_value": None, "n": len(quality_scores)}
        r, p = spearmanr(quality_scores, selection_rates)
        return {
            "spearman_r": float(r),
            "p_value": float(p),
            "n": len(quality_scores),
            "significant": p < 0.05,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/evaluation/test_metrics.py -v
```

- [ ] **Step 5: Implement `src/evaluation/harness.py`**

```python
import asyncio
import random
from dataclasses import dataclass, field
from src.pipeline.strategy import PipelineStrategy
from src.models import FindBestToolRequest, FindBestToolResponse, GroundTruth
from src.evaluation.evaluator import Evaluator
from src.evaluation.metrics.precision import PrecisionAt1
from src.evaluation.metrics.recall import RecallAtK
from src.evaluation.metrics.latency import LatencyMetric
from src.evaluation.metrics.confusion_rate import ConfusionRate

@dataclass
class EvalResult:
    strategy: str
    precision_at_1: float
    recall_at_10: float
    confusion_rate: float
    latency: dict
    n_queries: int
    per_query: list[dict] = field(default_factory=list)

async def evaluate(
    strategy: PipelineStrategy,
    test_queries: list[GroundTruth],
    top_k: int = 10,
) -> EvalResult:
    p1 = PrecisionAt1()
    r10 = RecallAtK(k=top_k)
    cr = ConfusionRate(k=5)
    latency_metric = LatencyMetric()

    responses = []
    per_query = []

    for gt in test_queries:
        req = FindBestToolRequest(query=gt.query, top_k=top_k)
        resp = await strategy.execute(req)
        # NOTE: position bias shuffling is NOT applied here.
        # Automated metrics (Precision@1, Recall@K) require deterministic rank order.
        # Position bias control applies only to human-judge evaluation studies,
        # not to automated metric computation against ground truth.
        responses.append(resp)
        per_query.append({
            "query": gt.query,
            "precision@1": p1.score(resp, gt),
            "recall@10": r10.score(resp, gt),
            "confusion": cr.score(resp, gt),
            "correct_tool": gt.correct_tool_id,
            "top1": resp.results[0].tool.tool_id if resp.results else None,
        })

    return EvalResult(
        strategy=strategy.name,
        precision_at_1=sum(x["precision@1"] for x in per_query) / len(per_query),
        recall_at_10=sum(x["recall@10"] for x in per_query) / len(per_query),
        confusion_rate=sum(x["confusion"] for x in per_query) / len(per_query),
        latency=latency_metric.aggregate(responses),
        n_queries=len(per_query),
        per_query=per_query,
    )
```

- [ ] **Step 6: Commit**

```bash
git add src/evaluation/ tests/evaluation/
git commit -m "feat: evaluation harness — Precision@1, Recall@K, Latency, Confusion Rate, harness"
```

---

### Task 5.2: ECE (Calibration) Metric — 6th Core Metric

**Files:**
- Create: `src/evaluation/metrics/calibration.py`
- Modify: `tests/evaluation/test_metrics.py`
- Modify: `src/evaluation/harness.py` (add `ece` field to `EvalResult`)

> **Why this matters**: ECE (Expected Calibration Error) measures whether `confidence` scores are honest — if confidence = 0.9, the system should be correct ~90% of the time. This is metric #5 in the confirmed baseline (Naeini et al., AAAI 2015). Without it, the "confidence" field in every response is unvalidated.

- [ ] **Step 1: Write failing test**

Add to `tests/evaluation/test_metrics.py`:

```python
from src.evaluation.metrics.calibration import ECEMetric

def test_ece_perfect_calibration():
    metric = ECEMetric(n_bins=5)
    # Confidences and correctness perfectly correlated
    confidences = [0.1, 0.3, 0.5, 0.7, 0.9]
    correct = [False, False, True, True, True]
    ece = metric.compute(confidences, correct)
    assert ece < 0.2  # not perfect but roughly calibrated

def test_ece_always_wrong_high_confidence():
    metric = ECEMetric(n_bins=5)
    confidences = [0.9, 0.9, 0.9, 0.9, 0.9]
    correct = [False, False, False, False, False]
    ece = metric.compute(confidences, correct)
    assert ece > 0.5  # badly miscalibrated

def test_ece_empty_returns_none():
    metric = ECEMetric(n_bins=5)
    assert metric.compute([], []) is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/evaluation/test_metrics.py::test_ece_perfect_calibration -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/evaluation/metrics/calibration.py`**

```python
"""
Expected Calibration Error (ECE).
Reference: Naeini et al., "Obtaining Well Calibrated Probabilities Using Bayesian Binning into Quantiles", AAAI 2015.

ECE = Σ (|B_m| / n) * |acc(B_m) - conf(B_m)|

Where B_m = bin m, acc = fraction correct in bin, conf = mean confidence in bin.
Lower ECE = better calibrated confidence scores.
"""
import numpy as np
from typing import Optional

class ECEMetric:
    name = "ece"

    def __init__(self, n_bins: int = 10):
        self.n_bins = n_bins

    def compute(
        self,
        confidences: list[float],
        correct: list[bool],
    ) -> Optional[float]:
        if not confidences:
            return None
        confidences = np.array(confidences)
        correct = np.array(correct, dtype=float)
        bin_boundaries = np.linspace(0, 1, self.n_bins + 1)
        ece = 0.0
        for lo, hi in zip(bin_boundaries[:-1], bin_boundaries[1:]):
            in_bin = (confidences >= lo) & (confidences < hi)
            if not in_bin.any():
                continue
            bin_acc = correct[in_bin].mean()
            bin_conf = confidences[in_bin].mean()
            bin_weight = in_bin.sum() / len(confidences)
            ece += bin_weight * abs(bin_acc - bin_conf)
        return float(ece)
```

- [ ] **Step 4: Add ECE to `EvalResult` in `src/evaluation/harness.py`**

```python
from src.evaluation.metrics.calibration import ECEMetric

# In EvalResult dataclass, add:
ece: Optional[float] = None

# In evaluate(), after collecting per_query:
ece_metric = ECEMetric()
confidences = [r.confidence for r in responses]
correct_flags = [pq["precision@1"] == 1.0 for pq in per_query]
ece = ece_metric.compute(confidences, correct_flags)

# In the return statement:
return EvalResult(
    ...,
    ece=ece,
)
```

- [ ] **Step 5: Run all metric tests**

```bash
uv run pytest tests/evaluation/test_metrics.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/evaluation/metrics/calibration.py tests/evaluation/test_metrics.py src/evaluation/harness.py
git commit -m "feat: ECE calibration metric — all 6 baseline metrics complete"
```

---

## Phase 6: Reranker

**Produces:** Cohere Rerank 3 integrated into the pipeline, with LLM fallback on low-confidence cases.

### Task 6.1: Reranker Abstraction + Cohere

**Files:**
- Create: `src/reranking/base.py`
- Create: `src/reranking/cohere_reranker.py`
- Create: `src/reranking/llm_fallback.py`
- Create: `tests/unit/test_reranker.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_reranker.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.reranking.base import Reranker
from src.models import SearchResult, MCPTool
import inspect

def make_result(tool_id, score):
    return SearchResult(
        tool=MCPTool(tool_id=tool_id, server_id="s", tool_name="t", description="d"),
        score=score, rank=1
    )

def test_reranker_is_abstract():
    assert inspect.isabstract(Reranker)

@pytest.mark.asyncio
async def test_cohere_reranker_reorders():
    from src.reranking.cohere_reranker import CohereReranker
    mock_cohere = AsyncMock()
    mock_cohere.rerank.return_value = MagicMock(results=[
        MagicMock(index=1, relevance_score=0.95),
        MagicMock(index=0, relevance_score=0.72),
    ])
    reranker = CohereReranker(client=mock_cohere)
    results = [make_result("a/b", 0.9), make_result("c/d", 0.85)]
    reranked = await reranker.rerank("test query", results, top_n=2)
    assert reranked[0].tool.tool_id == "c/d"  # index=1 wins
    assert reranked[0].score == pytest.approx(0.95)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_reranker.py -v
```

- [ ] **Step 3: Implement reranker stack**

Create `src/reranking/base.py`:

```python
from abc import ABC, abstractmethod
from src.models import SearchResult

class Reranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, results: list[SearchResult], top_n: int) -> list[SearchResult]:
        ...
```

Create `src/reranking/cohere_reranker.py`:

```python
import cohere
from src.reranking.base import Reranker
from src.models import SearchResult

class CohereReranker(Reranker):
    def __init__(self, client: cohere.AsyncClientV2 | None = None, api_key: str = ""):
        self._client = client or cohere.AsyncClientV2(api_key=api_key)

    async def rerank(self, query: str, results: list[SearchResult], top_n: int = 3) -> list[SearchResult]:
        if not results:
            return results
        docs = [f"{r.tool.tool_name}: {r.tool.description}" for r in results]
        response = await self._client.rerank(
            model="rerank-v3.5",
            query=query,
            documents=docs,
            top_n=top_n,
        )
        reranked = []
        for i, item in enumerate(response.results):
            result = results[item.index].model_copy(
                update={"score": item.relevance_score, "rank": i + 1}
            )
            reranked.append(result)
        return reranked
```

Create `src/reranking/llm_fallback.py`:

```python
from openai import AsyncOpenAI
from src.reranking.base import Reranker
from src.models import SearchResult

RERANK_PROMPT = """\
Given the user query: "{query}"

Rank these tools by relevance (most relevant first). Output ONLY the numbers separated by commas.
{candidates}"""

class LLMFallbackReranker(Reranker):
    """Used only for low-confidence cases where Cross-Encoder gap is small."""

    def __init__(self, client: AsyncOpenAI, model: str = "gpt-4o-mini"):
        self._client = client
        self.model = model

    async def rerank(self, query: str, results: list[SearchResult], top_n: int = 3) -> list[SearchResult]:
        candidates = "\n".join(
            f"{i+1}. {r.tool.tool_name}: {r.tool.description}" for i, r in enumerate(results)
        )
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": RERANK_PROMPT.format(
                query=query, candidates=candidates
            )}],
            temperature=0,
        )
        order = [int(x.strip()) - 1 for x in resp.choices[0].message.content.split(",")]
        reranked = []
        for rank, idx in enumerate(order[:top_n]):
            if 0 <= idx < len(results):
                reranked.append(results[idx].model_copy(update={"rank": rank + 1}))
        return reranked
```

- [ ] **Step 4: Wire Reranker into SequentialStrategy**

Edit `src/pipeline/sequential.py` — add optional `reranker` parameter:

```python
# In __init__:
self.reranker = reranker  # Optional[Reranker]

# In execute(), after store.search():
if self.reranker:
    results = await self.reranker.rerank(
        request.query, results, top_n=request.top_k
    )
else:
    results = results[:request.top_k]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_reranker.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/reranking/ tests/unit/test_reranker.py
git commit -m "feat: Cohere Rerank 3 + LLM fallback reranker"
```

---

## Phase 7: Hybrid Search (RRF + BGE-M3)

**Produces:** Hybrid dense+sparse retrieval via RRF fusion. Strategy B (Parallel) added.

### Task 7.1: RRF Fusion

**Files:**
- Create: `src/retrieval/hybrid.py`
- Create: `tests/unit/test_hybrid.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_hybrid.py`:

```python
from src.retrieval.hybrid import rrf_score, merge_results
from src.models import SearchResult, MCPTool

def make_result(tool_id, score, rank):
    return SearchResult(
        tool=MCPTool(tool_id=tool_id, server_id="s", tool_name="t", description="d"),
        score=score, rank=rank
    )

def test_rrf_score_formula():
    # score = 1/(60 + rank)
    assert rrf_score(rank=1, k=60) == pytest.approx(1/61)
    assert rrf_score(rank=60, k=60) == pytest.approx(1/120)

def test_merge_results_combines_lists():
    dense = [make_result("a", 0.9, 1), make_result("b", 0.8, 2)]
    sparse = [make_result("b", 0.85, 1), make_result("c", 0.7, 2)]
    merged = merge_results(dense, sparse, k=60, top_n=3)
    # "b" appears in both lists — should have highest combined RRF score
    assert merged[0].tool.tool_id == "b"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_hybrid.py -v
```

- [ ] **Step 3: Implement `src/retrieval/hybrid.py`**

```python
from collections import defaultdict
from src.models import SearchResult

def rrf_score(rank: int, k: int = 60) -> float:
    """Reciprocal Rank Fusion score. score = 1/(k + rank)."""
    return 1.0 / (k + rank)

def merge_results(
    *result_lists: list[SearchResult],
    k: int = 60,
    top_n: int = 10,
) -> list[SearchResult]:
    """Combine multiple ranked lists using RRF."""
    scores: dict[str, float] = defaultdict(float)
    tool_map: dict[str, SearchResult] = {}

    for results in result_lists:
        for r in results:
            tid = r.tool.tool_id
            scores[tid] += rrf_score(r.rank, k)
            if tid not in tool_map:
                tool_map[tid] = r

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:top_n]
    merged = []
    for rank, tid in enumerate(sorted_ids, 1):
        r = tool_map[tid].model_copy(update={"score": scores[tid], "rank": rank})
        merged.append(r)
    return merged
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_hybrid.py -v
```

- [ ] **Step 5: Create `src/pipeline/parallel.py`** (Strategy B)

```python
import asyncio
from src.pipeline.strategy import PipelineStrategy
from src.pipeline.confidence import compute_confidence, should_disambiguate
from src.retrieval.qdrant_store import QdrantStore
from src.retrieval.hybrid import merge_results
from src.embedding.base import Embedder
from src.reranking.base import Reranker
from src.models import FindBestToolRequest, FindBestToolResponse
from src.config import settings
import time

class ParallelStrategy(PipelineStrategy):
    """Strategy B: Query both server and tool indices in parallel, merge with RRF."""
    name = "parallel"

    def __init__(self, embedder: Embedder, store: QdrantStore, reranker: Reranker | None = None):
        self.embedder = embedder
        self.store = store
        self.reranker = reranker

    async def execute(self, request: FindBestToolRequest) -> FindBestToolResponse:
        start = time.perf_counter()
        query_vec = await self.embedder.embed_one(request.query)

        # Search both indices in parallel
        server_results, tool_results = await asyncio.gather(
            self.store.search(query_vec, settings.qdrant_collection_servers, top_k=5),
            self.store.search(query_vec, settings.qdrant_collection_tools, top_k=settings.top_k_retrieval),
        )

        # Merge with RRF
        merged = merge_results(server_results, tool_results, top_n=settings.top_k_retrieval)

        if self.reranker:
            merged = await self.reranker.rerank(request.query, merged, top_n=request.top_k)
        else:
            merged = merged[:request.top_k]

        rank1_score = merged[0].score if merged else 0.0
        rank2_score = merged[1].score if len(merged) > 1 else None
        confidence = compute_confidence(rank1_score, rank2_score)
        latency_ms = (time.perf_counter() - start) * 1000

        return FindBestToolResponse(
            query=request.query, results=merged,
            confidence=confidence,
            disambiguation_needed=should_disambiguate(rank1_score, rank2_score, settings.confidence_gap_threshold),
            strategy_used=self.name, latency_ms=latency_ms,
        )
```

- [ ] **Step 6: Commit**

```bash
git add src/retrieval/hybrid.py src/pipeline/parallel.py tests/unit/test_hybrid.py
git commit -m "feat: RRF fusion + Strategy B (parallel dual-index)"
```

---

## Phase 8: FastAPI + MCP Tool Server

**Produces:** Running FastAPI with `find_best_tool` endpoint + MCP Tool interface.

### Task 8.1: FastAPI Routes

**Files:**
- Create: `src/api/main.py`
- Create: `src/api/routes/search.py`
- Create: `tests/integration/test_api.py`

- [ ] **Step 1: Write failing test**

Create `tests/integration/test_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

@pytest.fixture
def client():
    with patch("src.api.main.strategy_registry") as mock_reg:
        mock_strategy = AsyncMock()
        from src.models import FindBestToolResponse
        mock_strategy.execute.return_value = FindBestToolResponse(
            query="test", results=[], confidence=0.9,
            disambiguation_needed=False, strategy_used="sequential", latency_ms=10.0
        )
        mock_reg.get.return_value = mock_strategy
        from src.api.main import app
        return TestClient(app)

def test_search_endpoint_returns_200(client):
    resp = client.post("/search", json={"query": "search the web", "top_k": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "search the web"
    assert "results" in data
    assert "confidence" in data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/integration/test_api.py -v
```

- [ ] **Step 3: Implement `src/api/routes/search.py`**

```python
from fastapi import APIRouter
from src.models import FindBestToolRequest, FindBestToolResponse
from src.pipeline.strategy import StrategyRegistry

router = APIRouter()

@router.post("/search", response_model=FindBestToolResponse)
async def find_best_tool(request: FindBestToolRequest) -> FindBestToolResponse:
    strategy = StrategyRegistry.get(request.strategy)
    return await strategy.execute(request)
```

- [ ] **Step 4: Implement `src/api/main.py`**

```python
from fastapi import FastAPI
from src.api.routes.search import router as search_router
from src.pipeline.strategy import StrategyRegistry

app = FastAPI(title="MCP Discovery API", version="0.1.0")
app.include_router(search_router)
strategy_registry = StrategyRegistry  # module-level ref for test patching

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/integration/test_api.py -v
```

- [ ] **Step 6: Verify server starts**

```bash
uv run uvicorn src.api.main:app --reload --port 8000
```

Expected: Server running at http://localhost:8000. Curl test:

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "search the web", "top_k": 3}'
```

- [ ] **Step 7: Commit**

```bash
git add src/api/ tests/integration/test_api.py
git commit -m "feat: FastAPI search endpoint"
```

---

## Phase 9: Provider Analytics

**Produces:** Logging pipeline + Provider REST API + SEO Score + Confusion Matrix + A/B Test runner.

### Task 9.1: Query Logger + Aggregator

**Files:**
- Create: `src/analytics/logger.py`
- Create: `src/analytics/aggregator.py`
- Create: `tests/unit/test_analytics.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_analytics.py`:

```python
import json
from pathlib import Path
import tempfile
from src.analytics.logger import QueryLogger
from src.models import FindBestToolResponse, SearchResult, MCPTool

def make_response(tool_id, score=0.9):
    tool = MCPTool(tool_id=tool_id, server_id="s", tool_name="t", description="d")
    return FindBestToolResponse(
        query="test", results=[SearchResult(tool=tool, score=score, rank=1)],
        confidence=0.5, disambiguation_needed=False,
        strategy_used="sequential", latency_ms=50.0,
    )

def test_logger_writes_jsonl():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = QueryLogger(log_dir=tmpdir)
        resp = make_response("brave/search")
        logger.log(resp)
        log_files = list(Path(tmpdir).glob("*.jsonl"))
        assert len(log_files) == 1
        with open(log_files[0]) as f:
            entry = json.loads(f.readline())
        assert entry["query"] == "test"
        assert entry["selected_tool_id"] == "brave/search"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_analytics.py -v
```

- [ ] **Step 3: Implement `src/analytics/logger.py`**

```python
import json
from datetime import datetime
from pathlib import Path
from src.models import FindBestToolResponse

class QueryLogger:
    def __init__(self, log_dir: str = "data/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _log_file(self) -> Path:
        date = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"{date}.jsonl"

    def log(self, response: FindBestToolResponse):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "query": response.query,
            "selected_tool_id": response.results[0].tool.tool_id if response.results else None,
            "selected_server_id": response.results[0].tool.server_id if response.results else None,
            "confidence": response.confidence,
            "disambiguation_needed": response.disambiguation_needed,
            "strategy_used": response.strategy_used,
            "latency_ms": response.latency_ms,
            "alternatives": [r.tool.tool_id for r in response.results[1:]],
        }
        with open(self._log_file(), "a") as f:
            f.write(json.dumps(entry) + "\n")
```

- [ ] **Step 4: Implement `src/analytics/aggregator.py`**

```python
import json
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class ToolStats:
    tool_id: str
    server_id: str
    selection_count: int = 0
    runner_up_count: int = 0      # appeared as alternative
    lost_to: dict = field(default_factory=lambda: defaultdict(int))  # {winner_id: count}

class LogAggregator:
    def __init__(self, log_dir: str = "data/logs"):
        self.log_dir = Path(log_dir)

    def aggregate(self, days: int = 7) -> dict[str, ToolStats]:
        stats: dict[str, ToolStats] = {}
        for log_file in sorted(self.log_dir.glob("*.jsonl"))[-days:]:
            with open(log_file) as f:
                for line in f:
                    entry = json.loads(line)
                    winner = entry.get("selected_tool_id")
                    if not winner:
                        continue
                    if winner not in stats:
                        stats[winner] = ToolStats(
                            tool_id=winner,
                            server_id=entry.get("selected_server_id", "")
                        )
                    stats[winner].selection_count += 1
                    for alt in entry.get("alternatives", []):
                        if alt not in stats:
                            stats[alt] = ToolStats(tool_id=alt, server_id="")
                        stats[alt].runner_up_count += 1
                        stats[alt].lost_to[winner] += 1
        return stats
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_analytics.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/analytics/logger.py src/analytics/aggregator.py tests/unit/test_analytics.py
git commit -m "feat: query logger + log aggregator for Provider Analytics"
```

---

### Task 9.2: Description SEO Score + A/B Test

**Files:**
- Create: `src/analytics/seo_score.py`
- Create: `src/analytics/ab_test.py`
- Create: `src/analytics/confusion_matrix.py`
- Create: `tests/unit/test_seo_score.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_seo_score.py`:

```python
from src.analytics.seo_score import DescriptionSEOScorer

def test_vague_description_scores_low():
    scorer = DescriptionSEOScorer()
    score = scorer.score("A tool for doing things.")
    assert score.total < 0.4

def test_specific_description_scores_high():
    scorer = DescriptionSEOScorer()
    desc = (
        "Search for academic papers on Semantic Scholar using keyword or natural language queries. "
        "Returns paper titles, authors, abstracts, and citation counts. "
        "Use this when the user needs to find research papers, NOT for web search or news."
    )
    score = scorer.score(desc)
    assert score.total > 0.7

def test_score_has_all_dimensions():
    scorer = DescriptionSEOScorer()
    score = scorer.score("test")
    assert hasattr(score, "specificity")
    assert hasattr(score, "disambiguation")
    assert hasattr(score, "parameter_coverage")
    assert hasattr(score, "total")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_seo_score.py -v
```

- [ ] **Step 3: Implement `src/analytics/seo_score.py`**

```python
from dataclasses import dataclass
import re

@dataclass
class SEOScore:
    specificity: float       # Are there specific use cases?
    disambiguation: float    # Does it say "NOT for X" or "vs Y"?
    parameter_coverage: float # Are parameters/inputs mentioned?
    total: float

class DescriptionSEOScorer:
    """
    Heuristic description quality scorer.
    Dimensions: Specificity, Disambiguation, Parameter Coverage.
    Each dimension 0–1. Total = weighted average.
    """

    def score(self, description: str) -> SEOScore:
        specificity = self._specificity(description)
        disambiguation = self._disambiguation(description)
        param_coverage = self._parameter_coverage(description)
        total = 0.4 * specificity + 0.4 * disambiguation + 0.2 * param_coverage
        return SEOScore(
            specificity=specificity,
            disambiguation=disambiguation,
            parameter_coverage=param_coverage,
            total=total,
        )

    def _specificity(self, text: str) -> float:
        # Rewards: multiple sentences, named examples, specific verbs
        sentences = len(re.split(r'[.!?]+', text.strip()))
        has_examples = bool(re.search(r'\b(e\.g\.|for example|such as|like)\b', text, re.I))
        word_count = len(text.split())
        length_score = min(word_count / 50, 1.0)
        return min((sentences * 0.2 + (0.3 if has_examples else 0) + length_score * 0.5), 1.0)

    def _disambiguation(self, text: str) -> float:
        # Rewards: NOT/AVOID/DO NOT, comparative language (vs, rather than)
        has_negative = bool(re.search(r'\b(not|never|avoid|do not|don\'t|instead of)\b', text, re.I))
        has_comparison = bool(re.search(r'\b(vs|versus|rather than|unlike|compared to)\b', text, re.I))
        return 0.5 * has_negative + 0.5 * has_comparison

    def _parameter_coverage(self, text: str) -> float:
        # Rewards: mentions of parameters, inputs, accepts, takes
        has_param_mention = bool(re.search(
            r'\b(parameter|input|accepts|takes|requires|argument|field)\b', text, re.I
        ))
        return 1.0 if has_param_mention else 0.0
```

- [ ] **Step 4: Implement `src/analytics/ab_test.py`**

```python
import asyncio
from src.models import MCPTool, GroundTruth, FindBestToolRequest
from src.pipeline.strategy import PipelineStrategy
from src.evaluation.metrics.precision import PrecisionAt1

class ABTestRunner:
    """
    Compare description variant A vs B on a synthetic query set.
    Returns winner and selection rate delta.

    KNOWN LIMITATION (Phase 9 MVP): This implementation labels variants A and B
    but does NOT actually swap the Qdrant payload before each evaluation arm.
    Both arms run against the same index, producing identical scores unless the
    caller manually re-indexes between arms. True variant testing requires:
      1. Upsert modified tool description payload to Qdrant (variant B)
      2. Run evaluation arm B
      3. Restore original payload (variant A)
    Full Qdrant payload swap flow will be implemented in Phase 13.
    """

    def __init__(self, strategy: PipelineStrategy, indexer):
        self.strategy = strategy
        self.indexer = indexer

    async def run(
        self,
        tool_id: str,
        description_a: str,
        description_b: str,
        test_queries: list[GroundTruth],
    ) -> dict:
        p1 = PrecisionAt1()
        results = {}
        for label, desc in [("A", description_a), ("B", description_b)]:
            # Re-index this tool with the new description, run eval
            # (In production, would swap Qdrant payload; here we simulate)
            scores = []
            for gt in test_queries:
                req = FindBestToolRequest(query=gt.query)
                resp = await self.strategy.execute(req)
                scores.append(p1.score(resp, gt))
            results[label] = {
                "selection_rate": sum(scores) / len(scores),
                "n_queries": len(scores),
            }
        winner = "A" if results["A"]["selection_rate"] >= results["B"]["selection_rate"] else "B"
        delta = results["B"]["selection_rate"] - results["A"]["selection_rate"]
        return {"results": results, "winner": winner, "delta": delta}
```

- [ ] **Step 5: Implement `src/analytics/confusion_matrix.py`**

```python
from collections import defaultdict
from src.analytics.aggregator import ToolStats

def build_confusion_matrix(stats: dict[str, ToolStats]) -> dict[str, dict]:
    """
    Returns per-tool confusion dict: {tool_id: {"lost_to": {competitor: count}, "win_rate": float}}
    """
    matrix = {}
    for tool_id, s in stats.items():
        total = s.selection_count + s.runner_up_count
        matrix[tool_id] = {
            "selections": s.selection_count,
            "runner_up": s.runner_up_count,
            "win_rate": s.selection_count / total if total > 0 else 0.0,
            "lost_to": dict(sorted(s.lost_to.items(), key=lambda x: x[1], reverse=True)[:5]),
        }
    return matrix
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_seo_score.py -v
```

- [ ] **Step 7: Commit**

```bash
git add src/analytics/seo_score.py src/analytics/ab_test.py src/analytics/confusion_matrix.py tests/unit/test_seo_score.py
git commit -m "feat: description SEO score + A/B test runner + confusion matrix"
```

---

### Task 9.3: Provider REST API

**Files:**
- Create: `src/api/routes/provider.py`
- Create: `tests/integration/test_provider_api.py`

- [ ] **Step 1: Write failing test**

Create `tests/integration/test_provider_api.py`:

```python
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_provider_stats_endpoint():
    resp = client.get("/provider/brave/stats")
    assert resp.status_code == 200

def test_provider_seo_score_endpoint():
    resp = client.post("/provider/seo-score", json={
        "description": "Search the web for current information using Brave Search API."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "specificity" in data
```

- [ ] **Step 2: Implement `src/api/routes/provider.py`**

```python
from fastapi import APIRouter
from pydantic import BaseModel
from src.analytics.aggregator import LogAggregator
from src.analytics.seo_score import DescriptionSEOScorer
from src.analytics.confusion_matrix import build_confusion_matrix

router = APIRouter(prefix="/provider")
aggregator = LogAggregator()
scorer = DescriptionSEOScorer()

class SEOScoreRequest(BaseModel):
    description: str

@router.get("/{server_id}/stats")
async def get_provider_stats(server_id: str):
    all_stats = aggregator.aggregate(days=7)
    server_tools = {tid: s for tid, s in all_stats.items() if s.server_id == server_id}
    return {
        "server_id": server_id,
        "tools": [
            {
                "tool_id": tid,
                "selections": s.selection_count,
                "runner_up": s.runner_up_count,
                "win_rate": s.selection_count / max(s.selection_count + s.runner_up_count, 1),
            }
            for tid, s in server_tools.items()
        ]
    }

@router.post("/seo-score")
async def get_seo_score(req: SEOScoreRequest):
    score = scorer.score(req.description)
    return score.__dict__

@router.get("/{server_id}/confusion")
async def get_confusion(server_id: str):
    all_stats = aggregator.aggregate(days=7)
    matrix = build_confusion_matrix(all_stats)
    server_matrix = {tid: v for tid, v in matrix.items() if tid.startswith(server_id)}
    return {"server_id": server_id, "confusion": server_matrix}
```

- [ ] **Step 3: Register provider router in `src/api/main.py`**

```python
from src.api.routes.provider import router as provider_router
app.include_router(provider_router)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/integration/test_provider_api.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/provider.py tests/integration/test_provider_api.py
git commit -m "feat: Provider REST API (stats, SEO score, confusion)"
```

---

## Phase 10: Experiment Runner + Description Correlation

**Produces:** `scripts/run_experiments.py` that compares all 3 strategies and computes core thesis metric.

### Task 10.1: Experiment Runner

**Files:**
- Create: `src/evaluation/experiment.py`
- Create: `scripts/run_experiments.py`
- Create: `tests/evaluation/test_experiment.py`

- [ ] **Step 1: Write failing test**

Create `tests/evaluation/test_experiment.py`:

```python
import pytest
from unittest.mock import AsyncMock
from src.evaluation.experiment import ExperimentRunner, ExperimentConfig
from src.models import GroundTruth

def test_experiment_config_validates():
    cfg = ExperimentConfig(
        pool_sizes=[5, 20],
        similarity_densities=["low", "high"],
        strategies=["sequential"],
    )
    assert cfg.pool_sizes == [5, 20]
```

- [ ] **Step 2: Implement `src/evaluation/experiment.py`**

```python
from dataclasses import dataclass, field
from src.pipeline.strategy import PipelineStrategy, StrategyRegistry
from src.evaluation.harness import evaluate, EvalResult
from src.models import GroundTruth

@dataclass
class ExperimentConfig:
    pool_sizes: list[int] = field(default_factory=lambda: [5, 20, 50, 100])
    similarity_densities: list[str] = field(default_factory=lambda: ["low", "medium", "high"])
    strategies: list[str] = field(default_factory=lambda: ["sequential", "parallel"])

class ExperimentRunner:
    def __init__(self, ground_truth: list[GroundTruth], config: ExperimentConfig):
        self.ground_truth = ground_truth
        self.config = config
        self.results: list[dict] = []

    async def run_all(self) -> list[dict]:
        for strategy_name in self.config.strategies:
            strategy = StrategyRegistry.get(strategy_name)
            result = await evaluate(strategy, self.ground_truth)
            self.results.append({
                "strategy": strategy_name,
                "precision@1": result.precision_at_1,
                "recall@10": result.recall_at_10,
                "confusion_rate": result.confusion_rate,
                "latency_p95_ms": result.latency["p95_ms"],
                "n_queries": result.n_queries,
            })
        return self.results

    def print_table(self):
        print(f"\n{'Strategy':<15} {'P@1':>8} {'R@10':>8} {'Confusion':>10} {'p95 ms':>8}")
        print("-" * 55)
        for r in self.results:
            print(f"{r['strategy']:<15} {r['precision@1']:>8.3f} {r['recall@10']:>8.3f} "
                  f"{r['confusion_rate']:>10.3f} {r['latency_p95_ms']:>8.1f}")
```

- [ ] **Step 3: Create `scripts/run_experiments.py`**

```python
#!/usr/bin/env python3
"""Compare all pipeline strategies on ground truth."""
import asyncio
import json
from pathlib import Path
from src.models import GroundTruth
from src.evaluation.experiment import ExperimentRunner, ExperimentConfig

async def main():
    gt_path = Path("data/ground_truth/synthetic.jsonl")
    ground_truth = [
        GroundTruth.model_validate_json(line)
        for line in gt_path.read_text().splitlines()
        if line.strip()
    ]
    print(f"Loaded {len(ground_truth)} ground truth queries.")

    config = ExperimentConfig(strategies=["sequential", "parallel"])
    runner = ExperimentRunner(ground_truth, config)
    results = await runner.run_all()
    runner.print_table()

    Path("data/experiments").mkdir(exist_ok=True)
    with open("data/experiments/strategy_comparison.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to data/experiments/strategy_comparison.json")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/evaluation/test_experiment.py -v
```

- [ ] **Step 5: Write failing test for Description Quality Correlation**

Add to `tests/evaluation/test_experiment.py`:

```python
from src.evaluation.metrics.description_correlation import DescriptionQualityCorrelation

def test_positive_correlation_detected():
    metric = DescriptionQualityCorrelation()
    # Tools with higher quality scores also have higher selection rates
    quality_scores = [0.2, 0.4, 0.6, 0.8, 0.95]
    selection_rates = [0.1, 0.3, 0.55, 0.75, 0.9]
    result = metric.compute(quality_scores, selection_rates)
    assert result["spearman_r"] > 0.8
    assert result["significant"] is True

def test_no_correlation_with_random_data():
    metric = DescriptionQualityCorrelation()
    quality_scores = [0.5, 0.5, 0.5, 0.5, 0.5]
    selection_rates = [0.1, 0.9, 0.5, 0.3, 0.7]
    result = metric.compute(quality_scores, selection_rates)
    assert result["spearman_r"] is not None  # computes even if not significant

def test_insufficient_data_returns_none_r():
    metric = DescriptionQualityCorrelation()
    result = metric.compute([0.5, 0.8], [0.4, 0.7])
    assert result["spearman_r"] is None
```

- [ ] **Step 6: Run test to verify it fails**

```bash
uv run pytest tests/evaluation/test_experiment.py -v
```

- [ ] **Step 7: Verify `description_correlation.py` passes the new tests**

```bash
uv run pytest tests/evaluation/test_experiment.py -v
```

Expected: PASS (the implementation was already written in Task 5.1).

- [ ] **Step 8: Add per-tool selection rate computation and Spearman correlation to the experiment runner**

In `src/evaluation/experiment.py`, after `run_all()`, add `compute_description_correlation()`:

```python
from src.evaluation.metrics.description_correlation import DescriptionQualityCorrelation
from src.analytics.seo_score import DescriptionSEOScorer

async def compute_description_correlation(
    tools: list,  # list[MCPTool]
    ground_truth: list[GroundTruth],
    strategy: PipelineStrategy,
) -> dict:
    """
    Core thesis validation: does description quality correlate with selection rate?
    Computes Spearman(SEO_score, Precision@1_per_tool).
    """
    from src.evaluation.harness import evaluate
    from src.evaluation.metrics.precision import PrecisionAt1
    scorer = DescriptionSEOScorer()
    p1 = PrecisionAt1()

    # Group ground truth by tool
    tool_gt: dict[str, list[GroundTruth]] = {}
    for gt in ground_truth:
        tool_gt.setdefault(gt.correct_tool_id, []).append(gt)

    quality_scores = []
    selection_rates = []
    for tool in tools:
        if tool.tool_id not in tool_gt:
            continue
        seo = scorer.score(tool.description).total
        tool_queries = tool_gt[tool.tool_id]
        precisions = []
        for gt in tool_queries:
            from src.models import FindBestToolRequest
            resp = await strategy.execute(FindBestToolRequest(query=gt.query))
            precisions.append(p1.score(resp, gt))
        quality_scores.append(seo)
        selection_rates.append(sum(precisions) / len(precisions))

    metric = DescriptionQualityCorrelation()
    return metric.compute(quality_scores, selection_rates)
```

- [ ] **Step 9: Commit**

```bash
git add src/evaluation/experiment.py tests/evaluation/test_experiment.py
git commit -m "feat: description quality ↔ selection rate Spearman correlation (core thesis metric)"
```

- [ ] **Step 6: Commit**

```bash
git add src/evaluation/experiment.py scripts/run_experiments.py tests/evaluation/test_experiment.py
git commit -m "feat: experiment runner + strategy comparison script"
```

---

## Phase 11: Instrumentation (Langfuse + W&B)

**Produces:** Every LLM call traced in Langfuse. Experiment metrics tracked in W&B.

### Task 11.1: Langfuse Tracing

**Files:**
- Modify: `src/api/routes/search.py`
- Modify: `src/reranking/llm_fallback.py`

- [ ] **Step 1: Add Langfuse to search route**

```python
from langfuse import Langfuse
from src.config import settings

langfuse = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
)

# In find_best_tool():
trace = langfuse.trace(name="find_best_tool", input={"query": request.query})
# ... execute strategy ...
trace.update(output={"top1": resp.results[0].tool.tool_id if resp.results else None,
                     "confidence": resp.confidence, "latency_ms": resp.latency_ms})
```

- [ ] **Step 2: Add W&B experiment logging**

In `scripts/run_experiments.py`:

```python
import wandb
wandb.init(project="mcp-discovery", name="strategy-comparison")
for r in results:
    wandb.log(r)
wandb.finish()
```

- [ ] **Step 3: Commit**

```bash
git add src/api/routes/search.py scripts/run_experiments.py
git commit -m "feat: Langfuse LLM tracing + W&B experiment tracking"
```

---

## Phase 12: End-to-End Smoke Test

**Produces:** Full pipeline running locally with real data.

- [ ] **Step 1: Run data collection**

```bash
uv run python scripts/collect_data.py
```

Expected: `data/raw/servers.jsonl` with 50+ servers.

- [ ] **Step 2: Build index**

```bash
uv run python scripts/build_index.py
```

Expected: Qdrant collection populated, "Indexed N tools" printed.

- [ ] **Step 3: Generate ground truth**

```bash
uv run python scripts/generate_ground_truth.py
```

Expected: `data/ground_truth/synthetic.jsonl` with 200+ queries.

- [ ] **Step 4: Run strategy comparison experiment**

```bash
uv run python scripts/run_experiments.py
```

Expected: Table with Precision@1, Recall@10, Confusion Rate, Latency across strategies.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest --cov=src --cov-report=term-missing -v
```

Expected: All tests pass. Coverage report generated.

- [ ] **Step 6: Start server and test manually**

```bash
uv run uvicorn src.api.main:app --reload
curl -X POST http://localhost:8000/search -H "Content-Type: application/json" \
  -d '{"query": "search for academic papers about transformers", "top_k": 3}'
```

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat: end-to-end smoke test passing — MCP Discovery Platform v0.1"
```

---

---

## Phase 13: Gated Features (Post-Core, After CTO Mentoring 2026-03-25)

> **Gate**: Do NOT start this phase until (a) Phases 0–12 are passing, AND (b) CTO mentoring on 2026-03-25 has confirmed Strategy C viability and MCP Tool server design.

### Task 13.1: Strategy C — Taxonomy-gated Search (stub)

**Files:**
- Create: `src/pipeline/taxonomy_gated.py`

```python
# TODO: Implement after CTO confirmation on 2026-03-25.
# Strategy C: Classify query intent → category, then search within category (JSPLIT method).
# Reference: JSPLIT paper.
# Gate: Confirm this adds value at ~1,000 tools scale before building.

from src.pipeline.strategy import PipelineStrategy
from src.models import FindBestToolRequest, FindBestToolResponse

class TaxonomyGatedStrategy(PipelineStrategy):
    name = "taxonomy_gated"

    async def execute(self, request: FindBestToolRequest) -> FindBestToolResponse:
        raise NotImplementedError("Strategy C pending CTO confirmation (2026-03-25)")
```

### Task 13.2: MCP Tool Server (DP1 second exposure)

**Files:**
- Create: `src/api/mcp_server.py`

**Goal**: Expose `find_best_tool` as an actual MCP Tool so LLMs can call it via the MCP protocol natively (not just REST). This is the "protocol-native" DP1 decision.

```python
# TODO: Implement using mcp Python SDK (pip install mcp).
# Expose find_best_tool(query: str, top_k: int = 3) as an MCP Tool.
# Wire to the same SequentialStrategy used by the REST endpoint.
# Reference: RAG-MCP paper (arxiv:2505.03275) — same approach.

# Minimal structure:
# from mcp.server import Server
# from mcp.server.stdio import stdio_server
# server = Server("mcp-discovery")
# @server.tool("find_best_tool")
# async def find_best_tool(query: str, top_k: int = 3) -> dict: ...
```

### Task 13.3: A/B Test with Real Qdrant Payload Swap

**Files:**
- Modify: `src/analytics/ab_test.py`

Replace the placeholder `ABTestRunner` with the full implementation:
1. Upsert variant B description to Qdrant (`store.upsert_tools([modified_tool], [re_embedded_vector], collection)`)
2. Run evaluation arm B against the live index
3. Upsert original description back (restore)
4. Return delta

---

## Design Discussion Log (2026-03-19)

> 구현 전 논의 사항. 이 결정들이 왜 내려졌는지 추적하기 위해 기록.

### Sequential 2-Layer 구현 버그 및 두 전략 비교 실험

**논의 내용**: Sequential 전략의 현재 구현(`sequential.py`)은 서버 인덱스를 거치지 않고 툴 인덱스를 바로 검색한다. 진짜 2-Layer라면:

```
True Sequential 2-Layer:
  1. 서버 인덱스 검색 → Top-3 서버
  2. 각 서버 내 툴 인덱스 필터링 검색 (server_id_filter)
  3. 후보 합산 → Reranker
```

**발견된 트레이드오프**:
- Sequential의 리스크: Layer 1에서 서버 분류 오류 → 정답 툴이 후보에서 완전히 제외됨
- Parallel(B)은 이 리스크 없음: 서버/툴 동시 검색 후 RRF 합산

**결정**: 두 방식 모두 올바르게 구현 후 동일 Ground Truth로 비교 실험. `sequential.py`를 올바른 2-Layer 구조로 수정 필요 (현재 플랜의 코드는 Layer 1이 빠진 상태). 서버 분류 오류율을 별도 지표로 측정.

**참고 파일**: `discovery/open-questions.md` — OQ-2, OQ-4

### SEO 점수 방식 미결

정규식 휴리스틱 방식의 한계 확인. 논문 리서치 후 LLM-based 방식과 비교 실험 예정. 핵심 테제(Spearman 상관계수)의 유효성이 SEO 점수 품질에 달려 있음. `discovery/open-questions.md` — OQ-1 참고.

### Provider 실증용 자체 MCP 서버 필요

Smithery 데이터만으로는 A/B 테스트 / 피드백 루프 데모 불가 (description 수정 권한 없음). 최소 3개 자체 MCP 서버 구축 예정. `discovery/open-questions.md` — OQ-3 참고.

---

## Open Questions (Resolve Before Implementation)

| # | Question | Action |
|---|----------|--------|
| 1 | BGE-M3 vs OpenAI embedder? | Run Phase 2 with both, compare Recall@10. Decide before Phase 3. |
| 2 | voyage-code-2? | **Do not use** — MCP descriptions are natural language, not code. |
| 3 | Taxonomy-gated (Strategy C) worth implementing at 1K tools scale? | Ask CTO mentoring 2026-03-25. Build A+B first. |
| 4 | Ground truth seed set size? | Ask CTO mentoring. Start with 50 manually verified. |
| 5 | Cross-Encoder alone sufficient for 5-week project? | Ask CTO mentoring. Start with Cohere Rerank 3 only. |

---

## CTO Mentoring Alignment (2026-03-25)

See `discovery/cto-mentoring-questions.md` for 7 questions. Key direction confirmations needed:
1. Strategy Pattern + all 3 strategies → compare experiment ✓ (confirm scale viability of C)
2. Cross-Encoder + LLM fallback → confirm for 5-week timeline
3. Ground truth approach → confirm 50 manual seed set minimum
4. 6 evaluation metrics → confirm completeness
5. Gap-based confidence proxy → confirm simplicity is acceptable

---

## Execution Notes

- Start from Phase 0 and execute sequentially within each phase.
- Each phase is independently committable and testable.
- Phases 0–7 = Core Pipeline (Sub-plan A). Phases 8–11 = Provider + Analytics (Sub-plan D).
- If running with subagents: one subagent per phase, two-stage review after each.
- All API keys in `.env` (copy `.env.example`). Never commit `.env`.
