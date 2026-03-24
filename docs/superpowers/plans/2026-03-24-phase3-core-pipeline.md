# Phase 3: Core Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement PipelineStrategy ABC + StrategyRegistry, gap-based confidence branching, FlatStrategy (1-Layer baseline for E0), and SequentialStrategy (true 2-Layer per OQ-4).

**Architecture:** Two strategies share a `PipelineStrategy` ABC and are registered via `StrategyRegistry`. `FlatStrategy` does direct tool vector search (1-Layer). `SequentialStrategy` does server-level search first, then filters tool search by server IDs (2-Layer). `compute_confidence()` computes gap-based confidence for downstream branching.

**Tech Stack:** Python 3.12, AsyncQdrantClient, Embedder ABC (existing), numpy, loguru, pytest-asyncio, unittest.mock

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/pipeline/__init__.py` | Re-export public API |
| Create | `src/pipeline/strategy.py` | `PipelineStrategy` ABC + `StrategyRegistry` |
| Create | `src/pipeline/confidence.py` | `compute_confidence()` — gap-based branching |
| Create | `src/pipeline/flat.py` | `FlatStrategy` — 1-Layer direct tool search |
| Create | `src/pipeline/sequential.py` | `SequentialStrategy` — 2-Layer server→tool |
| Modify | `src/retrieval/qdrant_store.py` | Add `search_server_ids()` method |
| Create | `tests/unit/test_pipeline_strategy.py` | ABC + registry tests |
| Create | `tests/unit/test_confidence.py` | Confidence branching tests |
| Create | `tests/unit/test_flat_strategy.py` | FlatStrategy tests |
| Create | `tests/unit/test_sequential_strategy.py` | SequentialStrategy tests |

---

## Task 1: PipelineStrategy ABC + StrategyRegistry

**Files:**
- Create: `src/pipeline/strategy.py`
- Create: `tests/unit/test_pipeline_strategy.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_pipeline_strategy.py
"""Tests for PipelineStrategy ABC and StrategyRegistry."""
import pytest
from unittest.mock import AsyncMock

from models import SearchResult, MCPTool
from pipeline.strategy import PipelineStrategy, StrategyRegistry


def make_tool(server_id: str = "srv", tool_name: str = "tool") -> MCPTool:
    return MCPTool(
        server_id=server_id,
        tool_name=tool_name,
        tool_id=f"{server_id}::{tool_name}",
    )


class ConcreteStrategy(PipelineStrategy):
    async def search(self, query: str, top_k: int) -> list[SearchResult]:
        return [SearchResult(tool=make_tool(), score=0.9, rank=1)]


class TestPipelineStrategyABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            PipelineStrategy()

    async def test_concrete_strategy_search(self):
        strategy = ConcreteStrategy()
        results = await strategy.search("test", top_k=3)
        assert len(results) == 1
        assert results[0].score == 0.9


class TestStrategyRegistry:
    def setup_method(self):
        # Isolate registry state per test
        self._original = StrategyRegistry._registry.copy()

    def teardown_method(self):
        StrategyRegistry._registry.clear()
        StrategyRegistry._registry.update(self._original)

    def test_register_and_get(self):
        @StrategyRegistry.register("test_strat")
        class TestStrat(PipelineStrategy):
            async def search(self, query: str, top_k: int) -> list[SearchResult]:
                return []

        assert StrategyRegistry.get("test_strat") is TestStrat

    def test_get_unknown_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            StrategyRegistry.get("nonexistent_xyz_abc")

    def test_list_strategies_includes_registered(self):
        @StrategyRegistry.register("test_list_strat")
        class ListStrat(PipelineStrategy):
            async def search(self, query: str, top_k: int) -> list[SearchResult]:
                return []

        assert "test_list_strat" in StrategyRegistry.list_strategies()

    def test_register_decorator_returns_class_unchanged(self):
        @StrategyRegistry.register("test_decorator")
        class DecoratorStrat(PipelineStrategy):
            async def search(self, query: str, top_k: int) -> list[SearchResult]:
                return []

        # Decorator must return the class itself
        assert DecoratorStrat.__name__ == "DecoratorStrat"
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
cd /Users/iyeonjae/Desktop/shockwave/mcp-discovery
uv run pytest tests/unit/test_pipeline_strategy.py -v
```
Expected: `ModuleNotFoundError: No module named 'pipeline'`

- [ ] **Step 3: Create `src/pipeline/strategy.py`**

```python
"""PipelineStrategy ABC and StrategyRegistry."""

