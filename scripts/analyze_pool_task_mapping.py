"""Analyze pool-task overlap for all MCP-Atlas tasks.

Read-only analysis tool that reports which MCP-Atlas tasks have high pool
coverage, helping decide which tasks to select for GT conversion.

Usage:
    uv run python scripts/analyze_pool_task_mapping.py \
        --input data/external/mcp-atlas \
        --pool-file data/raw/mcp_zero_servers.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# Add scripts/ and project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from convert_mcp_atlas import (
    extract_substantive_steps,
    load_parquet_tasks,
    parse_trajectory,
    split_tool_name,
)
from loguru import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_INPUT_DIR = "data/external/mcp-atlas"
DEFAULT_POOL_FILE = "data/raw/mcp_zero_servers.jsonl"

COVERAGE_BUCKETS: list[tuple[str, float, float]] = [
    ("100%", 1.0, 1.0),
    ("50-99%", 0.50, 0.99),
    ("1-49%", 0.01, 0.49),
    ("0%", 0.0, 0.0),
]


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def score_task(
    substantive_calls: list[dict],
    pool_server_ids: set[str],
) -> dict:
    """Score a single task's pool coverage.

    Args:
        substantive_calls: list of tool call dicts with 'name' key.
        pool_server_ids: set of server IDs in the pool.

    Returns:
        Dict with keys:
            pool_calls: int
            total_calls: int
            pool_ratio: float
            pool_servers: list[str] - unique pool servers used (sorted)
            non_pool_servers: list[str] - unique non-pool servers used (sorted)
    """
    if not substantive_calls:
        return {
            "pool_calls": 0,
            "total_calls": 0,
            "pool_ratio": 0.0,
            "pool_servers": [],
            "non_pool_servers": [],
        }

    pool_server_set: set[str] = set()
    non_pool_server_set: set[str] = set()
    pool_calls = 0

    for call in substantive_calls:
        server_id, _tool_name = split_tool_name(call["name"])
        if server_id in pool_server_ids:
            pool_calls += 1
            pool_server_set.add(server_id)
        else:
            non_pool_server_set.add(server_id)

    total_calls = len(substantive_calls)

    return {
        "pool_calls": pool_calls,
        "total_calls": total_calls,
        "pool_ratio": pool_calls / total_calls,
        "pool_servers": sorted(pool_server_set),
        "non_pool_servers": sorted(non_pool_server_set),
    }


def bucket_label(pool_ratio: float) -> str:
    """Return the coverage bucket label for a given pool_ratio."""
    for label, lo, hi in COVERAGE_BUCKETS:
        if lo <= pool_ratio <= hi:
            return label
    return "0%"


def aggregate_server_stats(
    task_scores: list[dict],
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    """Aggregate per-server task and call counts.

    Returns:
        (pool_stats, non_pool_stats) where each is
        {server_id: {"task_count": int, "call_count": int}}.
    """
    pool_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"task_count": 0, "call_count": 0})
    non_pool_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"task_count": 0, "call_count": 0}
    )

    for score in task_scores:
        for server_id in score["pool_servers"]:
            pool_stats[server_id]["task_count"] += 1
        for server_id in score["non_pool_servers"]:
            non_pool_stats[server_id]["task_count"] += 1

        # Count calls per server for this task
        pool_call_counts: dict[str, int] = defaultdict(int)
        non_pool_call_counts: dict[str, int] = defaultdict(int)
        for call in score.get("_calls", []):
            sid, _ = split_tool_name(call["name"])
            if sid in {s for s in score["pool_servers"]}:
                pool_call_counts[sid] += 1
            else:
                non_pool_call_counts[sid] += 1

        for sid, count in pool_call_counts.items():
            pool_stats[sid]["call_count"] += count
        for sid, count in non_pool_call_counts.items():
            non_pool_stats[sid]["call_count"] += count

    return dict(pool_stats), dict(non_pool_stats)


def format_report(
    task_scores: list[dict],
    pool_stats: dict[str, dict[str, int]],
    non_pool_stats: dict[str, dict[str, int]],
) -> str:
    """Format the analysis report as a string."""
    lines: list[str] = []

    # 1. Total tasks
    total = len(task_scores)
    lines.append("POOL-TASK MAPPING ANALYSIS")
    lines.append("=" * 55)
    lines.append(f"Total tasks analyzed: {total}")
    lines.append("")

    # 2. Tasks by coverage bucket
    lines.append("[1] Tasks by pool coverage bucket")
    lines.append("-" * 40)
    bucket_counts: dict[str, int] = defaultdict(int)
    for score in task_scores:
        bucket_counts[bucket_label(score["pool_ratio"])] += 1

    for label, _lo, _hi in COVERAGE_BUCKETS:
        count = bucket_counts.get(label, 0)
        pct = count / total * 100 if total else 0.0
        lines.append(f"  {label:<10} {count:>5} tasks ({pct:>5.1f}%)")
    lines.append("")

    # 3. Per pool-server stats
    lines.append("[2] Per pool-server: task count, call count")
    lines.append("-" * 40)
    for sid in sorted(pool_stats, key=lambda s: -pool_stats[s]["task_count"]):
        stats = pool_stats[sid]
        lines.append(f"  {sid:<35} {stats['task_count']:>4} tasks, {stats['call_count']:>5} calls")
    lines.append("")

    # 4. Per non-pool-server stats
    lines.append("[3] Per non-pool-server: task count, call count")
    lines.append("-" * 40)
    for sid in sorted(non_pool_stats, key=lambda s: -non_pool_stats[s]["task_count"]):
        stats = non_pool_stats[sid]
        lines.append(f"  {sid:<35} {stats['task_count']:>4} tasks, {stats['call_count']:>5} calls")
    lines.append("")

    # 5. Recommended task selection summary
    full = bucket_counts.get("100%", 0)
    partial = bucket_counts.get("50-99%", 0) + bucket_counts.get("1-49%", 0)
    lines.append("[4] Recommended task selection summary")
    lines.append("-" * 40)
    lines.append(f"  Fully covered (100%):    {full:>5} tasks")
    lines.append(f"  Partially covered (>0%): {partial:>5} tasks")
    lines.append(f"  No coverage (0%):        {bucket_counts.get('0%', 0):>5} tasks")
    lines.append(f"  Available for GT:        {full + partial:>5} tasks (fully + partially)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_pool_server_ids(pool_path: Path) -> set[str]:
    """Load server IDs from an MCP-Zero JSONL pool file."""
    ids: set[str] = set()
    for line in pool_path.read_text().splitlines():
        line = line.strip()
        if line:
            ids.add(json.loads(line)["server_id"])
    logger.info(f"Loaded {len(ids)} pool server IDs from {pool_path}")
    return ids


def analyze_tasks(
    tasks: list[dict],
    pool_server_ids: set[str],
) -> list[dict]:
    """Analyze all tasks and return scored results.

    Each result dict has the keys from score_task plus '_calls' for
    aggregate_server_stats.
    """
    results: list[dict] = []

    for task in tasks:
        trajectory_raw = task.get("TRAJECTORY") or task.get("trajectory")
        if trajectory_raw is None:
            continue

        if isinstance(trajectory_raw, str):
            try:
                trajectory = json.loads(trajectory_raw)
            except json.JSONDecodeError:
                logger.warning("Failed to parse trajectory JSON, skipping task")
                continue
        else:
            trajectory = trajectory_raw

        if not isinstance(trajectory, list):
            continue

        all_calls = parse_trajectory(trajectory)
        substantive = extract_substantive_steps(all_calls)

        if not substantive:
            continue

        score = score_task(substantive, pool_server_ids)
        # Attach raw calls for per-server call counting
        score["_calls"] = substantive
        results.append(score)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entrypoint for pool-task mapping analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze pool-task overlap for all MCP-Atlas tasks"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(DEFAULT_INPUT_DIR),
        help=f"MCP-Atlas parquet directory (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--pool-file",
        type=Path,
        default=Path(DEFAULT_POOL_FILE),
        help=f"MCP-Zero pool JSONL (default: {DEFAULT_POOL_FILE})",
    )
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input directory not found: {args.input}")
        logger.info("Download MCP-Atlas first. See data/external/README.md")
        sys.exit(1)

    if not args.pool_file.exists():
        logger.error(f"Pool file not found: {args.pool_file}")
        sys.exit(1)

    tasks = load_parquet_tasks(args.input)
    if not tasks:
        logger.error("No tasks loaded. Check parquet file format.")
        sys.exit(1)

    pool_server_ids = load_pool_server_ids(args.pool_file)

    task_scores = analyze_tasks(tasks, pool_server_ids)
    pool_stats, non_pool_stats = aggregate_server_stats(task_scores)
    report = format_report(task_scores, pool_stats, non_pool_stats)

    # Print report (CLI output, following verify_ground_truth.py pattern)
    print(report)  # noqa: T201


if __name__ == "__main__":
    main()
