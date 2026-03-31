# Reranker Integration + E0 Re-run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire CohereReranker into all three pipeline strategies and `run_e0.py`, add unit tests for the reranker integration path, then re-run E0 to measure reranker impact on Precision@1.

**Architecture:** The Reranker ABC and CohereReranker are already implemented and tested. FlatStrategy and SequentialStrategy already accept an optional `reranker` parameter but it's never passed in `run_e0.py`. ParallelStrategy lacks reranker support entirely. This plan: (1) adds reranker to ParallelStrategy, (2) tests all three strategy+reranker paths, (3) wires CohereReranker into `run_e0.py` with a CLI flag, (4) re-runs E0.

**Tech Stack:** Python 3.12, pytest + pytest-asyncio, Cohere Rerank 3 (rerank-v3.5), Qdrant, OpenAI text-embedding-3-large

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/pipeline/parallel.py` | Modify | Add optional `reranker` parameter, apply post-RRF |
| `tests/unit/test_flat_strategy.py` | Modify | Add reranker integration tests |
| `tests/unit/test_sequential_strategy.py` | Modify | Add reranker integration tests |
| `tests/unit/test_parallel_strategy.py` | Modify | Add reranker integration tests |
| `scripts/run_e0.py` | Modify | Wire CohereReranker + `--rerank/--no-rerank` flag |
| `.claude/evals/E0-baseline.log` | Overwrite | Updated with reranker results after re-run |

---

### Task 1: Add reranker integration tests for FlatStrategy

**Files:**
- Modify: `tests/unit/test_flat_strategy.py`

- [ ] **Step 1: Write failing test — FlatStrategy calls reranker when provided**

Add to `tests/unit/test_flat_strategy.py`, inside `class TestFlatStrategy`:

```python
async def test_search_calls_reranker_when_provided(self, mock_embedder, mock_tool_store):
    mock_reranker = AsyncMock()
    reranked = [make_search_result(0, score=0.95)]
    mock_reranker.rerank = AsyncMock(return_value=reranked)

    strategy = FlatStrategy(
        embedder=mock_embedder, tool_store=mock_tool_store, reranker=mock_reranker
    )
    results = await strategy.search("test query", top_k=3)

    mock_reranker.rerank.assert_called_once_with("test query", mock_tool_store.search.return_value, 3)
    assert results == reranked

async def test_search_skips_reranker_when_none(self, mock_embedder, mock_tool_store):
    strategy = FlatStrategy(embedder=mock_embedder, tool_store=mock_tool_store, reranker=None)
    results = await strategy.search("test query", top_k=3)
    assert len(results) == 2  # raw store results, no reranker call
```

- [ ] **Step 2: Run tests to verify they pass**

The implementation already exists in `src/pipeline/flat.py` (lines 47-48), so these tests should pass immediately against existing code.

Run: `PYTHONPATH=src uv run pytest tests/unit/test_flat_strategy.py -v`
Expected: ALL PASS (including new tests)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_flat_strategy.py
git commit -m "test: add reranker integration tests for FlatStrategy"
```

---

### Task 2: Add reranker integration tests for SequentialStrategy

**Files:**
- Modify: `tests/unit/test_sequential_strategy.py`

- [ ] **Step 1: Write tests — SequentialStrategy calls reranker after merge**

Add to `tests/unit/test_sequential_strategy.py`, inside `class TestSequentialStrategy`:

```python
async def test_search_calls_reranker_when_provided(
    self, mock_embedder, mock_server_store, mock_tool_store
):
    mock_reranker = AsyncMock()
    reranked = [make_result("srv1", "tool_a", score=0.95)]
    mock_reranker.rerank = AsyncMock(return_value=reranked)

    strategy = SequentialStrategy(
        embedder=mock_embedder,
        tool_store=mock_tool_store,
        server_store=mock_server_store,
        reranker=mock_reranker,
    )
    results = await strategy.search("test query", top_k=3)

    mock_reranker.rerank.assert_called_once()
    call_args = mock_reranker.rerank.call_args
    assert call_args[0][0] == "test query"  # query
    assert call_args[0][2] == 3  # top_k
    assert results == reranked

async def test_search_skips_reranker_when_none(
    self, mock_embedder, mock_server_store, mock_tool_store
):
    strategy = SequentialStrategy(
        embedder=mock_embedder,
        tool_store=mock_tool_store,
        server_store=mock_server_store,
        reranker=None,
    )
    results = await strategy.search("test query", top_k=3)
    assert len(results) == 2  # srv1::tool_a + srv2::tool_b, no reranker
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `PYTHONPATH=src uv run pytest tests/unit/test_sequential_strategy.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_sequential_strategy.py
git commit -m "test: add reranker integration tests for SequentialStrategy"
```

---

### Task 3: Add optional reranker to ParallelStrategy

**Files:**
- Modify: `src/pipeline/parallel.py`
- Modify: `tests/unit/test_parallel_strategy.py`

- [ ] **Step 1: Write failing tests for ParallelStrategy + reranker**

Add to `tests/unit/test_parallel_strategy.py`, inside `class TestParallelStrategy`:

```python
async def test_search_calls_reranker_when_provided(
    self, mock_embedder, mock_server_store, mock_tool_store
):
    mock_reranker = AsyncMock()
    reranked = [make_result("srv1", "tool_a", score=0.99)]
    mock_reranker.rerank = AsyncMock(return_value=reranked)

    strategy = ParallelStrategy(
        embedder=mock_embedder,
        tool_store=mock_tool_store,
        server_store=mock_server_store,
        reranker=mock_reranker,
    )
    results = await strategy.search("test query", top_k=3)

    mock_reranker.rerank.assert_called_once()
    call_args = mock_reranker.rerank.call_args
    assert call_args[0][0] == "test query"
    assert call_args[0][2] == 3
    assert results == reranked

