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

## Module Structure

> 아래는 현재 구현 + 계획을 구분한 구조. [planned]는 미구현.

Key models in `src/models.py`:
- `SearchResult`: tool + score + rank + reason + input_schema + score_breakdown (ScoreBreakdown) + is_boosted
- `ScoreBreakdown`: relevance + quality (0.0 MLP) + boost (0.0 MLP)

```
src/
├── models.py              # MCPTool, MCPServer, SearchResult, ScoreBreakdown, GroundTruthEntry
├── config.py              # pydantic-settings (BaseSettings)
├── pipeline/
│   ├── strategy.py        # PipelineStrategy ABC + StrategyRegistry
│   ├── flat.py            # 1-Layer (E0 baseline)
│   ├── sequential.py      # Strategy A
│   ├── confidence.py      # Gap-based confidence branching
│   ├── parallel.py        # [planned] Strategy B
│   └── taxonomy_gated.py  # [planned] Strategy C
├── embedding/
│   ├── base.py            # Embedder ABC
│   ├── openai_embedder.py # text-embedding-3-small
│   └── bge_m3.py          # [planned] BGE-M3
├── retrieval/
│   ├── qdrant_store.py    # Qdrant Cloud wrapper
│   └── hybrid.py          # [planned] RRF fusion
├── reranking/
│   ├── base.py            # Reranker ABC
│   ├── cohere_reranker.py # Cohere Rerank 3
│   └── llm_fallback.py    # [planned] LLM reranker (low-confidence)
├── data/
│   ├── crawler.py         # Smithery registry crawler
│   ├── smithery_client.py # Smithery HTTP client
│   ├── server_selector.py # Server selection logic
│   ├── mcp_connector.py   # Direct tools/list MCP
│   ├── ground_truth.py    # GT 생성 + Quality Gate
│   └── indexer.py         # Batch embed + Qdrant upsert
data/
├── external/              # 외부 데이터셋 (Git-ignored, 별도 다운로드)
│   ├── mcp-zero/          # MCP-Zero 308 servers (repo-local canonical input: servers.json)
│   ├── mcp-atlas/         # MCP-Atlas GT 원본 (*.parquet, 40 servers, 307 tools)
│   └── README.md          # 다운로드 방법, 라이선스
src/
├── evaluation/
│   ├── harness.py         # evaluate(strategy, queries, gt)
│   ├── evaluator.py       # Evaluator ABC
│   └── metrics.py         # Precision@1, Recall@K, MRR, NDCG@5, Confusion Rate, ECE, Latency
├── analytics/             # [planned]
│   ├── logger.py          # [planned] Query log (JSONL)
│   ├── aggregator.py      # [planned] Log → ToolStats
│   ├── geo_score.py       # [planned] Description GEO score
│   └── ab_test.py         # [planned] A/B test runner
├── bridge/                # [planned]
│   ├── mcp_bridge.py      # [planned] Bridge MCP Server
│   ├── proxy.py           # [planned] execute_tool → Provider MCP proxy
│   └── registry.py        # [planned] tool_id → ClientSession 매핑
└── api/                   # [planned]
    ├── main.py            # [planned] FastAPI app
    └── routes/            # search, provider analytics
```

## Architectural Decisions (Must Follow)

| DP | Rule |
|----|------|
| DP1 | MCP Tool (Bridge) + REST API 이중 노출 |
| DP2 | 2-Layer (서버 → Tool) 추천 — 서버 수준 필터 후 Tool 매칭 |
| DP3 | Strategy Pattern — A/B/C 모두 `PipelineStrategy` ABC 구현 |
| DP5 | Reranker: Cohere Rerank 3 (`rerank-v3.5`) + low-confidence LLM fallback |
| DP6 | Confidence 분기: gap 기반 (threshold 0.15) |
| DP8 | 배포: 로컬 FastAPI → Lambda + API Gateway |

> DP0 (우선순위), DP4 (임베딩 모델 — E2 실험 결정), DP7 (데이터 소스 — ADR-0011로 대체), DP9 (평가 체계)는 `docs/design/architecture.md` 참조.

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

## 외부 데이터 흐름 (ADR-0011)

```
External Sources (MCP-Zero, MCP-Atlas)
    ↓ import scripts (import_mcp_zero.py, convert_mcp_atlas.py)
data/external/ → data/ground_truth/ (변환 후 GT)
               → Qdrant (인덱싱 후 Tool Pool)
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
