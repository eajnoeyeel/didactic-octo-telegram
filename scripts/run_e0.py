"""E0 Experiment: 1-Layer (FlatStrategy) vs 2-Layer (SequentialStrategy).

Uses MCP-Zero pool (308 servers, 2,797 tools) with combined ground truth
from seed_set.jsonl and mcp_atlas.jsonl.

Qdrant collection was built with text-embedding-3-large (3072-dim) vectors.
The query embedder must match.

Usage:
    PYTHONPATH=src uv run python scripts/run_e0.py
    PYTHONPATH=src uv run python scripts/run_e0.py --top-k 10
    PYTHONPATH=src uv run python scripts/run_e0.py --pool-size 50
    PYTHONPATH=src uv run python scripts/run_e0.py --sweep

Results saved to:
    .claude/evals/E0-baseline.log  (default run)
    data/results/e0_result.json    (single run)
    data/results/e5_scale_sweep.json (sweep mode)
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src/ to path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from loguru import logger
from qdrant_client import AsyncQdrantClient

from config import Settings
from data.ground_truth import load_ground_truth, merge_ground_truth
from embedding.openai_embedder import OpenAIEmbedder
from evaluation.harness import evaluate
from pipeline.flat import FlatStrategy
from pipeline.sequential import SequentialStrategy
from retrieval.qdrant_store import QdrantStore

load_dotenv()

EVAL_LOG_PATH = Path(".claude/evals/E0-baseline.log")

# Ground truth file paths
GT_SEED_PATH = Path("data/ground_truth/seed_set.jsonl")
GT_ATLAS_PATH = Path("data/ground_truth/mcp_atlas.jsonl")

# MCP-Zero pool (replaces old Smithery 8-server pool)
POOL_PATH = Path("data/raw/mcp_zero_servers.jsonl")

# Embedding model must match the Qdrant collection vectors (text-embedding-3-large, 3072-dim)
E0_EMBEDDING_MODEL = "text-embedding-3-large"
E0_EMBEDDING_DIMENSION = 3072

RESULTS_DIR = Path("data/results")
SWEEP_SIZES: list[int] = [5, 20, 50, 100, 200, 308]


def _load_pool_server_ids(pool_path: Path, pool_size: int | None = None) -> list[str]:
    """Load server IDs from MCP-Zero pool JSONL, optionally taking first N (alphabetical)."""
    if not pool_path.exists():
        raise FileNotFoundError(f"Pool file not found: {pool_path}")
    server_ids: set[str] = set()
    for line in pool_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        server_ids.add(json.loads(line)["server_id"])

    sorted_ids = sorted(server_ids)
    if pool_size is not None:
        sorted_ids = sorted_ids[:pool_size]

    logger.info(
        f"Pool: {len(sorted_ids)} servers"
        + (f" (subset of {len(server_ids)})" if pool_size is not None else "")
        + f" loaded from {pool_path}"
    )
    return sorted_ids


def _load_and_filter_gt(pool_server_ids: list[str]) -> list:
    """Load GT from multiple sources, filter to servers in pool, log breakdown."""
    from models import GroundTruthEntry

    pool_set = set(pool_server_ids)

    gt_paths: list[Path] = []
    source_counts: dict[str, dict[str, int]] = {}

    for label, path in [("seed", GT_SEED_PATH), ("atlas", GT_ATLAS_PATH)]:
        if path.exists():
            gt_paths.append(path)
            entries = load_ground_truth(path)
            total = len(entries)
            covered = sum(1 for e in entries if e.correct_server_id in pool_set)
            source_counts[label] = {"total": total, "covered": covered}
        else:
            logger.warning(f"GT file not found, skipping: {path}")

    if not gt_paths:
        logger.error("No GT files found at all.")
        return []

    # Merge all GT (deduplicates by query_id)
    all_entries: list[GroundTruthEntry] = merge_ground_truth(*gt_paths)

    # Filter to entries whose correct_server_id exists in the MCP-Zero pool
    filtered = [e for e in all_entries if e.correct_server_id in pool_set]

    # Log source breakdown
    logger.info("--- GT Source Breakdown ---")
    for label, counts in source_counts.items():
        logger.info(
            f"  {label}: {counts['total']} total, "
            f"{counts['covered']} covered by pool "
            f"({counts['covered'] / counts['total'] * 100:.1f}%)"
        )
    logger.info(
        f"  Combined: {len(all_entries)} total, "
        f"{len(filtered)} covered by pool "
        f"({len(filtered) / len(all_entries) * 100:.1f}%)"
    )

    return filtered


def _eval_result_to_dict(result) -> dict:
    """Convert EvalResult to JSON-serializable dict (excluding per_query)."""
    return {
        "name": result.strategy_name,
        "metrics": {
            "precision_at_1": result.precision_at_1,
            "recall_at_k": result.recall_at_k,
            "mrr": result.mrr,
            "ndcg_at_5": result.ndcg_at_5,
            "confusion_rate": result.confusion_rate,
            "ece": result.ece,
            "latency_p50": result.latency_p50,
            "latency_p95": result.latency_p95,
            "latency_p99": result.latency_p99,
            "latency_mean": result.latency_mean,
        },
        "n_queries": result.n_queries,
        "n_failed": result.n_failed,
    }


def _build_result_payload(
    experiment: str,
    pool_size: int,
    top_k: int,
    results: list,
) -> dict:
    """Build the complete JSON payload for one experiment run."""
    return {
        "experiment": experiment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "pool_size": pool_size,
            "top_k": top_k,
            "embedding_model": E0_EMBEDDING_MODEL,
            "gt_sources": ["seed_set", "mcp_atlas"],
        },
        "strategies": [_eval_result_to_dict(r) for r in results],
    }


def _save_json(data: dict, path: Path) -> None:
    """Write dict as formatted JSON, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    logger.info(f"JSON results saved to {path}")