from abc import ABC, abstractmethod

from models import SearchResult


class PipelineStrategy(ABC):
    """Abstract base class for all retrieval pipeline strategies.

    Implementations: FlatStrategy (1-Layer), SequentialStrategy (2-Layer),
    ParallelStrategy (RRF fusion).
    All concrete strategies must be registered via StrategyRegistry.
    """

    @abstractmethod
    async def search(self, query: str, top_k: int) -> list[SearchResult]:
        """Execute the retrieval pipeline for a query.

        Args:
            query: Natural language query from the LLM client.
            top_k: Number of results to return.

        Returns:
            Ranked list of SearchResult, highest score first.
        """


class StrategyRegistry:
    """Maps strategy names to PipelineStrategy subclasses.

    Usage:
        @StrategyRegistry.register("sequential")
        class SequentialStrategy(PipelineStrategy):
            ...

        StrategyClass = StrategyRegistry.get("sequential")
        strategy = StrategyClass(embedder=..., tool_store=...)
    """

    _registry: dict[str, type[PipelineStrategy]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator: register a PipelineStrategy subclass under name."""

        def decorator(klass: type[PipelineStrategy]) -> type[PipelineStrategy]:
            cls._registry[name] = klass
            return klass

        return decorator

    @classmethod
    def get(cls, name: str) -> type[PipelineStrategy]:
        """Return the registered strategy class for name.

        Raises:
            ValueError: if name is not registered.
        """
        if name not in cls._registry:
            available = list(cls._registry)
            raise ValueError(f"Unknown strategy '{name}'. Available: {available}")
        return cls._registry[name]

    @classmethod
    def list_strategies(cls) -> list[str]:
        """Return all registered strategy names."""
        return list(cls._registry.keys())
```

- [ ] **Step 4: Create `src/pipeline/__init__.py`**

```python
"""Pipeline strategies for MCP Discovery Platform."""

from pipeline.confidence import compute_confidence
from pipeline.strategy import PipelineStrategy, StrategyRegistry

__all__ = ["PipelineStrategy", "StrategyRegistry", "compute_confidence"]
```

- [ ] **Step 5: Run tests — verify they PASS**

```bash
uv run pytest tests/unit/test_pipeline_strategy.py -v
```
Expected: All 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/pipeline/strategy.py src/pipeline/__init__.py tests/unit/test_pipeline_strategy.py
git commit -m "feat(pipeline): add PipelineStrategy ABC and StrategyRegistry"
```

---

## Task 2: Gap-Based Confidence Branching

**Files:**
- Create: `src/pipeline/confidence.py`
- Create: `tests/unit/test_confidence.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_confidence.py
"""Tests for gap-based confidence branching."""
import pytest

from models import MCPTool, SearchResult
from pipeline.confidence import compute_confidence


def make_result(score: float, rank: int = 1, server_id: str = "srv") -> SearchResult:
    tool = MCPTool(
        server_id=server_id,
        tool_name=f"tool_{rank}",
        tool_id=f"{server_id}::tool_{rank}",
    )
    return SearchResult(tool=tool, score=score, rank=rank)


class TestComputeConfidence:
    def test_empty_results_returns_zero_confidence_and_needs_disambiguation(self):
        confidence, needs_disambiguation = compute_confidence([])
        assert confidence == 0.0
        assert needs_disambiguation is True

    def test_single_result_returns_its_score_no_disambiguation(self):
        result = make_result(score=0.9, rank=1)
        confidence, needs_disambiguation = compute_confidence([result])
        assert confidence == pytest.approx(0.9)
        assert needs_disambiguation is False

    def test_gap_above_threshold_no_disambiguation(self):
        # gap = 0.9 - 0.7 = 0.2 > 0.15 → clear winner, no ambiguity
        results = [make_result(0.9, 1), make_result(0.7, 2)]
        confidence, needs_disambiguation = compute_confidence(results)
        assert confidence == pytest.approx(0.9)
        assert needs_disambiguation is False

    def test_gap_below_threshold_needs_disambiguation(self):
        # gap = 0.8 - 0.72 = 0.08 < 0.15 → ambiguous
        results = [make_result(0.8, 1), make_result(0.72, 2)]
        confidence, needs_disambiguation = compute_confidence(results)
        assert confidence == pytest.approx(0.8)
        assert needs_disambiguation is True

    def test_gap_exactly_at_threshold_no_disambiguation(self):
        # gap = 0.15 == 0.15 → boundary: not ambiguous (gap >= threshold)
        results = [make_result(0.9, 1), make_result(0.75, 2)]
        confidence, needs_disambiguation = compute_confidence(results)
        assert needs_disambiguation is False

    def test_custom_gap_threshold(self):
        # With threshold=0.05, gap=0.08 is now clear enough
        results = [make_result(0.8, 1), make_result(0.72, 2)]
        _, needs_disambiguation = compute_confidence(results, gap_threshold=0.05)
        assert needs_disambiguation is False

    def test_uses_top_two_only(self):
        # Only rank1 and rank2 matter for gap calculation
        results = [make_result(0.9, 1), make_result(0.5, 2), make_result(0.1, 3)]
        confidence, needs_disambiguation = compute_confidence(results)
        assert confidence == pytest.approx(0.9)
        assert needs_disambiguation is False  # gap = 0.4 > 0.15
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
uv run pytest tests/unit/test_confidence.py -v
```
Expected: `ModuleNotFoundError: No module named 'pipeline.confidence'`

- [ ] **Step 3: Create `src/pipeline/confidence.py`**

```python
"""Gap-based confidence branching for retrieval results."""

from models import SearchResult


def compute_confidence(
    results: list[SearchResult],
    gap_threshold: float = 0.15,
) -> tuple[float, bool]:
    """Compute confidence score and disambiguation flag from ranked results.

    Uses the score gap between rank-1 and rank-2 to determine confidence.
    A small gap means the top two results are close — the LLM may need to
    ask for clarification (disambiguation_needed=True).

    Args:
        results: Ranked SearchResults, highest score first.
        gap_threshold: Minimum gap for a clear winner. Default 0.15 (from config).

    Returns:
        (confidence, needs_disambiguation):
            confidence: Score of the top result (0.0 if no results).
            needs_disambiguation: True if gap < threshold or no results.
    """
    if not results:
        return 0.0, True

    confidence = results[0].score

    if len(results) == 1:
        return confidence, False

    gap = results[0].score - results[1].score
    needs_disambiguation = gap < gap_threshold
    return confidence, needs_disambiguation
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
uv run pytest tests/unit/test_confidence.py -v
```
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/confidence.py tests/unit/test_confidence.py
git commit -m "feat(pipeline): add gap-based confidence branching"
```

---

## Task 3: FlatStrategy — 1-Layer Baseline (E0)

**Files:**
- Create: `src/pipeline/flat.py`
- Create: `tests/unit/test_flat_strategy.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_flat_strategy.py
"""Tests for FlatStrategy — 1-Layer direct tool search."""
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock

from models import MCPTool, SearchResult
from pipeline.strategy import StrategyRegistry
from pipeline.flat import FlatStrategy


def make_tool(n: int = 0) -> MCPTool:
    return MCPTool(
        server_id=f"@srv{n}",
        tool_name=f"tool{n}",
        tool_id=f"@srv{n}::tool{n}",
    )


def make_search_result(n: int = 0, score: float = 0.9) -> SearchResult:
    return SearchResult(tool=make_tool(n), score=score, rank=n + 1)


@pytest.fixture
def mock_embedder():
    embedder = AsyncMock()
    embedder.embed_one = AsyncMock(return_value=np.zeros(1536))
    return embedder


@pytest.fixture
def mock_tool_store():
    store = AsyncMock()
    store.search = AsyncMock(return_value=[make_search_result(0), make_search_result(1, 0.8)])
    return store


class TestFlatStrategy:
    async def test_search_embeds_query(self, mock_embedder, mock_tool_store):
        strategy = FlatStrategy(embedder=mock_embedder, tool_store=mock_tool_store)
        await strategy.search("find a github tool", top_k=3)
        mock_embedder.embed_one.assert_called_once_with("find a github tool")

    async def test_search_calls_tool_store_with_query_vector(
        self, mock_embedder, mock_tool_store
    ):
        strategy = FlatStrategy(embedder=mock_embedder, tool_store=mock_tool_store)
        await strategy.search("test query", top_k=5)
        mock_tool_store.search.assert_called_once()
        call_kwargs = mock_tool_store.search.call_args
        assert call_kwargs.kwargs["top_k"] == 5

    async def test_search_returns_results_from_store(self, mock_embedder, mock_tool_store):
        strategy = FlatStrategy(embedder=mock_embedder, tool_store=mock_tool_store)
        results = await strategy.search("test", top_k=3)
        assert len(results) == 2
        assert results[0].score == 0.9

    async def test_search_no_server_filter(self, mock_embedder, mock_tool_store):
        """FlatStrategy must NOT apply any server_id filter."""
        strategy = FlatStrategy(embedder=mock_embedder, tool_store=mock_tool_store)
        await strategy.search("test", top_k=3)
        call_kwargs = mock_tool_store.search.call_args.kwargs
        assert call_kwargs.get("server_id_filter") is None

    def test_registered_as_flat(self):
        assert "flat" in StrategyRegistry.list_strategies()
        assert StrategyRegistry.get("flat") is FlatStrategy
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
uv run pytest tests/unit/test_flat_strategy.py -v
```
Expected: `ModuleNotFoundError: No module named 'pipeline.flat'`

- [ ] **Step 3: Create `src/pipeline/flat.py`**

```python
"""FlatStrategy — 1-Layer direct tool search (E0 baseline)."""

import numpy as np
from loguru import logger

from embedding.base import Embedder
from models import SearchResult
from pipeline.strategy import PipelineStrategy, StrategyRegistry
from retrieval.qdrant_store import QdrantStore


@StrategyRegistry.register("flat")
class FlatStrategy(PipelineStrategy):
    """1-Layer pipeline: embed query → search tool index directly.

    Used as the E0 baseline to compare against 2-Layer strategies.
    No server-level filtering — searches all tools in the collection.
    """

    def __init__(self, embedder: Embedder, tool_store: QdrantStore) -> None:
        self.embedder = embedder
        self.tool_store = tool_store

    async def search(self, query: str, top_k: int) -> list[SearchResult]:
        """Search all tools directly without server-level filtering.

        Args:
            query: Natural language query.
            top_k: Number of results to return.

        Returns:
            Top-k SearchResults ranked by vector similarity.
        """
        logger.info(f"FlatStrategy.search: query='{query[:60]}', top_k={top_k}")
        query_vector: np.ndarray = await self.embedder.embed_one(query)
        results = await self.tool_store.search(
            query_vector=query_vector,
            top_k=top_k,
            server_id_filter=None,
        )
        logger.info(f"FlatStrategy: {len(results)} results returned")
        return results
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
uv run pytest tests/unit/test_flat_strategy.py -v
```
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/flat.py tests/unit/test_flat_strategy.py
git commit -m "feat(pipeline): add FlatStrategy 1-Layer baseline for E0"
```

---

## Task 4: Add `search_server_ids()` to QdrantStore

**Files:**
- Modify: `src/retrieval/qdrant_store.py`
- Modify: `tests/unit/test_qdrant_store.py`

`SequentialStrategy` needs server-level search. `QdrantStore` is reused with `mcp_servers` collection — but `search()` returns `SearchResult[MCPTool]` which doesn't work for servers. Add a dedicated `search_server_ids()` that extracts `server_id` fields from payloads.

- [ ] **Step 1: Add failing test to `test_qdrant_store.py`**

Append this class to the existing file:

```python
class TestSearchServerIds:
    async def test_returns_server_ids_from_payloads(self):
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value=[
                MagicMock(payload={"server_id": "srv1", "name": "Server 1"}),
                MagicMock(payload={"server_id": "srv2", "name": "Server 2"}),
            ]
        )
        store = QdrantStore(client=mock_client, collection_name="mcp_servers")
        server_ids = await store.search_server_ids(np.zeros(1536), top_k=5)
        assert server_ids == ["srv1", "srv2"]

    async def test_skips_payloads_without_server_id(self):
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value=[
                MagicMock(payload={"server_id": "srv1"}),
                MagicMock(payload={"name": "no_server_id_here"}),  # missing
                MagicMock(payload=None),  # null payload
            ]
        )
        store = QdrantStore(client=mock_client, collection_name="mcp_servers")
        server_ids = await store.search_server_ids(np.zeros(1536), top_k=5)
        assert server_ids == ["srv1"]  # only valid ones returned

    async def test_passes_top_k_to_client(self):
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=[])
        store = QdrantStore(client=mock_client, collection_name="mcp_servers")
        await store.search_server_ids(np.zeros(1536), top_k=7)
        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs["limit"] == 7
```

Also add `from unittest.mock import AsyncMock, MagicMock` to the imports at the top of `test_qdrant_store.py`.

- [ ] **Step 2: Run tests — verify the new tests FAIL**

```bash
uv run pytest tests/unit/test_qdrant_store.py::TestSearchServerIds -v
```
Expected: `AttributeError: 'QdrantStore' object has no attribute 'search_server_ids'`

- [ ] **Step 3: Add `search_server_ids()` to `QdrantStore`**

Add after the existing `search()` method in `src/retrieval/qdrant_store.py`:

```python
    async def search_server_ids(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
    ) -> list[str]:
        """Search collection and extract server_id from each hit's payload.

        Use with mcp_servers collection. Payloads must contain 'server_id'.
        Hits without 'server_id' in payload are silently skipped.

        Args:
            query_vector: Embedded query vector.
            top_k: Maximum number of servers to return.

        Returns:
            List of server_id strings, ordered by relevance score.
        """
        try:
            results = await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector.tolist(),
                limit=top_k,
            )
        except Exception as e:
            logger.error(f"Qdrant server search failed: {e}")
            raise
        server_ids = []
        for hit in results:
            if hit.payload and (sid := hit.payload.get("server_id")):
                server_ids.append(sid)
        return server_ids
```

- [ ] **Step 4: Run tests — verify all QdrantStore tests PASS**

```bash
uv run pytest tests/unit/test_qdrant_store.py -v
```
Expected: All tests PASS (including new `TestSearchServerIds`).

- [ ] **Step 5: Commit**

```bash
git add src/retrieval/qdrant_store.py tests/unit/test_qdrant_store.py
git commit -m "feat(retrieval): add search_server_ids() for 2-Layer pipeline"
```

---

## Task 5: SequentialStrategy — True 2-Layer (OQ-4 Fix)

**Files:**
- Create: `src/pipeline/sequential.py`
- Create: `tests/unit/test_sequential_strategy.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_sequential_strategy.py
"""Tests for SequentialStrategy — true 2-Layer server→tool pipeline."""
import numpy as np
import pytest
from unittest.mock import AsyncMock, call

from models import MCPTool, SearchResult
from pipeline.strategy import StrategyRegistry
from pipeline.sequential import SequentialStrategy


def make_tool(server_id: str, name: str = "tool") -> MCPTool:
    return MCPTool(
        server_id=server_id,
        tool_name=name,
        tool_id=f"{server_id}::{name}",
    )


def make_result(server_id: str, name: str = "tool", score: float = 0.9) -> SearchResult:
    return SearchResult(tool=make_tool(server_id, name), score=score, rank=1)


@pytest.fixture
def mock_embedder():
    embedder = AsyncMock()
    embedder.embed_one = AsyncMock(return_value=np.zeros(1536))
    return embedder


@pytest.fixture
def mock_server_store():
    store = AsyncMock()
    store.search_server_ids = AsyncMock(return_value=["srv1", "srv2"])
    return store


@pytest.fixture
def mock_tool_store():
    store = AsyncMock()
    # Return 1 result per server
    store.search = AsyncMock(
        side_effect=[
            [make_result("srv1", "tool_a", score=0.9)],
            [make_result("srv2", "tool_b", score=0.7)],
        ]
    )
    return store


class TestSequentialStrategy:
    async def test_embeds_query_once(
        self, mock_embedder, mock_server_store, mock_tool_store
    ):
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        await strategy.search("find github tool", top_k=3)
        mock_embedder.embed_one.assert_called_once_with("find github tool")

    async def test_searches_server_index_first(
        self, mock_embedder, mock_server_store, mock_tool_store
    ):
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        await strategy.search("test", top_k=3)
        mock_server_store.search_server_ids.assert_called_once()

    async def test_filters_tool_search_by_server_id(
        self, mock_embedder, mock_server_store, mock_tool_store
    ):
        """Layer 2 must filter by each server_id returned from Layer 1."""
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        await strategy.search("test", top_k=3)
        # Should call tool_store.search once per server
        assert mock_tool_store.search.call_count == 2
        calls = mock_tool_store.search.call_args_list
        server_filters = [c.kwargs["server_id_filter"] for c in calls]
        assert "srv1" in server_filters
        assert "srv2" in server_filters

    async def test_results_sorted_by_score_descending(
        self, mock_embedder, mock_server_store, mock_tool_store
    ):
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        results = await strategy.search("test", top_k=3)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    async def test_ranks_are_reassigned_after_merge(
        self, mock_embedder, mock_server_store, mock_tool_store
    ):
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        results = await strategy.search("test", top_k=3)
        for i, r in enumerate(results):
            assert r.rank == i + 1

    async def test_top_k_limits_returned_results(
        self, mock_embedder, mock_server_store, mock_tool_store
    ):
        # mock returns 1 result per server = 2 total; request top_k=1
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=mock_server_store,
        )
        results = await strategy.search("test", top_k=1)
        assert len(results) == 1

    async def test_empty_server_results_returns_empty(
        self, mock_embedder, mock_tool_store
    ):
        server_store = AsyncMock()
        server_store.search_server_ids = AsyncMock(return_value=[])
        strategy = SequentialStrategy(
            embedder=mock_embedder,
            tool_store=mock_tool_store,
            server_store=server_store,
        )
        results = await strategy.search("test", top_k=3)
        assert results == []
        mock_tool_store.search.assert_not_called()

    def test_registered_as_sequential(self):
        assert "sequential" in StrategyRegistry.list_strategies()
        assert StrategyRegistry.get("sequential") is SequentialStrategy
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
uv run pytest tests/unit/test_sequential_strategy.py -v
```
Expected: `ModuleNotFoundError: No module named 'pipeline.sequential'`

- [ ] **Step 3: Create `src/pipeline/sequential.py`**

```python
"""SequentialStrategy — true 2-Layer server→tool pipeline (OQ-4)."""

import numpy as np
from loguru import logger

from embedding.base import Embedder
from models import SearchResult
from pipeline.strategy import PipelineStrategy, StrategyRegistry
from retrieval.qdrant_store import QdrantStore


@StrategyRegistry.register("sequential")
class SequentialStrategy(PipelineStrategy):
    """2-Layer pipeline: server index → filtered tool search.

    Layer 1: Embed query, search mcp_servers collection → top server IDs.
    Layer 2: For each server ID, search mcp_tools filtered by server_id.
    Merge all tool results, sort by score, re-rank, return top_k.

    This is the reference implementation for OQ-4 fix (true 2-Layer).
    Compare against FlatStrategy in E0 to validate 2-Layer benefit.
    """

    def __init__(
        self,
        embedder: Embedder,
        tool_store: QdrantStore,
        server_store: QdrantStore,
        top_k_servers: int = 5,
    ) -> None:
        self.embedder = embedder
        self.tool_store = tool_store
        self.server_store = server_store
        self.top_k_servers = top_k_servers

    async def search(self, query: str, top_k: int) -> list[SearchResult]:
        """Execute 2-Layer retrieval for a query.

        Args:
            query: Natural language query.
            top_k: Number of final results to return.

        Returns:
            Top-k SearchResults merged from all candidate servers.
        """
        logger.info(f"SequentialStrategy.search: query='{query[:60]}', top_k={top_k}")

        # Embed once — reused for both layers
        query_vector: np.ndarray = await self.embedder.embed_one(query)

        # Layer 1: server-level search
        server_ids = await self.server_store.search_server_ids(
            query_vector, top_k=self.top_k_servers
        )
        logger.debug(f"Layer 1: {len(server_ids)} candidate servers: {server_ids}")

        if not server_ids:
            logger.warning("SequentialStrategy: no servers found in Layer 1")
            return []

        # Layer 2: tool search filtered per server
        all_results: list[SearchResult] = []
        for server_id in server_ids:
            results = await self.tool_store.search(
                query_vector=query_vector,
                top_k=top_k,
                server_id_filter=server_id,
            )
            all_results.extend(results)
        logger.debug(f"Layer 2: {len(all_results)} total tool candidates")

        # Merge: sort by score, re-assign ranks, return top_k
        all_results.sort(key=lambda r: r.score, reverse=True)
        return [
            SearchResult(tool=r.tool, score=r.score, rank=i + 1)
            for i, r in enumerate(all_results[:top_k])
        ]
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
uv run pytest tests/unit/test_sequential_strategy.py -v
```
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/sequential.py tests/unit/test_sequential_strategy.py
git commit -m "feat(pipeline): add SequentialStrategy true 2-Layer (fix OQ-4)"
```

---

## Task 6: Final Integration Check

- [ ] **Step 1: Run full test suite with coverage**

```bash
uv run pytest tests/ --cov=src -v
```
Expected:
- All existing tests PASS
- New pipeline tests PASS
- Coverage ≥ 80%

- [ ] **Step 2: Lint check**

```bash
uv run ruff check src/ tests/
```
Expected: No errors.

- [ ] **Step 3: Update `pipeline/__init__.py`** to re-export all public symbols

```python
"""Pipeline strategies for MCP Discovery Platform."""

from pipeline.confidence import compute_confidence
from pipeline.flat import FlatStrategy
from pipeline.sequential import SequentialStrategy
from pipeline.strategy import PipelineStrategy, StrategyRegistry

__all__ = [
    "PipelineStrategy",
    "StrategyRegistry",
    "compute_confidence",
    "FlatStrategy",
    "SequentialStrategy",
]
```

- [ ] **Step 4: Final commit**

```bash
git add src/pipeline/__init__.py
git commit -m "chore(pipeline): update __init__ exports for Phase 3"
```

---

## What's Next (Phase 3 → Phase 4)

After this plan is complete:
- **Phase 4**: Ground Truth — `data/ground_truth/seed_set.jsonl` (80 entries), `src/data/ground_truth.py`
- **OQ-5/E0**: Implement `src/pipeline/flat.py` ✅ (done here) → run E0 experiment
- **Phase 5**: Evaluation harness — `src/evaluation/harness.py`, metrics
- **Phase 6**: Reranker — `src/reranking/cohere_reranker.py`, inject into strategies

> CTO 멘토링 (3/25) 전까지 이 플랜 완료하면 E0 실험 논의 가능.
