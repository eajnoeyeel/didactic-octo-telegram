"""E0 Experiment: 1-Layer (FlatStrategy) vs 2-Layer (SequentialStrategy).

Uses MCP-Zero pool (308 servers, 2,797 tools) with combined ground truth
from seed_set.jsonl and mcp_atlas.jsonl.

Qdrant collection was built with text-embedding-3-large (3072-dim) vectors.
The query embedder must match.

Usage:
    PYTHONPATH=src uv run python scripts/run_e0.py
    PYTHONPATH=src uv run python scripts/run_e0.py --no-rerank
    PYTHONPATH=src uv run python scripts/run_e0.py --top-k 10
    PYTHONPATH=src uv run python scripts/run_e0.py --pool-size 50
    PYTHONPATH=src uv run python scripts/run_e0.py --sweep
    PYTHONPATH=src uv run python scripts/run_e0.py --no-wandb

Results saved to:
    .claude/evals/E0-baseline.log  (default run)
    data/results/e0_result.json    (single run)
    data/results/e5_scale_sweep.json (sweep mode)
    W&B project: mcp-discovery     (unless --no-wandb)
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import wandb

# Add src/ to path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from loguru import logger
from qdrant_client import AsyncQdrantClient

from config import Settings
from data.ground_truth import load_ground_truth, merge_ground_truth
from embedding.openai_embedder import OpenAIEmbedder
from evaluation.harness import evaluate
from evaluation.metrics import EvalResult
from pipeline.flat import FlatStrategy
from pipeline.parallel import ParallelStrategy
from pipeline.sequential import SequentialStrategy
from reranking.base import Reranker
from reranking.cohere_reranker import CohereReranker
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
STRATEGY_CHOICES: list[str] = ["flat", "sequential", "parallel", "all"]


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
            "server_recall_at_k": result.server_recall_at_k,
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
    reranker_model: str | None = None,
) -> dict:
    """Build the complete JSON payload for one experiment run."""
    return {
        "experiment": experiment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "pool_size": pool_size,
            "top_k": top_k,
            "embedding_model": E0_EMBEDDING_MODEL,
            "reranker": reranker_model or "none",
            "gt_sources": ["seed_set", "mcp_atlas"],
        },
        "strategies": [_eval_result_to_dict(r) for r in results],
    }


def _save_json(data: dict, path: Path) -> None:
    """Write dict as formatted JSON, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    logger.info(f"JSON results saved to {path}")


def _format_results_table(
    eval_results: list[EvalResult],
    n_entries: int,
    top_k: int,
    pool_size: int | None = None,
) -> str:
    """Format comparison table for any number of strategies."""
    pool_label = f", pool={pool_size}" if pool_size is not None else ""
    names = [r.strategy_name for r in eval_results]
    col_width = 20
    name_header = "".join(f"{n:>{col_width}}" for n in names)
    name_sep = "".join(f"{'-' * col_width}" for _ in names)
    header = (
        f"\n{'=' * 60}\n"
        f"E0 EXPERIMENT RESULTS  (n={n_entries}, top_k={top_k}{pool_label})\n"
        f"{'=' * 60}\n"
        f"{'Metric':<20} {name_header}\n"
        f"{'-' * 20} {name_sep}\n"
    )

    metrics = [
        ("Precision@1", "precision_at_1"),
        ("Recall@K", "recall_at_k"),
        ("Server Recall@K", "server_recall_at_k"),
        ("MRR", "mrr"),
        ("NDCG@5", "ndcg_at_5"),
        ("Confusion Rate", "confusion_rate"),
        ("ECE", "ece"),
    ]
    latency_metrics = [
        ("Latency p50 (ms)", "latency_p50"),
        ("Latency mean (ms)", "latency_mean"),
    ]

    rows: list[str] = []
    for label, attr in metrics:
        vals = "".join(
            f"{getattr(r, attr):>{col_width}.3f}"
            if getattr(r, attr) is not None
            else f"{'N/A':>{col_width}}"
            for r in eval_results
        )
        rows.append(f"{label:<20} {vals}")

    for label, attr in latency_metrics:
        vals = "".join(f"{getattr(r, attr):>{col_width}.1f}" for r in eval_results)
        rows.append(f"{label:<20} {vals}")

    return header + "\n".join(rows) + "\n"