async def main(args: argparse.Namespace) -> None:
    settings = Settings()

    # --- Load pool server IDs from MCP-Zero ---
    pool_server_ids = _load_pool_server_ids(POOL_PATH)

    # --- Load and filter GT ---
    entries = _load_and_filter_gt(pool_server_ids)

    if not entries:
        logger.error("No GT entries covered by current MCP-Zero pool. Check data files.")
        return

    logger.info(f"GT: {len(entries)} entries (covered by MCP-Zero pool)")

    # --- Setup shared components ---
    # Embedder must match Qdrant collection (text-embedding-3-large, 3072-dim)
    embedder = OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=E0_EMBEDDING_MODEL,
        dimension=E0_EMBEDDING_DIMENSION,
    )
    qdrant_client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

    try:
        tool_store = QdrantStore(
            client=qdrant_client, collection_name=settings.qdrant_collection_name
        )

        flat_result = None
        seq_result = None

        # --- Strategy A: FlatStrategy (1-layer) ---
        if args.strategy in ("flat", "both"):
            flat = FlatStrategy(embedder=embedder, tool_store=tool_store)
            logger.info("Running FlatStrategy (1-layer)...")
            flat_result = await evaluate(flat, entries, top_k=args.top_k)

        # --- Strategy B: SequentialStrategy (2-layer) ---
        if args.strategy in ("sequential", "both"):
            server_store = QdrantStore(client=qdrant_client, collection_name="mcp_servers")
            seq = SequentialStrategy(
                embedder=embedder,
                tool_store=tool_store,
                server_store=server_store,
                top_k_servers=5,
            )
            logger.info("Running SequentialStrategy (2-layer)...")
            seq_result = await evaluate(seq, entries, top_k=args.top_k)

    finally:
        await qdrant_client.close()

    # --- Print results ---
    header = (
        f"\n{'=' * 60}\n"
        f"E0 EXPERIMENT RESULTS  (n={len(entries)}, top_k={args.top_k}, strategy={args.strategy})\n"
        f"{'=' * 60}"
    )

    lines = [header]

    if flat_result and seq_result:
        lines.append(f"{'Metric':<20} {'Flat':>14} {'Sequential':>14} {'Delta':>8}")
        lines.append(f"{'-' * 20} {'-' * 14} {'-' * 14} {'-' * 8}")
        for metric in ["precision_at_1", "recall_at_k", "mrr", "ndcg_at_5"]:
            f_val = getattr(flat_result, metric)
            s_val = getattr(seq_result, metric)
            delta = f" {s_val - f_val:>+.3f}" if f_val is not None and s_val is not None else ""
            lines.append(f"{metric:<20} {f_val:>14.3f} {s_val:>14.3f}{delta}")
        for metric in ["confusion_rate", "ece"]:
            f_val = getattr(flat_result, metric)
            s_val = getattr(seq_result, metric)
            lines.append(f"{metric:<20} {f_val:>14.3f} {s_val:>14.3f}")
        lines.append(
            f"{'latency_mean (ms)':<20} "
            f"{flat_result.latency_mean:>14.1f} {seq_result.latency_mean:>14.1f}"
        )
    else:
        result = flat_result or seq_result
        name = "Flat" if flat_result else "Sequential"
        lines.append(f"Strategy: {name}")
        lines.append(f"{'Metric':<20} {'Value':>14}")
        lines.append(f"{'-' * 20} {'-' * 14}")
        for metric in [
            "precision_at_1",
            "recall_at_k",
            "mrr",
            "ndcg_at_5",
            "confusion_rate",
            "ece",
        ]:
            val = getattr(result, metric)
            lines.append(
                f"{metric:<20} {val:>14.3f}" if val is not None else f"{metric:<20} {'N/A':>14}"
            )
        lines.append(f"{'latency_mean (ms)':<20} {result.latency_mean:>14.1f}")
        lines.append(f"{'latency_p50 (ms)':<20} {result.latency_p50:>14.1f}")
        lines.append(f"{'latency_p95 (ms)':<20} {result.latency_p95:>14.1f}")

    output = "\n".join(lines) + "\n"
    logger.info(output)

    # --- Save log ---
    EVAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVAL_LOG_PATH.open("a") as f:
        f.write(f"\n--- Run: {args.strategy} ---\n")
        f.write(output)
        f.write(
            f"\nPool: MCP-Zero ({len(pool_server_ids)} servers)\n"
            f"GT sources: seed_set ({GT_SEED_PATH}), mcp_atlas ({GT_ATLAS_PATH})\n"
            f"Embedding: {E0_EMBEDDING_MODEL} ({E0_EMBEDDING_DIMENSION}-dim)\n"
            f"Entries used: {len(entries)} (covered by pool)\n"
        )
    logger.info(f"Results saved to {EVAL_LOG_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E0: 1-Layer vs 2-Layer experiment")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--strategy",
        type=str,
        choices=["flat", "sequential", "both"],
        default="both",
        help="Which strategy to run (default: both)",
    )
    args = parser.parse_args()
    asyncio.run(main(args))
