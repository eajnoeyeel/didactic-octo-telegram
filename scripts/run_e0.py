"""E0 Experiment: 1-Layer (FlatStrategy) vs 2-Layer (SequentialStrategy).

Usage:
    PYTHONPATH=src uv run python scripts/run_e0.py
    PYTHONPATH=src uv run python scripts/run_e0.py --top-k 10

Results saved to: .claude/evals/E0-baseline.log
"""

import argparse
import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from qdrant_client import AsyncQdrantClient

from config import Settings
from data.ground_truth import load_ground_truth
from embedding.openai_embedder import OpenAIEmbedder
from evaluation.harness import evaluate
from pipeline.flat import FlatStrategy
from pipeline.sequential import SequentialStrategy
from retrieval.qdrant_store import QdrantStore

load_dotenv()

EVAL_LOG_PATH = Path(".claude/evals/E0-baseline.log")


async def main(args: argparse.Namespace) -> None:
    settings = Settings()

    # --- Load GT (manually_verified seed set only) ---
    gt_path = Path("data/ground_truth/seed_set.jsonl")
    all_entries = load_ground_truth(gt_path)
    entries = [e for e in all_entries if e.manually_verified]

    # Filter to entries whose correct_server_id is in the index
    indexed_servers = set(
        json.loads(line)["server_id"]
        for line in open("data/raw/servers.jsonl")
    )
    entries = [e for e in entries if e.correct_server_id in indexed_servers]
    logger.info(f"GT: {len(entries)} entries (manually_verified + server in index)")

    if not entries:
        logger.error("No GT entries covered by current index. Re-crawl missing servers.")
        return

    # --- Setup shared components ---
    embedder = OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
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
        d = f" {s - f:>+8.3f}" if delta and f is not None and s is not None else ""
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
    print(output)

    # --- Save log ---
    EVAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVAL_LOG_PATH.open("w") as f:
        f.write(output)
        f.write(
            f"\nNote: Seed Set only (n={len(entries)}, 4 servers: "
            "instagram, EthanHenrickson/math-mcp, clay-inc/clay-mcp, github)\n"
        )
        f.write(
            "Missing from GT: arxiv, brave-search, postgres, yahoo-finance"
            " (removed from Smithery)\n"
        )
    logger.info(f"Results saved to {EVAL_LOG_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E0: 1-Layer vs 2-Layer experiment")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(main(args))
