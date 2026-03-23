# Architecture Rules — MCP Discovery Platform

## System Overview

MCP Discovery Platform — 양면 플랫폼 (LLM 고객 + Provider 고객)

```
LLM Client
    ↓
Bridge MCP Server (find_best_tool / execute_tool)
    ↓
Core Pipeline (2-Stage Retrieval)
    ↓ Stage 1              ↓ Stage 2
Embedding Search      Reranker + Confidence
    ↓                      ↓
Qdrant Vector Store   Cohere Rerank 3
                          ↓
                   Confidence Branching (gap > 0.15)
```

## Module Structure (Canonical Pattern)

```
src/
├── models.py              # MCPTool, MCPServer, SearchResult, GroundTruth
├── config.py              # pydantic-settings (BaseSettings)
├── pipeline/
│   ├── strategy.py        # PipelineStrategy ABC + StrategyRegistry
│   ├── sequential.py      # Strategy A
│   ├── parallel.py        # Strategy B
│   ├── taxonomy_gated.py  # Strategy C
│   └── confidence.py      # Gap-based confidence branching
├── embedding/
│   ├── base.py            # Embedder ABC
│   ├── bge_m3.py          # BGE-M3
│   └── openai_embedder.py # text-embedding-3-small
├── retrieval/
│   ├── qdrant_store.py    # Qdrant Cloud wrapper
│   └── hybrid.py          # RRF fusion
├── reranking/
│   ├── base.py            # Reranker ABC
│   ├── cohere_reranker.py # Cohere Rerank 3
│   └── llm_fallback.py    # LLM reranker (low-confidence)
├── data/
│   ├── crawler.py         # Smithery registry crawler
│   ├── mcp_connector.py   # Direct tools/list MCP
│   ├── ground_truth.py    # GT 생성 + Quality Gate
│   └── indexer.py         # Batch embed + Qdrant upsert
├── evaluation/
│   ├── harness.py         # evaluate(strategy, queries, gt)
│   ├── evaluator.py       # Evaluator ABC
│   ├── experiment.py      # ExperimentRunner, ExperimentConfig
│   └── metrics/           # Precision@1, Recall@K, ECE, etc.
├── analytics/
│   ├── logger.py          # Query log (JSONL)
│   ├── aggregator.py      # Log → ToolStats
│   ├── seo_score.py       # Description SEO score
│   └── ab_test.py         # A/B test runner
├── bridge/
│   ├── mcp_bridge.py      # Bridge MCP Server
│   ├── proxy.py           # execute_tool → Provider MCP proxy
│   └── registry.py        # Provider MCP endpoint cache
└── api/
    ├── main.py            # FastAPI app
    └── routes/            # search, provider analytics
```

## Architectural Decisions (Must Follow)

| DP | Rule |
|----|------|
| DP1 | MCP Tool (Bridge) + REST API 이중 노출 |
| DP2 | 2-Layer (서버 → Tool) 추천 — 서버 수준 필터 후 Tool 매칭 |
| DP3 | Strategy Pattern — A/B/C 모두 `PipelineStrategy` ABC 구현 |
| DP5 | Reranker: Cohere Rerank 3 + low-confidence LLM fallback |
| DP6 | Confidence 분기: gap 기반 (threshold 0.15) |
| DP8 | 배포: 로컬 FastAPI → Lambda + API Gateway |

## Design Patterns (Mandatory)

### Strategy Pattern — Pipeline

```python
from abc import ABC, abstractmethod

class PipelineStrategy(ABC):
    @abstractmethod
    async def search(self, query: str, top_k: int) -> list[SearchResult]:
        ...

class SequentialStrategy(PipelineStrategy):
    async def search(self, query: str, top_k: int) -> list[SearchResult]:
        servers = await self.server_index.search(query, top_k=5)
        tools = await self.tool_index.search(query, server_ids=[s.id for s in servers])
        return await self.reranker.rerank(query, tools, top_k=top_k)
```

All strategies registered via `StrategyRegistry` — 동일 평가 하네스로 비교.

### ABC Pattern — Embedder / Reranker / Evaluator

```python
class Embedder(ABC):
    @abstractmethod
    async def embed_one(self, text: str) -> np.ndarray: ...
    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]: ...
```

Concrete implementations handle provider specifics. Business logic depends on ABC only.

## Anti-Patterns (DO NOT USE)

```python
# WRONG: Direct embedding/reranking calls outside ABC
from openai import OpenAI
client = OpenAI()
response = client.embeddings.create(...)  # Use Embedder ABC

# WRONG: Hardcoded strategy selection
if strategy == "sequential":
    ...  # Use StrategyRegistry

# WRONG: Blocking I/O in async
result = requests.get(url)  # Use httpx.AsyncClient

# WRONG: voyage-code-2 embedding (DP4 금지)
embedder = VoyageEmbedder(model="voyage-code-2")  # 코드 특화, MCP description은 자연어
```

## Source of Truth

설계 문서가 SOT. 충돌 시 `docs/design/` 우선.

| 영역 | SOT 문서 |
|------|----------|
| 아키텍처 | `docs/design/architecture.md` |
| 평가 지표 | `docs/design/metrics-rubric.md` |
| Ground Truth | `docs/design/ground-truth-design.md` |
| 실험 설계 | `docs/design/experiment-design.md` |
| 코드 구조 | `docs/design/code-structure.md` |
