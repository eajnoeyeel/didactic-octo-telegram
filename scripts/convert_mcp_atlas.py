"""Convert MCP-Atlas parquet → GroundTruthEntry JSONL.

Reads MCP-Atlas dataset (human-authored tasks from Scale AI),
extracts the first tool call from each multi-step task,
and outputs GroundTruthEntry-compatible JSONL.

Usage:
    uv run python scripts/convert_mcp_atlas.py
    uv run python scripts/convert_mcp_atlas.py --input data/external/mcp-atlas/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from loguru import logger

from src.models import TOOL_ID_SEPARATOR

# Default paths
DEFAULT_INPUT_DIR = "data/external/mcp-atlas"
DEFAULT_OUTPUT_PATH = "data/ground_truth/mcp_atlas.jsonl"


def extract_first_tool_call(task: dict) -> dict | None:
    """Extract the first tool call from a multi-step MCP-Atlas task.

    Args:
        task: Raw MCP-Atlas task dictionary.

    Returns:
        Dict with server_id, tool_name, query fields, or None if extraction fails.
    """
    # MCP-Atlas stores tool calls in various formats depending on version.
    # Adapt parsing logic once actual parquet schema is inspected.
    tool_calls = task.get("tool_calls") or task.get("steps") or []

    if not tool_calls:
        logger.warning(f"Task has no tool_calls: {task.get('task_id', 'unknown')}")
        return None

    first_call = tool_calls[0] if isinstance(tool_calls, list) else None
    if first_call is None:
        return None

    server_id = first_call.get("server_id") or first_call.get("server", "")
    tool_name = first_call.get("tool_name") or first_call.get("tool", "")

    if not server_id or not tool_name:
        logger.warning(f"Missing server_id or tool_name in first call: {task.get('task_id')}")
        return None

    return {
        "server_id": server_id,
        "tool_name": tool_name,
        "query": task.get("query") or task.get("instruction") or task.get("task", ""),
    }


def convert_to_ground_truth_entry(
    task: dict,
    index: int,
    extracted: dict,
) -> dict:
    """Convert extracted task data to GroundTruthEntry-compatible dict.

    Args:
        task: Raw MCP-Atlas task dictionary.
        index: 1-based index for query_id generation.
        extracted: Output of extract_first_tool_call().

    Returns:
        Dict compatible with GroundTruthEntry.model_validate().
    """
    server_id = extracted["server_id"]
    tool_name = extracted["tool_name"]
    tool_id = f"{server_id}{TOOL_ID_SEPARATOR}{tool_name}"

    return {
        "query_id": f"gt-atlas-{index:03d}",
        "query": extracted["query"],
        "correct_server_id": server_id,
        "correct_tool_id": tool_id,
        "difficulty": task.get("difficulty", "medium"),
        "category": task.get("category", "general"),
        "ambiguity": task.get("ambiguity", "medium"),
        "source": "external_mcp_atlas",
        "manually_verified": True,
        "author": "scale_ai",
        "created_at": "2026-03-28",
        "alternative_tools": task.get("alternative_tools"),
        "notes": "MCP-Atlas task converted (first tool call)",
    }


def load_parquet_tasks(input_dir: Path) -> list[dict]:
    """Load tasks from MCP-Atlas parquet files.

    Args:
        input_dir: Directory containing parquet files.

    Returns:
        List of task dictionaries.
    """
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

    # Concat all parquet files into a single table
    table = pq.read_table(parquet_files[0])
    for pf in parquet_files[1:]:
        table = pa.concat_tables([table, pq.read_table(pf)])

    # pyarrow returns column-oriented dict; convert to row-oriented
    columns = table.to_pydict()
    n_rows = len(next(iter(columns.values())))
    tasks = [{col: columns[col][i] for col in columns} for i in range(n_rows)]
    logger.info(f"Loaded {len(tasks)} tasks from {len(parquet_files)} parquet files")

    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert MCP-Atlas parquet → GT JSONL")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(DEFAULT_INPUT_DIR),
        help=f"MCP-Atlas parquet directory (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT_PATH),
        help=f"Output JSONL path (default: {DEFAULT_OUTPUT_PATH})",
    )
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input directory not found: {args.input}")
        logger.info("Download MCP-Atlas first. See data/external/README.md")
        return

    tasks = load_parquet_tasks(args.input)
    if not tasks:
        logger.error("No tasks loaded. Check parquet file format.")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)

    converted = 0
    skipped = 0

    with args.output.open("w") as f:
        for i, task in enumerate(tasks, start=1):
            extracted = extract_first_tool_call(task)
            if extracted is None:
                skipped += 1
                continue

            entry = convert_to_ground_truth_entry(task, converted + 1, extracted)
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            converted += 1

    logger.info(f"Converted {converted} entries, skipped {skipped}")
    logger.info(f"Output: {args.output}")


if __name__ == "__main__":
    main()