async def _run_strategies(
    strategy_names: list[str],
    embedder: OpenAIEmbedder,
    tool_store: QdrantStore,
    server_store: QdrantStore,
    entries: list,
    top_k: int,
    reranker: Reranker | None = None,
) -> list[EvalResult]:
    """Run requested strategies, return list of EvalResults."""
    results: list[EvalResult] = []

    for name in strategy_names:
        if name == "flat":
            strategy = FlatStrategy(
                embedder=embedder, tool_store=tool_store, reranker=reranker
            )
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
        else:
            raise ValueError(f"Unknown strategy: {name}")

        logger.info(f"Running {name} strategy...")
        result = await evaluate(strategy, entries, top_k=top_k)
        results.append(result)

    return results


def _format_sweep_table(sweep_payloads: list[dict]) -> str:
    """Format a summary table of sweep results across pool sizes."""
    header = (
        f"\n{'=' * 90}\n"
        f"E5 SCALE SWEEP SUMMARY\n"
        f"{'=' * 90}\n"
        f"{'Pool':>6} {'Strategy':<22} {'P@1':>7} {'R@K':>7} {'MRR':>7} "
        f"{'NDCG@5':>7} {'Latency p50':>12}\n"
        f"{'-' * 6} {'-' * 22} {'-' * 7} {'-' * 7} {'-' * 7} {'-' * 7} {'-' * 12}"
    )
    rows: list[str] = []
    for payload in sweep_payloads:
        pool_size = payload["config"]["pool_size"]
        for s in payload["strategies"]:
            m = s["metrics"]
            rows.append(
                f"{pool_size:>6} {s['name']:<22} {m['precision_at_1']:>7.3f} "
                f"{m['recall_at_k']:>7.3f} {m['mrr']:>7.3f} "
                f"{m['ndcg_at_5']:>7.3f} {m['latency_p50']:>10.1f}ms"
            )
    return header + "\n" + "\n".join(rows) + "\n"


def _log_wandb_results(eval_results: list[EvalResult]) -> None:
    """Log all strategy results to the active W&B run."""
    log_data: dict[str, float] = {}
    for result in eval_results:
        name = result.strategy_name
        log_data[f"{name}/precision_at_1"] = result.precision_at_1
        log_data[f"{name}/recall_at_k"] = result.recall_at_k
        log_data[f"{name}/server_recall_at_k"] = result.server_recall_at_k
        log_data[f"{name}/mrr"] = result.mrr
        log_data[f"{name}/ndcg_at_5"] = result.ndcg_at_5
        if result.confusion_rate is not None:
            log_data[f"{name}/confusion_rate"] = result.confusion_rate
        log_data[f"{name}/latency_p50_ms"] = result.latency_p50
        log_data[f"{name}/latency_p95_ms"] = result.latency_p95
        log_data[f"{name}/n_failed"] = result.n_failed

    # Delta between flat and sequential if both present
    by_name = {r.strategy_name: r for r in eval_results}
    flat = by_name.get("FlatStrategy")
    seq = by_name.get("SequentialStrategy")
    if flat and seq:
        log_data["delta/precision_at_1"] = seq.precision_at_1 - flat.precision_at_1
        log_data["delta/mrr"] = seq.mrr - flat.mrr

    wandb.log(log_data)