async def test_search_skips_reranker_when_none(
    self, mock_embedder, mock_server_store, mock_tool_store
):
    strategy = ParallelStrategy(
        embedder=mock_embedder,
        tool_store=mock_tool_store,
        server_store=mock_server_store,
        reranker=None,
    )
    results = await strategy.search("test query", top_k=4)
    assert len(results) == 4  # all 4 tools returned via RRF, no reranker
```

- [ ] **Step 2: Run tests to verify they FAIL**

Run: `PYTHONPATH=src uv run pytest tests/unit/test_parallel_strategy.py::TestParallelStrategy::test_search_calls_reranker_when_provided -v`
Expected: FAIL — `ParallelStrategy.__init__()` got unexpected keyword argument `reranker`

- [ ] **Step 3: Add reranker parameter to ParallelStrategy**

In `src/pipeline/parallel.py`, modify the `__init__` and `search` methods:

Replace the `__init__` signature (lines 32-44):
```python
def __init__(
    self,
    embedder: Embedder,
    tool_store: QdrantStore,
    server_store: QdrantStore,
    top_k_servers: int = 5,
    rrf_k: int = 60,
    reranker: Reranker | None = None,
) -> None:
    self.embedder = embedder
    self.tool_store = tool_store
    self.server_store = server_store
    self.top_k_servers = top_k_servers
    self.rrf_k = rrf_k
    self.reranker = reranker
```

Add the import at top of `src/pipeline/parallel.py`:
```python
from reranking.base import Reranker
```

At the end of the `search` method, before the final `return results` (after line 97), insert:
```python
if self.reranker is not None:
    results = await self.reranker.rerank(query, results, top_k)
```

- [ ] **Step 4: Run tests to verify they PASS**

Run: `PYTHONPATH=src uv run pytest tests/unit/test_parallel_strategy.py -v`
Expected: ALL PASS (including both new tests and all existing tests)

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/parallel.py tests/unit/test_parallel_strategy.py
git commit -m "feat(pipeline): add optional reranker to ParallelStrategy (post-RRF)"
```

---

### Task 4: Wire CohereReranker into run_e0.py

**Files:**
- Modify: `scripts/run_e0.py`

- [ ] **Step 1: Add `--rerank` / `--no-rerank` CLI flag**

In `scripts/run_e0.py`, add the argument in the `argparse` block (after line 464):

```python
parser.add_argument(
    "--no-rerank",
    action="store_true",
    help="Disable Cohere reranker (embedding-only baseline)",
)
```

- [ ] **Step 2: Add CohereReranker import and instantiation**

At the top of `scripts/run_e0.py`, add the import (after line 47):
```python
from reranking.cohere_reranker import CohereReranker
```

In `async def main()`, after the `embedder` creation (after line 340), add reranker setup:
```python
# --- Setup reranker (if COHERE_API_KEY available and not disabled) ---
reranker = None
if not args.no_rerank and settings.cohere_api_key:
    reranker = CohereReranker(
        api_key=settings.cohere_api_key,
        model=settings.cohere_rerank_model,
    )
    logger.info(f"Reranker enabled: {settings.cohere_rerank_model}")
elif args.no_rerank:
    logger.info("Reranker disabled via --no-rerank flag")
else:
    logger.warning("COHERE_API_KEY not set — running without reranker")
```

- [ ] **Step 3: Pass reranker to `_run_strategies()`**

Update `_run_strategies` function signature (line 236) to accept reranker:

```python
async def _run_strategies(
    strategy_names: list[str],
    embedder: OpenAIEmbedder,
    tool_store: QdrantStore,
    server_store: QdrantStore,
    entries: list,
    top_k: int,
    reranker: Reranker | None = None,
) -> list[EvalResult]:
```

Add the import for Reranker at top:
```python
from reranking.base import Reranker
```

Update the strategy instantiations inside `_run_strategies` to pass reranker:

```python
if name == "flat":
    strategy = FlatStrategy(embedder=embedder, tool_store=tool_store, reranker=reranker)
elif name == "sequential":
    strategy = SequentialStrategy(
        embedder=embedder,
        tool_store=tool_store,
        server_store=server_store,
        top_k_servers=5,
        reranker=reranker,
    )
elif name == "parallel":
    strategy = ParallelStrategy(
        embedder=embedder,
        tool_store=tool_store,
        server_store=server_store,
        top_k_servers=5,
        reranker=reranker,
    )
```

