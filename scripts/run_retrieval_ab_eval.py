"""Retrieval 3-Way Evaluation — P@1 비교 (원본 vs search_description vs optimized_description).

3-way A/B 검증:
  - Condition A: Original description (Control)
  - Condition B: search_description (Treatment A — PRIMARY, ~23 words, retrieval-optimized)
  - Condition C: optimized_description (Treatment B — secondary, ~94 words, human-readable)

Usage:
    PYTHONPATH=src uv run python scripts/run_retrieval_ab_eval.py \
        --tools data/raw/servers.jsonl \
        --ground-truth data/ground_truth/seed_set.jsonl \
        --optimized data/verification/grounded_optimization_results.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loguru import logger

if TYPE_CHECKING:
    from embedding.base import Embedder


async def load_tools(tools_path: Path) -> dict[str, str]:
    """서버 JSONL에서 tool_id -> description 매핑 로드."""
    tool_descriptions: dict[str, str] = {}
    with open(tools_path) as f:
        for line in f:
            server = json.loads(line.strip())
            for tool in server.get("tools", []):
                tool_id = tool.get("tool_id", "")
                desc = tool.get("description", "")
                if tool_id and desc:
                    tool_descriptions[tool_id] = desc
    return tool_descriptions


async def load_ground_truth(gt_path: Path) -> dict[str, list[str]]:
    """Ground truth를 correct_tool_id별로 쿼리 그룹화."""
    relevant_queries: dict[str, list[str]] = {}
    with open(gt_path) as f:
        for line in f:
            entry = json.loads(line.strip())
            tool_id = entry["correct_tool_id"]
            query = entry["query"]
            relevant_queries.setdefault(tool_id, []).append(query)
    return relevant_queries


async def load_optimized(opt_path: Path) -> dict[str, str]:
    """최적화된 description 로드 (성공 건만)."""
    optimized: dict[str, str] = {}
    with open(opt_path) as f:
        for line in f:
            entry = json.loads(line.strip())
            if entry.get("status") == "success":
                optimized[entry["tool_id"]] = entry["optimized_description"]
    return optimized


async def load_search_descriptions(opt_path: Path) -> dict[str, str]:
    """search_description 로드 (성공 건만)."""
    search: dict[str, str] = {}
    with open(opt_path) as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line.strip())
            if entry.get("status") == "success" and entry.get("search_description"):
                search[entry["tool_id"]] = entry["search_description"]
    return search


async def compute_retrieval_scores(
    embedder: "Embedder",
    tool_descriptions: dict[str, str],
    relevant_queries: dict[str, list[str]],
) -> dict[str, dict]:
    """임베딩 기반 검색 성능 측정 (인메모리 코사인 유사도)."""
    tool_ids = list(tool_descriptions.keys())
    texts = [tool_descriptions[tid] for tid in tool_ids]

    logger.info(f"Embedding {len(texts)} tool descriptions...")
    vectors = await embedder.embed_batch(texts)
    pool = np.stack(vectors)
    norms = np.linalg.norm(pool, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    pool = pool / norms

    results: dict[str, dict] = {}

    for tool_id, queries in relevant_queries.items():
        if tool_id not in tool_ids:
            continue

        tool_idx = tool_ids.index(tool_id)
        ranks: list[int] = []

        for query in queries:
            q_vec = await embedder.embed_one(query)
            q_norm = np.linalg.norm(q_vec)
            if q_norm > 0:
                q_vec = q_vec / q_norm
            sims = pool @ q_vec
            sorted_indices = np.argsort(-sims)
            rank = int(np.where(sorted_indices == tool_idx)[0][0]) + 1
            ranks.append(rank)

        p_at_1 = sum(1 for r in ranks if r == 1) / len(ranks) if ranks else 0
        mrr = sum(1.0 / r for r in ranks) / len(ranks) if ranks else 0
        results[tool_id] = {
            "p_at_1": p_at_1,
            "mrr": mrr,
            "avg_rank": sum(ranks) / len(ranks) if ranks else 0,
            "n_queries": len(ranks),
        }

    return results


async def main(args: argparse.Namespace) -> None:
    tools_path = Path(args.tools)
    gt_path = Path(args.ground_truth)
    opt_path = Path(args.optimized)

    for p in [tools_path, gt_path, opt_path]:
        if not p.exists():
            logger.error(f"File not found: {p}")
            return

    tool_descriptions = await load_tools(tools_path)
    relevant_queries = await load_ground_truth(gt_path)
    optimized_descriptions = await load_optimized(opt_path)
    search_descriptions = await load_search_descriptions(opt_path)

    logger.info(
        f"Loaded {len(tool_descriptions)} tools, "
        f"{sum(len(v) for v in relevant_queries.values())} GT queries, "
        f"{len(optimized_descriptions)} optimized descriptions, "
        f"{len(search_descriptions)} search descriptions"
    )

    from config import Settings
    from embedding.openai_embedder import OpenAIEmbedder

    settings = Settings()
    embedder = OpenAIEmbedder(api_key=settings.openai_api_key)

    # Condition A: 원본 description (Control)
    logger.info("=== Condition A: Original descriptions (Control) ===")
    scores_original = await compute_retrieval_scores(embedder, tool_descriptions, relevant_queries)

    # Condition B: search_description (Treatment A — PRIMARY)
    logger.info("=== Condition B: search_description (Treatment A — PRIMARY) ===")
    search_pool = dict(tool_descriptions)
    for tool_id, search_desc in search_descriptions.items():
        if tool_id in search_pool:
            search_pool[tool_id] = search_desc
    scores_search = await compute_retrieval_scores(embedder, search_pool, relevant_queries)

    # Condition C: optimized_description (Treatment B — secondary)
    logger.info("=== Condition C: optimized_description (Treatment B — secondary) ===")
    optimized_pool = dict(tool_descriptions)
    for tool_id, opt_desc in optimized_descriptions.items():
        if tool_id in optimized_pool:
            optimized_pool[tool_id] = opt_desc
    scores_optimized = await compute_retrieval_scores(embedder, optimized_pool, relevant_queries)

    # 3-way 비교 리포트
    shared_tools = (
        set(scores_original.keys()) & set(scores_search.keys()) & set(scores_optimized.keys())
    )

    def _aggregate(scores: dict[str, dict], tools: set[str]) -> tuple[float, float]:
        p1_vals = [scores[t]["p_at_1"] for t in tools]
        mrr_vals = [scores[t]["mrr"] for t in tools]
        return float(np.mean(p1_vals)), float(np.mean(mrr_vals))

    p1_orig, mrr_orig = _aggregate(scores_original, shared_tools)
    p1_search, mrr_search = _aggregate(scores_search, shared_tools)
    p1_opt, mrr_opt = _aggregate(scores_optimized, shared_tools)

    delta_search_p1 = p1_search - p1_orig
    delta_search_mrr = mrr_search - mrr_orig
    delta_opt_p1 = p1_opt - p1_orig
    delta_opt_mrr = mrr_opt - mrr_orig

    logger.info("=" * 60)
    logger.info("RETRIEVAL 3-WAY EVALUATION REPORT")
    logger.info("=" * 60)
    logger.info(f"Tools evaluated: {len(shared_tools)}")
    logger.info(f"Condition A (Original):           P@1={p1_orig:.4f}, MRR={mrr_orig:.4f}")
    logger.info(f"Condition B (search_description): P@1={p1_search:.4f}, MRR={mrr_search:.4f}")
    logger.info(f"Condition C (optimized_description): P@1={p1_opt:.4f}, MRR={mrr_opt:.4f}")
    logger.info(
        f"Delta B-A (Search vs Orig):    P@1={delta_search_p1:+.4f}, MRR={delta_search_mrr:+.4f}"
    )
    logger.info(f"Delta C-A (Optimized vs Orig): P@1={delta_opt_p1:+.4f}, MRR={delta_opt_mrr:+.4f}")

    # Per-tool 비교: Search vs Original
    search_improved = sum(
        1 for t in shared_tools if scores_search[t]["p_at_1"] > scores_original[t]["p_at_1"]
    )
    search_degraded = sum(
        1 for t in shared_tools if scores_search[t]["p_at_1"] < scores_original[t]["p_at_1"]
    )
    search_same = len(shared_tools) - search_improved - search_degraded
    logger.info(
        f"Search vs Orig per-tool: {search_improved} improved, "
        f"{search_degraded} degraded, {search_same} same"
    )

    # Per-tool 비교: Optimized vs Original
    opt_improved = sum(
        1 for t in shared_tools if scores_optimized[t]["p_at_1"] > scores_original[t]["p_at_1"]
    )
    opt_degraded = sum(
        1 for t in shared_tools if scores_optimized[t]["p_at_1"] < scores_original[t]["p_at_1"]
    )
    opt_same = len(shared_tools) - opt_improved - opt_degraded
    logger.info(
        f"Optimized vs Orig per-tool: {opt_improved} improved, "
        f"{opt_degraded} degraded, {opt_same} same"
    )

    # 결과 판정
    def _judge(label: str, delta: float) -> None:
        if delta >= 0.05:
            logger.info(f"RESULT [{label}]: IMPROVES retrieval (+5pp or more)")
        elif delta >= 0:
            logger.info(f"RESULT [{label}]: MARGINAL positive effect")
        else:
            logger.info(f"RESULT [{label}]: DEGRADES retrieval — investigate")

    _judge("Search", delta_search_p1)
    _judge("Optimized", delta_opt_p1)

    # 결과 JSON 저장
    output_path = (
        Path(args.output)
        if args.output
        else Path("data/verification/retrieval_3way_ab_report.json")
    )
    report = {
        "n_tools": len(shared_tools),
        "n_queries": sum(scores_original[t]["n_queries"] for t in shared_tools),
        "condition_a": {
            "name": "original",
            "p_at_1": p1_orig,
            "mrr": mrr_orig,
        },
        "condition_b": {
            "name": "search_description",
            "p_at_1": p1_search,
            "mrr": mrr_search,
        },
        "condition_c": {
            "name": "optimized_description",
            "p_at_1": p1_opt,
            "mrr": mrr_opt,
        },
        "delta_search_vs_orig": {
            "p_at_1": delta_search_p1,
            "mrr": delta_search_mrr,
        },
        "delta_optimized_vs_orig": {
            "p_at_1": delta_opt_p1,
            "mrr": delta_opt_mrr,
        },
        "per_tool_search_vs_orig": {
            "improved": search_improved,
            "degraded": search_degraded,
            "same": search_same,
        },
        "per_tool_optimized_vs_orig": {
            "improved": opt_improved,
            "degraded": opt_degraded,
            "same": opt_same,
        },
        "per_tool_details": {
            t: {
                "original_p1": scores_original[t]["p_at_1"],
                "search_p1": scores_search[t]["p_at_1"],
                "optimized_p1": scores_optimized[t]["p_at_1"],
                "delta_search_p1": scores_search[t]["p_at_1"] - scores_original[t]["p_at_1"],
                "delta_optimized_p1": scores_optimized[t]["p_at_1"] - scores_original[t]["p_at_1"],
                "original_mrr": scores_original[t]["mrr"],
                "search_mrr": scores_search[t]["mrr"],
                "optimized_mrr": scores_optimized[t]["mrr"],
                "n_queries": scores_original[t]["n_queries"],
            }
            for t in sorted(shared_tools)
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(f"Report saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieval A/B Evaluation")
    parser.add_argument("--tools", default="data/raw/servers.jsonl")
    parser.add_argument("--ground-truth", default="data/ground_truth/seed_set.jsonl")
    parser.add_argument(
        "--optimized",
        default="data/verification/grounded_optimization_results.jsonl",
    )
    parser.add_argument("--output", default=None, help="Report JSON output path")
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
