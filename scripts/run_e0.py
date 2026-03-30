"""E0 Experiment: 1-Layer (FlatStrategy) vs 2-Layer (SequentialStrategy).

Uses MCP-Zero pool (308 servers, 2,797 tools) with combined ground truth
from seed_set.jsonl (80 entries) and mcp_atlas.jsonl (394 entries).

Qdrant collection was built with text-embedding-3-large (3072-dim) vectors.
The query embedder must match.

Usage:
    PYTHONPATH=src uv run python scripts/run_e0.py
    PYTHONPATH=src uv run python scripts/run_e0.py --top-k 10

Results saved to: .claude/evals/E0-baseline.log
"""

import argparse
import asyncio
import json
import sys
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


def _load_pool_server_ids(pool_path: Path) -> set[str]:
    """Load server IDs from the MCP-Zero pool JSONL file."""
    if not pool_path.exists():
        raise FileNotFoundError(f"Pool file not found: {pool_path}")
    server_ids: set[str] = set()
    for line in pool_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        server_ids.add(json.loads(line)["server_id"])
    logger.info(f"Pool: {len(server_ids)} servers loaded from {pool_path}")
    return server_ids


def _load_and_filter_gt(pool_server_ids: set[str]) -> list:
    """Load GT from multiple sources, filter to servers in pool, log breakdown."""
    from models import GroundTruthEntry

    gt_paths: list[Path] = []
    source_counts: dict[str, dict[str, int]] = {}

    for label, path in [("seed", GT_SEED_PATH), ("atlas", GT_ATLAS_PATH)]:
        if path.exists():
            gt_paths.append(path)
            entries = load_ground_truth(path)
            total = len(entries)
            covered = sum(1 for e in entries if e.correct_server_id in pool_server_ids)
            source_counts[label] = {"total": total, "covered": covered}
        else:
            logger.warning(f"GT file not found, skipping: {path}")

    if not gt_paths:
        logger.error("No GT files found at all.")
        return []

    # Merge all GT (deduplicates by query_id)
    all_entries: list[GroundTruthEntry] = merge_ground_truth(*gt_paths)

    # Filter to entries whose correct_server_id exists in the MCP-Zero pool
    filtered = [e for e in all_entries if e.correct_server_id in pool_server_ids]

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
        server_store = QdrantStore(client=qdrant_client, collection_name="mcp_servers")

        # --- Strategy A: FlatStrategy (1-layer) ---
        flat = FlatStrategy(embedder=embedder, tool_store=tool_store)
        logger.info("Running FlatStrategy (1-layer)...")
        flat_result = await evaluate(flat, entries, top_k=args.top_k)

        # --- Strategy B: SequentialStrategy (2-layer) ---
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
        f"\n{'=' * 60}\nE0 EXPERIMENT RESULTS  (n={len(entries)}, top_k={args.top_k})\n{'=' * 60}"
    )

    def row(metric: str, f: float | None, s: float | None, delta: bool = True) -> str:
        f_str = f"{f:>14.3f}" if f is not None else f"{'N/A':>14}"
        s_str = f"{s:>20.3f}" if s is not None else f"{'N/A':>20}"
        d = ""
        if delta and f is not None and s is not None:
            d = f" {s - f:>+8.3f}"
        return f"{metric:<20} {f_str} {s_str}{d}"

    def row_ms(metric: str, f: float, s: float) -> str:
        return f"{metric:<20} {f:>14.1f} {s:>20.1f}"

    rows = [
        f"{'Metric':<20} {'FlatStrategy':>14} {'SequentialStrategy':>20} {'Delta':>8}",
        f"{'-' * 20} {'-' * 14} {'-' * 20} {'-' * 8}",
        row("Precision@1", flat_result.precision_at_1, seq_result.precision_at_1),
        row("Recall@K", flat_result.recall_at_k, seq_result.recall_at_k),
        row("MRR", flat_result.mrr, seq_result.mrr),
        row("NDCG@5", flat_result.ndcg_at_5, seq_result.ndcg_at_5),
        row("Confusion Rate", flat_result.confusion_rate, seq_result.confusion_rate, delta=False),
        row("ECE", flat_result.ece, seq_result.ece, delta=False),
        row_ms("Latency p50 (ms)", flat_result.latency_p50, seq_result.latency_p50),
        row_ms("Latency mean (ms)", flat_result.latency_mean, seq_result.latency_mean),
    ]
    output = header + "\n" + "\n".join(rows) + "\n"
    logger.info(output)

    # --- Save log ---
    EVAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVAL_LOG_PATH.open("w") as f:
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
    args = parser.parse_args()
    asyncio.run(main(args))