async def main(args: argparse.Namespace) -> None:
    settings = Settings()
    use_wandb = not args.no_wandb

    # --- Resolve pool sizes to run ---
    if args.sweep:
        if args.pool_size is not None:
            logger.warning("--sweep overrides --pool-size; running full sweep")
        pool_sizes: list[int | None] = SWEEP_SIZES  # type: ignore[assignment]
    else:
        pool_sizes = [args.pool_size]  # None = all servers

    # --- Setup shared components (reused across sweep iterations) ---
    embedder = OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=E0_EMBEDDING_MODEL,
        dimension=E0_EMBEDDING_DIMENSION,
    )
    qdrant_client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

    # --- Setup reranker (if COHERE_API_KEY available and not disabled) ---
    reranker: Reranker | None = None
    if not args.no_rerank and settings.cohere_api_key:
        reranker = CohereReranker(
            api_key=settings.cohere_api_key,
            model=settings.cohere_rerank_model,
            max_rpm=args.cohere_rpm,
        )
        logger.info(
            f"Reranker enabled: {settings.cohere_rerank_model} "
            f"(rate limit: {args.cohere_rpm} rpm)"
        )
    elif args.no_rerank:
        logger.info("Reranker disabled via --no-rerank flag")
    else:
        logger.warning("COHERE_API_KEY not set — running without reranker")

    sweep_payloads: list[dict] = []

    try:
        tool_store = QdrantStore(
            client=qdrant_client, collection_name=settings.qdrant_collection_name
        )
        server_store = QdrantStore(client=qdrant_client, collection_name="mcp_servers")

        for pool_size in pool_sizes:
            logger.info(f"\n{'=' * 40}\nPool size: {pool_size or 'ALL'}\n{'=' * 40}")

            # Load pool (subset or all)
            pool_server_ids = _load_pool_server_ids(POOL_PATH, pool_size=pool_size)
            actual_pool_size = len(pool_server_ids)

            # Load & filter GT
            entries = _load_and_filter_gt(pool_server_ids)
            if not entries:
                logger.warning(f"No GT entries for pool_size={pool_size}. Skipping.")
                continue

            logger.info(
                f"GT: {len(entries)} entries (covered by pool of {actual_pool_size} servers)"
            )

            # Determine which strategies to run
            if args.strategy == "all":
                strategy_names = ["flat", "sequential", "parallel"]
            else:
                strategy_names = [args.strategy]

            # --- W&B: init run for this iteration ---
            if use_wandb:
                experiment_label = "E5" if args.sweep else "E0"
                wandb.init(
                    project="mcp-discovery",
                    name=f"{experiment_label}-{args.strategy}-pool{actual_pool_size}",
                    config={
                        "experiment": experiment_label,
                        "strategy": args.strategy,
                        "pool_size": actual_pool_size,
                        "top_k": args.top_k,
                        "embedding_model": E0_EMBEDDING_MODEL,
                        "reranker": settings.cohere_rerank_model if reranker else "none",
                        "gt_sources": ["seed_set", "mcp_atlas"],
                        "n_queries": len(entries),
                    },
                )

            # Run evaluation
            eval_results = await _run_strategies(
                strategy_names, embedder, tool_store, server_store, entries, args.top_k,
                reranker,
            )

            # --- W&B: log results + finish ---
            if use_wandb:
                _log_wandb_results(eval_results)
                wandb.finish()

            # Print per-iteration results table
            output = _format_results_table(eval_results, len(entries), args.top_k, pool_size)
            logger.info(output)

            # Build JSON payload
            reranker_model = settings.cohere_rerank_model if reranker else None
            payload = _build_result_payload(
                experiment="E0",
                pool_size=actual_pool_size,
                top_k=args.top_k,
                results=eval_results,
                reranker_model=reranker_model,
            )
            sweep_payloads.append(payload)

            # For default run (no --pool-size, no --sweep): save eval log (backward compat)
            if not args.sweep and args.pool_size is None:
                EVAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                with EVAL_LOG_PATH.open("w") as f:
                    f.write(output)
                    reranker_label = settings.cohere_rerank_model if reranker else "none"
                    f.write(
                        f"\nPool: MCP-Zero ({actual_pool_size} servers)\n"
                        f"GT sources: seed_set ({GT_SEED_PATH}), mcp_atlas ({GT_ATLAS_PATH})\n"
                        f"Embedding: {E0_EMBEDDING_MODEL} ({E0_EMBEDDING_DIMENSION}-dim)\n"
                        f"Reranker: {reranker_label}\n"
                        f"Entries used: {len(entries)} (covered by pool)\n"
                    )
                logger.info(f"Results saved to {EVAL_LOG_PATH}")

    finally:
        await qdrant_client.close()

    # --- Save JSON results ---
    if args.sweep:
        sweep_data = {"results": sweep_payloads}
        _save_json(sweep_data, RESULTS_DIR / "e5_scale_sweep.json")
        # Print sweep summary table
        logger.info(_format_sweep_table(sweep_payloads))
    else:
        if sweep_payloads:
            _save_json(sweep_payloads[0], RESULTS_DIR / "e0_result.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E0: 1-Layer vs 2-Layer experiment")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--pool-size",
        type=int,
        default=None,
        help="Number of servers to use (alphabetical subset). Default: all",
    )
    parser.add_argument(
        "--strategy",
        choices=STRATEGY_CHOICES,
        default="all",
        help="Strategy to run: flat, sequential, parallel, or all (default: all)",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Run E5 scale sweep: pool sizes [5, 20, 50, 100, 200, 308]",
    )
    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Disable Cohere reranker (embedding-only baseline)",
    )
    parser.add_argument(
        "--cohere-rpm",
        type=int,
        default=10,
        help="Cohere API rate limit in requests per minute (default: 10 for Trial key)",
    )
    parser.add_argument(
        "--no-wandb",
        action="store_true",
        help="Disable W&B logging (offline/local test mode)",
    )
    args = parser.parse_args()
    asyncio.run(main(args))
