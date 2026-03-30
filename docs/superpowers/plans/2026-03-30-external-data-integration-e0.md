# External Data Integration + E0 Rerun Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate MCP-Zero (308 servers, 2,797 tools) as the tool pool and MCP-Atlas (500 tasks → per-step GT decomposition) as ground truth, then re-run E0 experiment on the new data.

**Architecture:** Two import scripts transform external datasets into our Pydantic models. `import_mcp_zero.py` converts MCP-Zero JSON → MCPServer/MCPTool + Qdrant indexing. `convert_mcp_atlas.py` decomposes MCP-Atlas multi-step tasks into per-step single-tool GroundTruthEntry JSONL (ADR-0012). After both are complete, `run_e0.py` is updated to use the new pool + GT.

**Tech Stack:** Python 3.12, pyarrow, pydantic v2, qdrant-client (async), openai (async), loguru, pytest, pytest-asyncio

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/import_mcp_zero.py` | Rewrite | Convert MCP-Zero JSON → MCPServer/MCPTool JSONL + optional Qdrant upsert |
| `scripts/convert_mcp_atlas.py` | Rewrite | ADR-0012 per-step decomposition: trajectory parsing → LLM query gen → GT JSONL |
| `scripts/run_e0.py` | Modify | Point to new MCP-Zero pool + MCP-Atlas GT |
| `data/external/README.md` | Create | Download instructions for MCP-Zero + MCP-Atlas |
| `tests/unit/test_import_mcp_zero.py` | Create | Unit tests for MCP-Zero import conversion logic |
| `tests/unit/test_convert_mcp_atlas.py` | Create | Unit tests for MCP-Atlas per-step decomposition logic |
| `.gitignore` | Modify | Ensure `data/external/*/` contents ignored |

---

## External Dataset Verification (2026-03-30)

> 상세: `docs/research/external-benchmarks-20260328.md` (검증 결과 통합 완료)
> 검증 방식: 문서 조사 + HuggingFace API 직접 호출 + GitHub 리포 확인

MCP-Atlas 외 9개 GT 후보 데이터셋을 심층 검증한 결과, **MCP-Atlas per-step 분해 + self seed 80개 전략 유지가 최선**으로 확인됨. 이 Plan의 Task 1-8은 그대로 유효.

**보조 활용 (다음 스프린트):**
- MCPToolBench++ single-step subset → E0/E1 regression test
- MCPVerse tool registry (552 tools) → E5 Pool 확장
- ToolRet gorilla/toolalpaca → method validation / 논문 인용

---

## Task 1: Download MCP-Zero Data + Create `data/external/README.md`

**Files:**
- Create: `data/external/README.md`
- Create: `data/external/mcp-zero/` directory

MCP-Zero upstream file is a single JSON: `mcp_tools_with_embedding.json` (~200MB with embeddings). Download from Google Drive link in MCP-Zero GitHub README.

- [ ] **Step 1: Create `data/external/README.md`**

```markdown
# External Datasets

These datasets are Git-ignored. Download manually before running import scripts.

## MCP-Zero (Tool Pool)

- **Source**: https://github.com/xfey/MCP-Zero
- **License**: MIT
- **Size**: 308 servers, 2,797 tools
- **File**: `mcp-zero/servers.json` (renamed from `mcp_tools_with_embedding.json`)

### Download

1. Go to MCP-Zero GitHub README → Google Drive link
2. Download `mcp_tools_with_embedding.json`
3. Save as `data/external/mcp-zero/servers.json`

## MCP-Atlas (Ground Truth)

- **Source**: https://huggingface.co/datasets/ScaleAI/MCP-Atlas
- **License**: CC-BY-4.0
- **Size**: 500 human-authored tasks, 36 servers, 307 tools
- **File**: `mcp-atlas/MCP-Atlas.parquet`

### Download

Already present: `data/external/mcp-atlas/MCP-Atlas.parquet`

Or re-download:
```bash
pip install huggingface_hub
huggingface-cli download ScaleAI/MCP-Atlas --local-dir data/external/mcp-atlas/
```
```

- [ ] **Step 2: Create MCP-Zero directory**

```bash
mkdir -p data/external/mcp-zero
```

- [ ] **Step 3: Download MCP-Zero JSON**

Download `mcp_tools_with_embedding.json` from Google Drive and save as:
```
data/external/mcp-zero/servers.json
```

⚠️ This is a manual step — the file is ~200MB and hosted on Google Drive.

- [ ] **Step 4: Verify file exists**

```bash
ls -la data/external/mcp-zero/servers.json
python -c "import json; d=json.load(open('data/external/mcp-zero/servers.json')); print(f'Entries: {len(d) if isinstance(d,list) else len(d.get(\"servers\",d.get(\"tools\",[])))}'); print(f'Keys: {list(d[0].keys()) if isinstance(d,list) else list(d.keys())}')"
```

Expected: ~308 entries with keys like `server_name`, `server_summary`, `server_description`, `tools`, etc.

- [ ] **Step 5: Verify `.gitignore` covers external data**

Check that `data/external/` contents (except README.md) are git-ignored:

```bash
grep "data/external" .gitignore
```

If missing, add:
```
data/external/mcp-zero/
data/external/mcp-atlas/
!data/external/README.md
```

- [ ] **Step 6: Commit**

```bash
git add data/external/README.md .gitignore
git commit -m "docs: add external data download instructions"
```

---

## Task 2: Rewrite `scripts/import_mcp_zero.py`

The current script guesses at the MCP-Zero JSON schema. Now we know the actual schema from the handoff doc:

**MCP-Zero server entry fields:**
- `server_name`: string
- `server_summary`: string
- `server_description`: string
- `description_embedding`: float[3072] (text-embedding-3-large)
- `summary_embedding`: float[3072]
- `tools`: array of `{name, description, description_embedding, parameter}`

**Our conversion rules:**
- `server_id` = `server_name` (lowercased, spaces→underscores)
- `tool_id` = `"{server_id}::{tool.name}"`
- `input_schema` derived from `parameter` field: `{"param_name": "(type) description"}` → standard JSON Schema

**Files:**
- Modify: `scripts/import_mcp_zero.py`
- Test: `tests/unit/test_import_mcp_zero.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_import_mcp_zero.py`:

```python
"""Tests for scripts/import_mcp_zero.py — MCP-Zero JSON → MCPServer/MCPTool conversion."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

# We test the pure conversion functions, not the CLI
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from import_mcp_zero import convert_server, load_mcp_zero_json, parse_parameter_schema


# --- Fixtures ---

@pytest.fixture
def sample_server_raw() -> dict:
    """Realistic MCP-Zero server entry."""
    return {
        "server_name": "GitHub",
        "server_summary": "Access GitHub repositories and issues",
        "server_description": "A comprehensive GitHub integration server",
        "description_embedding": [0.1] * 3072,
        "summary_embedding": [0.2] * 3072,
        "tools": [
            {
                "name": "search_repositories",
                "description": "Search for GitHub repositories by query",
                "description_embedding": [0.3] * 3072,
                "parameter": {
                    "query": "(string) Search query text",
                    "sort": "(string) Sort field: stars, forks, updated",
                },
            },
            {
                "name": "get_issue",
                "description": "Get details of a GitHub issue",
                "description_embedding": [0.4] * 3072,
                "parameter": {
                    "owner": "(string) Repository owner",
                    "repo": "(string) Repository name",
                    "issue_number": "(integer) Issue number",
                },
            },
        ],
    }


@pytest.fixture
def sample_server_no_tools() -> dict:
    return {
        "server_name": "EmptyServer",
        "server_summary": "Has no tools",
        "server_description": "Empty",
        "tools": [],
    }


# --- convert_server ---

class TestConvertServer:
    def test_basic_conversion(self, sample_server_raw: dict) -> None:
        server = convert_server(sample_server_raw)
        assert server is not None
        assert server.server_id == "github"
        assert server.name == "GitHub"
        assert server.description == "A comprehensive GitHub integration server"
        assert len(server.tools) == 2

    def test_tool_ids_use_separator(self, sample_server_raw: dict) -> None:
        server = convert_server(sample_server_raw)
        assert server is not None
        assert server.tools[0].tool_id == "github::search_repositories"
        assert server.tools[1].tool_id == "github::get_issue"

    def test_tool_description_preserved(self, sample_server_raw: dict) -> None:
        server = convert_server(sample_server_raw)
        assert server is not None
        assert server.tools[0].description == "Search for GitHub repositories by query"

    def test_server_id_normalization(self) -> None:
        raw = {
            "server_name": "My Cool Server",
            "server_summary": "cool",
            "server_description": "Cool stuff",
            "tools": [{"name": "do_thing", "description": "Does thing"}],
        }
        server = convert_server(raw)
        assert server is not None
        assert server.server_id == "my_cool_server"

    def test_no_tools_returns_none(self, sample_server_no_tools: dict) -> None:
        server = convert_server(sample_server_no_tools)
        assert server is None

    def test_missing_server_name_returns_none(self) -> None:
        raw = {"tools": [{"name": "t", "description": "d"}]}
        server = convert_server(raw)
        assert server is None

    def test_embeddings_not_stored_in_model(self, sample_server_raw: dict) -> None:
        """Embeddings from MCP-Zero are NOT stored in our MCPTool model."""
        server = convert_server(sample_server_raw)
        assert server is not None
        # MCPTool doesn't have an embedding field
        assert not hasattr(server.tools[0], "embedding")


# --- parse_parameter_schema ---

class TestParseParameterSchema:
    def test_converts_mcp_zero_format(self) -> None:
        params = {
            "query": "(string) Search query text",
            "limit": "(integer) Max results",
        }
        schema = parse_parameter_schema(params)
        assert schema == {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "limit": {"type": "integer", "description": "Max results"},
            },
        }

    def test_empty_params(self) -> None:
        assert parse_parameter_schema({}) is None
        assert parse_parameter_schema(None) is None

    def test_unknown_type_defaults_to_string(self) -> None:
        params = {"data": "(bytes) Binary data"}
        schema = parse_parameter_schema(params)
        assert schema["properties"]["data"]["type"] == "string"

    def test_no_type_annotation(self) -> None:
        """If parameter value doesn't follow '(type) desc' format."""
        params = {"query": "Search query text"}
        schema = parse_parameter_schema(params)
        assert schema["properties"]["query"]["type"] == "string"
        assert schema["properties"]["query"]["description"] == "Search query text"


# --- load_mcp_zero_json ---

class TestLoadMcpZeroJson:
    def test_loads_list_format(self, tmp_path: Path) -> None:
        data = [{"server_name": "test", "tools": []}]
        f = tmp_path / "servers.json"
        f.write_text(json.dumps(data))
        result = load_mcp_zero_json(f)
        assert len(result) == 1

    def test_loads_dict_with_servers_key(self, tmp_path: Path) -> None:
        data = {"servers": [{"server_name": "test", "tools": []}]}
        f = tmp_path / "servers.json"
        f.write_text(json.dumps(data))
        result = load_mcp_zero_json(f)
        assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_import_mcp_zero.py -v
```

Expected: FAIL (missing `parse_parameter_schema` function, schema mismatches)

- [ ] **Step 3: Rewrite `scripts/import_mcp_zero.py`**

```python
"""Import MCP-Zero dataset → MCPServer/MCPTool models + optional Qdrant indexing.

Reads MCP-Zero JSON (308 servers, 2,797 tools), converts to our MCPServer/MCPTool
Pydantic models, and optionally indexes them into Qdrant with pre-computed
text-embedding-3-large vectors.

Usage:
    uv run python scripts/import_mcp_zero.py
    uv run python scripts/import_mcp_zero.py --input data/external/mcp-zero/servers.json
    uv run python scripts/import_mcp_zero.py --index  # Also upsert to Qdrant
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import uuid
from pathlib import Path

import numpy as np
from loguru import logger

from src.models import TOOL_ID_SEPARATOR, MCPServer, MCPTool
from src.retrieval.qdrant_store import MCP_DISCOVERY_NAMESPACE

# Default paths
DEFAULT_INPUT = "data/external/mcp-zero/servers.json"
DEFAULT_OUTPUT = "data/raw/mcp_zero_servers.jsonl"

# MCP-Zero parameter type pattern: "(type) description"
_PARAM_TYPE_RE = re.compile(r"^\((\w+)\)\s*(.*)$")

# Allowed JSON Schema types
_VALID_TYPES = {"string", "integer", "number", "boolean", "array", "object"}


def parse_parameter_schema(params: dict | None) -> dict | None:
    """Convert MCP-Zero parameter format to JSON Schema.

    MCP-Zero format: {"param_name": "(type) description"}
    Output: {"type": "object", "properties": {"param_name": {"type": "...", "description": "..."}}}
    """
    if not params:
        return None

    properties = {}
    for name, value in params.items():
        match = _PARAM_TYPE_RE.match(str(value))
        if match:
            param_type = match.group(1).lower()
            description = match.group(2).strip()
            if param_type not in _VALID_TYPES:
                param_type = "string"
        else:
            param_type = "string"
            description = str(value).strip()
        properties[name] = {"type": param_type, "description": description}

    return {"type": "object", "properties": properties}


def convert_server(raw: dict) -> MCPServer | None:
    """Convert a single MCP-Zero server entry to our MCPServer model.

    MCP-Zero fields: server_name, server_summary, server_description,
    description_embedding, summary_embedding, tools[{name, description,
    description_embedding, parameter}]
    """
    server_name = raw.get("server_name") or ""
    if not server_name:
        logger.warning(f"Server entry missing server_name: {raw}")
        return None

    server_id = server_name.strip().lower().replace(" ", "_")

    tools_raw = raw.get("tools") or []
    tools: list[MCPTool] = []

    for t in tools_raw:
        tool_name = t.get("name") or ""
        if not tool_name:
            continue

        tool_id = f"{server_id}{TOOL_ID_SEPARATOR}{tool_name}"
        input_schema = parse_parameter_schema(t.get("parameter"))

        tools.append(
            MCPTool(
                tool_id=tool_id,
                server_id=server_id,
                tool_name=tool_name,
                description=t.get("description", ""),
                input_schema=input_schema,
            )
        )

    if not tools:
        logger.warning(f"Server '{server_name}' has no tools, skipping")
        return None

    return MCPServer(
        server_id=server_id,
        name=server_name,
        description=raw.get("server_description") or raw.get("server_summary") or "",
        tools=tools,
    )


def load_mcp_zero_json(input_path: Path) -> list[dict]:
    """Load MCP-Zero servers from JSON file."""
    with input_path.open() as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "servers" in data:
        return data["servers"]

    logger.error(f"Unexpected JSON structure in {input_path}")
    return []


def extract_tool_embeddings(raw_servers: list[dict]) -> dict[str, np.ndarray]:
    """Extract pre-computed embeddings keyed by tool_id.

    Returns dict mapping tool_id → numpy embedding vector.
    """
    embeddings: dict[str, np.ndarray] = {}
    for raw in raw_servers:
        server_name = raw.get("server_name") or ""
        if not server_name:
            continue
        server_id = server_name.strip().lower().replace(" ", "_")
        for t in raw.get("tools") or []:
            tool_name = t.get("name") or ""
            emb = t.get("description_embedding")
            if tool_name and emb:
                tool_id = f"{server_id}{TOOL_ID_SEPARATOR}{tool_name}"
                embeddings[tool_id] = np.array(emb, dtype=np.float32)
    return embeddings


async def index_to_qdrant(
    servers: list[MCPServer],
    embeddings: dict[str, np.ndarray],
    qdrant_url: str,
    qdrant_api_key: str | None,
    collection_name: str = "mcp_tools",
) -> None:
    """Upsert tools to Qdrant using pre-computed MCP-Zero embeddings."""
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    client = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    # Determine dimension from first embedding
    first_emb = next(iter(embeddings.values()), None)
    if first_emb is None:
        logger.error("No embeddings found, cannot create collection")
        return
    dim = len(first_emb)

    # Ensure collection
    collections = await client.get_collections()
    existing = [c.name for c in collections.collections]
    if collection_name not in existing:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        logger.info(f"Created collection '{collection_name}' (dim={dim})")

    # Build points
    points: list[PointStruct] = []
    missing = 0
    for server in servers:
        for tool in server.tools:
            emb = embeddings.get(tool.tool_id)
            if emb is None:
                missing += 1
                continue
            points.append(
                PointStruct(
                    id=str(uuid.uuid5(MCP_DISCOVERY_NAMESPACE, tool.tool_id)),
                    vector=emb.tolist(),
                    payload={
                        "tool_id": tool.tool_id,
                        "server_id": tool.server_id,
                        "tool_name": tool.tool_name,
                        "description": tool.description or "",
                    },
                )
            )

    if missing:
        logger.warning(f"{missing} tools had no pre-computed embedding")

    # Batch upsert
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        await client.upsert(collection_name=collection_name, points=batch)
        logger.info(f"Upserted batch {i // batch_size + 1}: {len(batch)} points")

    logger.info(f"Qdrant indexing complete: {len(points)} tools in '{collection_name}'")
    await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import MCP-Zero → MCPServer/MCPTool")
    parser.add_argument(
        "--input", type=Path, default=Path(DEFAULT_INPUT),
        help=f"MCP-Zero servers JSON path (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output", type=Path, default=Path(DEFAULT_OUTPUT),
        help=f"Output JSONL path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--index", action="store_true",
        help="Also upsert to Qdrant using pre-computed embeddings",
    )
    parser.add_argument(
        "--qdrant-url", type=str, default=None,
        help="Qdrant URL (default: from .env QDRANT_URL)",
    )
    parser.add_argument(
        "--collection", type=str, default="mcp_tools",
        help="Qdrant collection name (default: mcp_tools)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        logger.info("Download MCP-Zero first. See data/external/README.md")
        return

    raw_servers = load_mcp_zero_json(args.input)
    logger.info(f"Loaded {len(raw_servers)} raw servers from {args.input}")

    servers: list[MCPServer] = []
    total_tools = 0
    for raw in raw_servers:
        server = convert_server(raw)
        if server is not None:
            servers.append(server)
            total_tools += len(server.tools)

    logger.info(f"Converted {len(servers)} servers, {total_tools} tools")

    # Save as JSONL
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        for server in servers:
            f.write(server.model_dump_json() + "\n")
    logger.info(f"Output: {args.output}")

    if args.index:
        from dotenv import load_dotenv
        load_dotenv()
        from src.config import Settings
        settings = Settings()

        qdrant_url = args.qdrant_url or settings.qdrant_url
        embeddings = extract_tool_embeddings(raw_servers)
        logger.info(f"Extracted {len(embeddings)} pre-computed embeddings")

        asyncio.run(index_to_qdrant(
            servers, embeddings, qdrant_url,
            settings.qdrant_api_key, args.collection,
        ))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_import_mcp_zero.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/import_mcp_zero.py tests/unit/test_import_mcp_zero.py
git commit -m "feat(scripts): rewrite import_mcp_zero for verified MCP-Zero schema"
```

---

## Task 3: Rewrite `scripts/convert_mcp_atlas.py` (ADR-0012 Per-Step Decomposition)

The current script only extracts the first tool call and doesn't implement ADR-0012.

**What needs to change:**
1. Parse TRAJECTORY JSON to extract ALL tool calls (not just first)
2. Filter out boilerplate calls (blocklist)
3. Generate per-step queries using LLM (OpenAI)
4. Output GroundTruthEntry-compatible JSONL with `origin_task_id`, `step_index` lineage
5. Support `--dry-run` mode for inspection without LLM calls

**MCP-Atlas TRAJECTORY format** (confirmed from parquet):
```json
[
  {"role": "assistant", "tool_calls": [{"function": {"name": "github_search_repositories", "arguments": "..."}, "id": "...", "type": "function"}]},
  {"role": "tool", "content": "...", "name": null},
  ...
]
```

**Tool naming convention in MCP-Atlas:** `{server}_{tool}` where first `_` separates server from tool. But hyphens in server names (e.g., `brave-search_brave_web_search`). So split on first `_` only for simple names, but need a lookup table for hyphenated servers.

**Known servers (from MCP-Atlas data):**
`airtable`, `alchemy`, `arxiv`, `brave-search`, `calculator`, `cli-mcp-server`, `clinicaltrialsgov-mcp-server`, `context7`, `ddg-search`, `desktop-commander`, `e2b-server`, `exa`, `fetch`, `filesystem`, `git`, `github`, `google-maps`, `google-workspace`, `lara-translate`, `mcp-code-executor`, `mcp-server-code-runner`, `memory`, `met-museum`, `mongodb`, `national-parks`, `notion`, `open-library`, `osm-mcp-server`, `oxylabs`, `pubmed`, `slack`, `twelvedata`, `weather`, `weather-data`, `whois`, `wikipedia`

**Files:**
- Modify: `scripts/convert_mcp_atlas.py`
- Test: `tests/unit/test_convert_mcp_atlas.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_convert_mcp_atlas.py`:

```python
"""Tests for scripts/convert_mcp_atlas.py — MCP-Atlas per-step GT decomposition."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from convert_mcp_atlas import (
    parse_trajectory,
    split_tool_name,
    is_boilerplate,
    extract_substantive_steps,
    build_ground_truth_entry,
    BOILERPLATE_BLOCKLIST,
)


# --- Fixtures ---

@pytest.fixture
def sample_trajectory() -> list[dict]:
    """Realistic MCP-Atlas trajectory."""
    return [
        {
            "role": "assistant",
            "content": "I'll search for the repository.",
            "tool_calls": [
                {
                    "function": {
                        "name": "github_search_repositories",
                        "arguments": '{"query": "assaultcube"}',
                    },
                    "id": "call_001",
                    "type": "function",
                }
            ],
        },
        {"role": "tool", "content": "Found 10 repos...", "name": None},
        {
            "role": "assistant",
            "content": "Let me get details.",
            "tool_calls": [
                {
                    "function": {
                        "name": "github_get_repository",
                        "arguments": '{"owner": "assaultcube", "repo": "AC"}',
                    },
                    "id": "call_002",
                    "type": "function",
                }
            ],
        },
        {"role": "tool", "content": "Repo details...", "name": None},
        {
            "role": "assistant",
            "content": "Let me fetch the website.",
            "tool_calls": [
                {
                    "function": {
                        "name": "fetch_fetch",
                        "arguments": '{"url": "https://assault.cubers.net"}',
                    },
                    "id": "call_003",
                    "type": "function",
                }
            ],
        },
        {"role": "tool", "content": "Page content...", "name": None},
    ]


@pytest.fixture
def trajectory_with_boilerplate() -> list[dict]:
    """Trajectory starting with boilerplate calls."""
    return [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "filesystem_list_allowed_directories",
                        "arguments": "{}",
                    },
                    "id": "call_000",
                    "type": "function",
                }
            ],
        },
        {"role": "tool", "content": "...", "name": None},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "desktop-commander_get_config",
                        "arguments": "{}",
                    },
                    "id": "call_001",
                    "type": "function",
                }
            ],
        },
        {"role": "tool", "content": "...", "name": None},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "github_search_repositories",
                        "arguments": '{"query": "test"}',
                    },
                    "id": "call_002",
                    "type": "function",
                }
            ],
        },
        {"role": "tool", "content": "...", "name": None},
    ]


# --- split_tool_name ---

class TestSplitToolName:
    def test_simple_server(self) -> None:
        server_id, tool_name = split_tool_name("github_search_repositories")
        assert server_id == "github"
        assert tool_name == "search_repositories"

    def test_hyphenated_server(self) -> None:
        server_id, tool_name = split_tool_name("brave-search_brave_web_search")
        assert server_id == "brave-search"
        assert tool_name == "brave_web_search"

    def test_multi_hyphen_server(self) -> None:
        server_id, tool_name = split_tool_name("cli-mcp-server_run_command")
        assert server_id == "cli-mcp-server"
        assert tool_name == "run_command"

    def test_single_word_tool(self) -> None:
        server_id, tool_name = split_tool_name("fetch_fetch")
        assert server_id == "fetch"
        assert tool_name == "fetch"

    def test_unknown_format_best_effort(self) -> None:
        server_id, tool_name = split_tool_name("sometool")
        assert server_id == "sometool"
        assert tool_name == ""


# --- is_boilerplate ---

class TestIsBoilerplate:
    def test_known_boilerplate(self) -> None:
        assert is_boilerplate("filesystem_list_allowed_directories") is True
        assert is_boilerplate("cli-mcp-server_show_security_rules") is True
        assert is_boilerplate("desktop-commander_get_config") is True

    def test_substantive_tool(self) -> None:
        assert is_boilerplate("github_search_repositories") is False

    def test_blocklist_has_known_items(self) -> None:
        assert "filesystem_list_allowed_directories" in BOILERPLATE_BLOCKLIST
        assert "cli-mcp-server_show_security_rules" in BOILERPLATE_BLOCKLIST
        assert "desktop-commander_get_config" in BOILERPLATE_BLOCKLIST


# --- parse_trajectory ---

class TestParseTrajectory:
    def test_extracts_tool_calls(self, sample_trajectory: list[dict]) -> None:
        calls = parse_trajectory(sample_trajectory)
        assert len(calls) == 3
        assert calls[0]["name"] == "github_search_repositories"
        assert calls[1]["name"] == "github_get_repository"
        assert calls[2]["name"] == "fetch_fetch"

    def test_preserves_arguments(self, sample_trajectory: list[dict]) -> None:
        calls = parse_trajectory(sample_trajectory)
        assert '"assaultcube"' in calls[0]["arguments"]

    def test_empty_trajectory(self) -> None:
        assert parse_trajectory([]) == []


# --- extract_substantive_steps ---

class TestExtractSubstantiveSteps:
    def test_filters_boilerplate(self, trajectory_with_boilerplate: list[dict]) -> None:
        calls = parse_trajectory(trajectory_with_boilerplate)
        steps = extract_substantive_steps(calls)
        assert len(steps) == 1
        assert steps[0]["name"] == "github_search_repositories"

    def test_all_substantive(self, sample_trajectory: list[dict]) -> None:
        calls = parse_trajectory(sample_trajectory)
        steps = extract_substantive_steps(calls)
        assert len(steps) == 3


# --- build_ground_truth_entry ---

class TestBuildGroundTruthEntry:
    def test_basic_entry(self) -> None:
        entry = build_ground_truth_entry(
            task_id="689f4d693e212e8ef3390731",
            task_index=42,
            step_index=0,
            tool_call_name="github_search_repositories",
            query="Search for open source game repositories on GitHub",
            prompt="I've been looking into open source games...",
        )
        assert entry["query_id"] == "gt-atlas-042-s00"
        assert entry["correct_server_id"] == "github"
        assert entry["correct_tool_id"] == "github::search_repositories"
        assert entry["source"] == "external_mcp_atlas"
        assert entry["manually_verified"] is True
        assert entry["task_type"] == "single_step"
        assert entry["origin_task_id"] == "689f4d693e212e8ef3390731"
        assert entry["step_index"] == 0

    def test_query_id_format(self) -> None:
        entry = build_ground_truth_entry(
            task_id="abc123",
            task_index=5,
            step_index=3,
            tool_call_name="fetch_fetch",
            query="Fetch webpage",
            prompt="...",
        )
        assert entry["query_id"] == "gt-atlas-005-s03"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_convert_mcp_atlas.py -v
```

Expected: FAIL

- [ ] **Step 3: Rewrite `scripts/convert_mcp_atlas.py`**

```python
"""Convert MCP-Atlas parquet → per-step single-tool GroundTruthEntry JSONL (ADR-0012).

Reads MCP-Atlas dataset (500 human-authored tasks from Scale AI),
decomposes multi-step trajectories into per-step single-tool GT entries.

Usage:
    uv run python scripts/convert_mcp_atlas.py --dry-run       # Inspect without LLM
    uv run python scripts/convert_mcp_atlas.py                  # Full conversion with LLM query gen
    uv run python scripts/convert_mcp_atlas.py --max-tasks 10   # Limit tasks for testing
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

from loguru import logger

from src.models import TOOL_ID_SEPARATOR

# Default paths
DEFAULT_INPUT_DIR = "data/external/mcp-atlas"
DEFAULT_OUTPUT_PATH = "data/ground_truth/mcp_atlas.jsonl"

# --- Boilerplate blocklist (ADR-0012) ---
BOILERPLATE_BLOCKLIST = frozenset({
    "filesystem_list_allowed_directories",
    "cli-mcp-server_show_security_rules",
    "desktop-commander_get_config",
    "memory_list_memories",
})

# Known MCP-Atlas servers with hyphens in their names.
# Needed to correctly split "server_tool" format.
_HYPHENATED_SERVERS = frozenset({
    "brave-search",
    "cli-mcp-server",
    "clinicaltrialsgov-mcp-server",
    "ddg-search",
    "desktop-commander",
    "e2b-server",
    "google-maps",
    "google-workspace",
    "lara-translate",
    "mcp-code-executor",
    "mcp-server-code-runner",
    "met-museum",
    "national-parks",
    "open-library",
    "osm-mcp-server",
    "weather-data",
})


def split_tool_name(full_name: str) -> tuple[str, str]:
    """Split MCP-Atlas tool name into (server_id, tool_name).

    MCP-Atlas convention: "{server}_{tool}" where server may contain hyphens.
    E.g., "github_search_repositories" → ("github", "search_repositories")
          "brave-search_brave_web_search" → ("brave-search", "brave_web_search")
    """
    # Try hyphenated servers first (longest match)
    for server in sorted(_HYPHENATED_SERVERS, key=len, reverse=True):
        prefix = server + "_"
        if full_name.startswith(prefix):
            return server, full_name[len(prefix):]

    # Simple case: first underscore splits server from tool
    parts = full_name.split("_", 1)
    if len(parts) == 2:
        return parts[0], parts[1]

    return full_name, ""


def is_boilerplate(tool_call_name: str) -> bool:
    """Check if a tool call is boilerplate (initialization, config, etc.)."""
    return tool_call_name in BOILERPLATE_BLOCKLIST


def parse_trajectory(trajectory: list[dict]) -> list[dict]:
    """Extract tool call entries from MCP-Atlas TRAJECTORY JSON.

    Returns list of dicts with: name, arguments, call_index.
    """
    calls: list[dict] = []
    idx = 0
    for entry in trajectory:
        if entry.get("role") == "assistant" and "tool_calls" in entry:
            for tc in entry["tool_calls"]:
                func = tc.get("function", {})
                calls.append({
                    "name": func.get("name", ""),
                    "arguments": func.get("arguments", ""),
                    "call_index": idx,
                })
                idx += 1
    return calls


def extract_substantive_steps(tool_calls: list[dict]) -> list[dict]:
    """Filter out boilerplate tool calls, keeping substantive steps."""
    return [tc for tc in tool_calls if not is_boilerplate(tc["name"])]


def build_ground_truth_entry(
    task_id: str,
    task_index: int,
    step_index: int,
    tool_call_name: str,
    query: str,
    prompt: str,
) -> dict:
    """Build a GroundTruthEntry-compatible dict for a single step.

    Args:
        task_id: MCP-Atlas TASK field (24-char hex ID).
        task_index: 1-based index among selected tasks.
        step_index: 0-based position within decomposed steps.
        tool_call_name: MCP-Atlas tool name (e.g., "github_search_repositories").
        query: Generated step-level natural language query.
        prompt: Original MCP-Atlas PROMPT for reference.
    """
    server_id, tool_name = split_tool_name(tool_call_name)
    tool_id = f"{server_id}{TOOL_ID_SEPARATOR}{tool_name}"

    return {
        "query_id": f"gt-atlas-{task_index:03d}-s{step_index:02d}",
        "query": query,
        "correct_server_id": server_id,
        "correct_tool_id": tool_id,
        "difficulty": "medium",
        "category": "general",
        "ambiguity": "low",
        "source": "external_mcp_atlas",
        "manually_verified": True,
        "author": "scale_ai",
        "created_at": "2026-03-30",
        "task_type": "single_step",
        "origin_task_id": task_id,
        "step_index": step_index,
        "notes": f"Decomposed from MCP-Atlas task. Original prompt: {prompt[:100]}...",
    }


async def generate_step_query(
    tool_call_name: str,
    tool_description: str,
    task_prompt: str,
    step_position: int,
    total_steps: int,
) -> str:
    """Generate a natural language query for a single step using LLM.

    ADR-0012 prompt template.
    """
    from openai import AsyncOpenAI

    server_id, tool_name = split_tool_name(tool_call_name)

    prompt = f"""Given this MCP tool and the context of what the user is trying to accomplish:

Tool: {server_id}::{tool_name}
Task context: {task_prompt}
Step position: {step_position + 1}th step of {total_steps} steps

Generate a natural language query that a user would give to an LLM,
which would lead the LLM to call this specific tool.

Rules:
- The query must be self-contained (no reference to previous steps)
- Do NOT include the tool name or server name in the query
- Write as if a human is asking for help, not describing an API call
- Keep it concise (1-2 sentences)

Output ONLY the query, nothing else."""

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()


def load_parquet_tasks(input_dir: Path) -> list[dict]:
    """Load tasks from MCP-Atlas parquet files."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        logger.error("pyarrow not installed. Run: uv add pyarrow")
        raise

    parquet_files = sorted(input_dir.glob("*.parquet"))
    if not parquet_files:
        logger.error(f"No parquet files found in {input_dir}")
        return []

    import pyarrow as pa
    table = pq.read_table(parquet_files[0])
    for pf in parquet_files[1:]:
        table = pa.concat_tables([table, pq.read_table(pf)])

    columns = table.to_pydict()
    n_rows = len(next(iter(columns.values())))
    tasks = [{col: columns[col][i] for col in columns} for i in range(n_rows)]
    logger.info(f"Loaded {len(tasks)} tasks from {len(parquet_files)} parquet files")
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert MCP-Atlas → per-step GT JSONL")
    parser.add_argument(
        "--input", type=Path, default=Path(DEFAULT_INPUT_DIR),
        help=f"MCP-Atlas parquet directory (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output", type=Path, default=Path(DEFAULT_OUTPUT_PATH),
        help=f"Output JSONL path (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--max-tasks", type=int, default=80,
        help="Maximum number of tasks to decompose (default: 80, ADR-0012: 50-80)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Extract steps without LLM query generation (for inspection)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input directory not found: {args.input}")
        logger.info("Download MCP-Atlas first. See data/external/README.md")
        return

    tasks = load_parquet_tasks(args.input)
    if not tasks:
        return

    # Parse trajectories and count substantive steps per task
    task_steps: list[tuple[dict, list[dict]]] = []
    for task in tasks:
        trajectory = json.loads(task.get("TRAJECTORY", "[]"))
        all_calls = parse_trajectory(trajectory)
        steps = extract_substantive_steps(all_calls)
        if len(steps) >= 2:  # ADR-0012: prioritize tasks with 2+ substantive tools
            task_steps.append((task, steps))

    logger.info(
        f"Tasks with 2+ substantive steps: {len(task_steps)} / {len(tasks)}"
    )

    # Select up to max_tasks
    selected = task_steps[: args.max_tasks]
    logger.info(f"Selected {len(selected)} tasks for decomposition")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    total_entries = 0

    if args.dry_run:
        # Dry run: output step info without LLM queries
        with args.output.open("w") as f:
            for task_idx, (task, steps) in enumerate(selected, start=1):
                for step_idx, step in enumerate(steps):
                    entry = build_ground_truth_entry(
                        task_id=task.get("TASK", "unknown"),
                        task_index=task_idx,
                        step_index=step_idx,
                        tool_call_name=step["name"],
                        query=f"[DRY RUN] Step for {step['name']}",
                        prompt=task.get("PROMPT", ""),
                    )
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    total_entries += 1
    else:
        # Full mode: generate queries with LLM
        async def run_conversion() -> int:
            count = 0
            with args.output.open("w") as f:
                for task_idx, (task, steps) in enumerate(selected, start=1):
                    for step_idx, step in enumerate(steps):
                        query = await generate_step_query(
                            tool_call_name=step["name"],
                            tool_description="",  # MCP-Atlas doesn't include descriptions
                            task_prompt=task.get("PROMPT", ""),
                            step_position=step_idx,
                            total_steps=len(steps),
                        )
                        entry = build_ground_truth_entry(
                            task_id=task.get("TASK", "unknown"),
                            task_index=task_idx,
                            step_index=step_idx,
                            tool_call_name=step["name"],
                            query=query,
                            prompt=task.get("PROMPT", ""),
                        )
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                        count += 1
                    if task_idx % 10 == 0:
                        logger.info(f"Processed {task_idx}/{len(selected)} tasks")
            return count

        total_entries = asyncio.run(run_conversion())

    logger.info(f"Generated {total_entries} per-step GT entries")
    logger.info(f"Output: {args.output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_convert_mcp_atlas.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/convert_mcp_atlas.py tests/unit/test_convert_mcp_atlas.py
git commit -m "feat(scripts): ADR-0012 per-step MCP-Atlas GT decomposition"
```

---

## Task 4: Run MCP-Zero Import + Validate

**Prerequisites:** Task 1 (MCP-Zero data downloaded), Task 2 (script rewritten)

- [ ] **Step 1: Inspect MCP-Zero JSON schema (verify assumptions)**

```bash
uv run python -c "
import json
with open('data/external/mcp-zero/servers.json') as f:
    data = json.load(f)
entries = data if isinstance(data, list) else data.get('servers', [])
print(f'Entries: {len(entries)}')
if entries:
    print(f'Keys: {list(entries[0].keys())}')
    print(f'server_name: {entries[0].get(\"server_name\")}')
    print(f'tools: {len(entries[0].get(\"tools\", []))} tools')
    if entries[0].get('tools'):
        print(f'Tool keys: {list(entries[0][\"tools\"][0].keys())}')
"
```

If the schema doesn't match our assumptions, update `convert_server()` before proceeding.

- [ ] **Step 2: Run the import (conversion only, no Qdrant)**

```bash
uv run python scripts/import_mcp_zero.py
```

Expected output:
```
Loaded 308 raw servers from data/external/mcp-zero/servers.json
Converted ~300+ servers, ~2700+ tools
Output: data/raw/mcp_zero_servers.jsonl
```

- [ ] **Step 3: Validate output**

```bash
uv run python -c "
import json
count = 0
total_tools = 0
with open('data/raw/mcp_zero_servers.jsonl') as f:
    for line in f:
        server = json.loads(line)
        count += 1
        total_tools += len(server['tools'])
print(f'Servers: {count}, Total tools: {total_tools}')
# Verify tool_id format
first = json.loads(open('data/raw/mcp_zero_servers.jsonl').readline())
print(f'First server: {first[\"server_id\"]}')
print(f'First tool_id: {first[\"tools\"][0][\"tool_id\"]}')
assert '::' in first['tools'][0]['tool_id'], 'tool_id must use :: separator'
print('Validation passed!')
"
```

- [ ] **Step 4: Run import with Qdrant indexing**

```bash
uv run python scripts/import_mcp_zero.py --index --collection mcp_tools
```

Expected: Pre-computed text-embedding-3-large vectors upserted to Qdrant.

- [ ] **Step 5: Verify Qdrant index**

```bash
uv run python -c "
import asyncio
from qdrant_client import AsyncQdrantClient
from dotenv import load_dotenv
from src.config import Settings
load_dotenv()
s = Settings()
async def check():
    c = AsyncQdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key)
    info = await c.get_collection('mcp_tools')
    print(f'Collection: mcp_tools')
    print(f'Points: {info.points_count}')
    print(f'Vectors size: {info.config.params.vectors.size}')
    await c.close()
asyncio.run(check())
"
```

Expected: ~2700+ points, vector size 3072

- [ ] **Step 6: Commit data artifacts**

```bash
git add data/raw/mcp_zero_servers.jsonl
git commit -m "data: import MCP-Zero 308 servers to JSONL"
```

---

## Task 5: Run MCP-Atlas Dry-Run + Full Conversion

**Prerequisites:** Task 3 (script rewritten), MCP-Atlas parquet present

- [ ] **Step 1: Dry run to inspect decomposition**

```bash
uv run python scripts/convert_mcp_atlas.py --dry-run --max-tasks 5
```

Expected: Inspect output at `data/ground_truth/mcp_atlas.jsonl`, verify:
- `query_id` format: `gt-atlas-001-s00`
- `correct_tool_id` uses `::` separator
- Boilerplate calls filtered out
- `origin_task_id` + `step_index` present

- [ ] **Step 2: Verify dry run output**

```bash
uv run python -c "
import json
entries = [json.loads(l) for l in open('data/ground_truth/mcp_atlas.jsonl')]
print(f'Total entries: {len(entries)}')
print(f'Sample query_id: {entries[0][\"query_id\"]}')
print(f'Sample tool_id: {entries[0][\"correct_tool_id\"]}')
print(f'Has origin_task_id: {entries[0].get(\"origin_task_id\") is not None}')
print(f'Has step_index: {entries[0].get(\"step_index\") is not None}')
# Check no boilerplate
tool_ids = [e['correct_tool_id'] for e in entries]
assert not any('list_allowed_directories' in t for t in tool_ids), 'Boilerplate not filtered!'
print('Validation passed!')
"
```

- [ ] **Step 3: Full conversion with LLM query generation**

⚠️ Requires `OPENAI_API_KEY` in `.env`. Costs ~$0.50-2.00 for 80 tasks.

```bash
uv run python scripts/convert_mcp_atlas.py --max-tasks 80
```

Expected: ~250-400 per-step GT entries generated.

- [ ] **Step 4: Validate full output**

```bash
uv run python -c "
import json
from src.models import GroundTruthEntry
entries = []
with open('data/ground_truth/mcp_atlas.jsonl') as f:
    for line in f:
        raw = json.loads(line)
        entry = GroundTruthEntry.model_validate(raw)
        entries.append(entry)
print(f'Total valid entries: {len(entries)}')
print(f'Unique tasks: {len(set(e.origin_task_id for e in entries))}')
print(f'Avg steps/task: {len(entries) / len(set(e.origin_task_id for e in entries)):.1f}')
servers = set(e.correct_server_id for e in entries)
print(f'Unique servers: {len(servers)}')
print(f'Servers: {sorted(servers)[:10]}...')
"
```

- [ ] **Step 5: Commit GT data**

```bash
git add data/ground_truth/mcp_atlas.jsonl
git commit -m "data: MCP-Atlas per-step GT decomposition (ADR-0012)"
```

---

## Task 6: Update `scripts/run_e0.py` for New Data

**Files:**
- Modify: `scripts/run_e0.py`

The current E0 script loads GT from `seed_set.jsonl` and checks against `data/raw/servers.jsonl` (Smithery 8 servers). It needs to:
1. Use MCP-Zero pool (from `data/raw/mcp_zero_servers.jsonl`)
2. Use combined GT: MCP-Atlas + seed set (filtered to servers in pool)
3. Use the Qdrant collection populated with MCP-Zero vectors (3072 dim, text-embedding-3-large)
4. Update `Settings` usage if embedding model/dimension differs

- [ ] **Step 1: Read current `run_e0.py`**

Read the full script to understand all dependencies.

- [ ] **Step 2: Update `run_e0.py` to use new data sources**

Key changes:
- Load GT from both `data/ground_truth/seed_set.jsonl` and `data/ground_truth/mcp_atlas.jsonl`
- Filter GT entries to servers present in MCP-Zero pool (loaded from `data/raw/mcp_zero_servers.jsonl`)
- Create embedder with `text-embedding-3-large` and dimension 3072 (matching MCP-Zero pre-computed vectors)
- Update Qdrant collection name if needed
- Log counts: total GT, covered GT, per-source breakdown

```python
# Key changes in run_e0.py:

# Load GT from multiple sources
gt_paths = [
    Path("data/ground_truth/seed_set.jsonl"),
    Path("data/ground_truth/mcp_atlas.jsonl"),
]
all_entries = []
for gt_path in gt_paths:
    if gt_path.exists():
        entries = load_ground_truth(gt_path)
        logger.info(f"Loaded {len(entries)} GT entries from {gt_path.name}")
        all_entries.extend(entries)

# Filter to servers in MCP-Zero pool
pool_servers = set()
pool_path = Path("data/raw/mcp_zero_servers.jsonl")
with pool_path.open() as f:
    for line in f:
        server = json.loads(line)
        pool_servers.add(server["server_id"])

covered = [e for e in all_entries if e.correct_server_id in pool_servers]
logger.info(f"GT coverage: {len(covered)}/{len(all_entries)} entries have servers in pool")

# Use text-embedding-3-large (3072 dim) to match MCP-Zero pre-computed vectors
embedder = OpenAIEmbedder(
    api_key=settings.openai_api_key,
    model="text-embedding-3-large",
    dimension=3072,
)
```

- [ ] **Step 3: Run updated E0**

```bash
uv run python scripts/run_e0.py
```

Expected: Precision@1, Recall@K, MRR results on the new MCP-Zero + MCP-Atlas data.

- [ ] **Step 4: Record results in `.claude/evals/E0-baseline.log`**

Append results with date, data source, and pool size.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_e0.py .claude/evals/E0-baseline.log
git commit -m "feat(e0): rerun E0 on MCP-Zero pool + MCP-Atlas GT"
```

---

## Task 7: Run Full Test Suite + Verify No Regressions

- [ ] **Step 1: Run all tests**

```bash
uv run pytest tests/ -v --tb=short
```

Expected: All 258+ existing tests PASS + new tests PASS

- [ ] **Step 2: Run with coverage**

```bash
uv run pytest tests/ --cov=src -v
```

Expected: 80%+ coverage maintained

- [ ] **Step 3: Lint**

```bash
uv run ruff check src/ tests/ scripts/
uv run ruff format src/ tests/ scripts/
```

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: address lint and test issues from external data integration"
```

---

## Task 8: Update Memory + Checklist

- [ ] **Step 1: Update `docs/plan/checklist.md`**

Mark OQ-2 items as complete:
- [x] MCP-Zero 데이터셋 다운로드
- [x] MCP-Atlas GT 다운로드
- [x] `scripts/import_mcp_zero.py` canonical input contract + 검증
- [x] `scripts/convert_mcp_atlas.py` ADR-0012 per-step 분해 완성
- [x] MCP-Atlas per-step GT + self seed 80 병합 검증

- [ ] **Step 2: Update project memory**

Update `project_current_workstreams.md`:
- Stream C: External data integration → ✅ COMPLETE
- Next: Phase 6 Reranker 연동 (CohereReranker → Pipeline 연결)

- [ ] **Step 3: Commit**

```bash
git add docs/plan/checklist.md
git commit -m "docs: update checklist after external data integration"
```

---

## Execution Order

```
Task 1 (Download data)  ──────────────────────────────────┐
Task 2 (Rewrite import_mcp_zero.py) ────────┐             │
Task 3 (Rewrite convert_mcp_atlas.py) ──┐    │             │
                                         │    │             │
                                         ▼    ▼             ▼
                                     Task 4 (Run MCP-Zero import)
                                         │
                                         ▼
                                     Task 5 (Run MCP-Atlas conversion)
                                         │
                                         ▼
                                     Task 6 (Update + Run E0)
                                         │
                                         ▼
                                     Task 7 (Test suite verification)
                                         │
                                         ▼
                                     Task 8 (Update docs + memory)
```

Tasks 2 and 3 can be done in parallel. Task 1 is a manual prerequisite for Task 4.