Update the call site in `main()` (around line 392):
```python
eval_results = await _run_strategies(
    strategy_names, embedder, tool_store, server_store, entries, args.top_k, reranker
)
```

- [ ] **Step 4: Add reranker info to W&B config and output**

In the `wandb.init()` config dict (around line 380), add:
```python
"reranker": settings.cohere_rerank_model if reranker else "none",
```

In `_build_result_payload()`, add reranker to config:
Update the function signature to accept reranker model name:

```python
def _build_result_payload(
    experiment: str,
    pool_size: int,
    top_k: int,
    results: list,
    reranker_model: str | None = None,
) -> dict:
```

Add to the config dict in the return value:
```python
"reranker": reranker_model or "none",
```

Update the call site:
```python
payload = _build_result_payload(
    experiment="E0",
    pool_size=actual_pool_size,
    top_k=args.top_k,
    results=eval_results,
    reranker_model=settings.cohere_rerank_model if reranker else None,
)
```

In the eval log output block (around line 420), add reranker info:
```python
f.write(
    f"\nPool: MCP-Zero ({actual_pool_size} servers)\n"
    f"GT sources: seed_set ({GT_SEED_PATH}), mcp_atlas ({GT_ATLAS_PATH})\n"
    f"Embedding: {E0_EMBEDDING_MODEL} ({E0_EMBEDDING_DIMENSION}-dim)\n"
    f"Reranker: {settings.cohere_rerank_model if reranker else 'none'}\n"
    f"Entries used: {len(entries)} (covered by pool)\n"
)
```

- [ ] **Step 5: Run lint**

Run: `uv run ruff check scripts/run_e0.py`
Expected: PASS (no lint errors)

- [ ] **Step 6: Commit**

```bash
git add scripts/run_e0.py
git commit -m "feat(scripts): wire CohereReranker into run_e0.py with --no-rerank flag"
```

---

### Task 5: Run all unit tests to verify no regressions

**Files:**
- None (verification only)

- [ ] **Step 1: Run full unit test suite**

Run: `PYTHONPATH=src uv run pytest tests/unit/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run lint on all modified files**

Run: `uv run ruff check src/pipeline/parallel.py scripts/run_e0.py tests/unit/test_flat_strategy.py tests/unit/test_sequential_strategy.py tests/unit/test_parallel_strategy.py`
Expected: PASS

---

### Task 6: Re-run E0 with reranker enabled

**Files:**
- Overwrite: `.claude/evals/E0-baseline.log`

> **Prerequisite:** COHERE_API_KEY, OPENAI_API_KEY, and QDRANT_URL must be set in `.env`.

- [ ] **Step 1: Run E0 with reranker (default, all strategies)**

Run:
```bash
PYTHONPATH=src uv run python scripts/run_e0.py --no-wandb
```

Expected: Script completes without error, prints results table for all 3 strategies with reranker applied. Results saved to `.claude/evals/E0-baseline.log`.

- [ ] **Step 2: Run E0 without reranker for comparison**

Run:
```bash
PYTHONPATH=src uv run python scripts/run_e0.py --no-rerank --no-wandb 2>&1 | head -40
```

Expected: Results match prior baseline (Flat P@1=0.309, Sequential P@1=0.253, Parallel P@1=0.263).

- [ ] **Step 3: Record results delta**

Compare reranker-on vs reranker-off P@1 for each strategy. Record the delta. If Flat+reranker P@1 >= 0.50, the North Star is met for Pool 292.

- [ ] **Step 4: Run E0 with W&B logging (final run)**

Run:
```bash
PYTHONPATH=src uv run python scripts/run_e0.py
```

Expected: Results logged to W&B project `mcp-discovery` with reranker config metadata.

- [ ] **Step 5: Commit updated eval log**

```bash
git add .claude/evals/E0-baseline.log
git commit -m "docs(eval): E0 rerun with CohereReranker rerank-v3.5 results"
```

---

### Task 7: Update E0 eval spec with reranker observations

**Files:**
- Modify: `.claude/evals/E0-baseline.md`

- [ ] **Step 1: Add reranker configuration note to E0 spec**

In `.claude/evals/E0-baseline.md`, update the CLI section to include reranker flag:

```markdown
## CLI

```bash
uv run python scripts/run_e0.py                           # All strategies + reranker (default)
uv run python scripts/run_e0.py --no-rerank               # Embedding-only baseline
uv run python scripts/run_e0.py --strategy flat            # Single strategy
```
```

Add a "Reranker Configuration" section after "Judgment Gate":

```markdown
## Reranker Configuration

- Default: CohereReranker (rerank-v3.5) applied post-retrieval to all strategies
- `--no-rerank`: Disables reranker for embedding-only comparison
- Requires `COHERE_API_KEY` in `.env`; if missing, runs without reranker automatically
```

- [ ] **Step 2: Commit**

```bash
git add .claude/evals/E0-baseline.md
git commit -m "docs(eval): update E0 spec with reranker configuration"
```
