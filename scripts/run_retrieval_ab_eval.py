"""Retrieval A/B Evaluation — P@1 비교 (원본 vs 최적화 description).

Description 최적화의 궁극적 검증: "최적화된 description이 실제로 도구 선택 정확도를 높이는가?"

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
            server_id = server.get("qualifiedName", server.get("name", ""))
            for tool in server.get("tools", []):
                tool_name = tool.get("name", "")
                tool_id = f"{server_id}::{tool_name}"
                desc = tool.get("description", "")
                if desc:
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

    logger.info(
        f"Loaded {len(tool_descriptions)} tools, "
        f"{sum(len(v) for v in relevant_queries.values())} GT queries, "
        f"{len(optimized_descriptions)} optimized descriptions"
    )

    from embedding.openai_embedder import OpenAIEmbedder

    embedder = OpenAIEmbedder()

    # Condition A: 원본 description
    logger.info("=== Condition A: Original descriptions ===")
    scores_original = await compute_retrieval_scores(embedder, tool_descriptions, relevant_queries)

    # Condition B: 최적화 description
    logger.info("=== Condition B: Optimized descriptions ===")
    optimized_pool = dict(tool_descriptions)
    for tool_id, opt_desc in optimized_descriptions.items():
        if tool_id in optimized_pool:
            optimized_pool[tool_id] = opt_desc
    scores_optimized = await compute_retrieval_scores(embedder, optimized_pool, relevant_queries)

    # 비교 리포트
    shared_tools = set(scores_original.keys()) & set(scores_optimized.keys())
    p1_orig = [scores_original[t]["p_at_1"] for t in shared_tools]
    p1_opt = [scores_optimized[t]["p_at_1"] for t in shared_tools]
    mrr_orig = [scores_original[t]["mrr"] for t in shared_tools]
    mrr_opt = [scores_optimized[t]["mrr"] for t in shared_tools]

    logger.info("=" * 60)
    logger.info("RETRIEVAL A/B EVALUATION REPORT")
    logger.info("=" * 60)
    logger.info(f"Tools evaluated: {len(shared_tools)}")
    logger.info(f"Condition A (Original):  P@1={np.mean(p1_orig):.4f}, MRR={np.mean(mrr_orig):.4f}")
    logger.info(f"Condition B (Optimized): P@1={np.mean(p1_opt):.4f}, MRR={np.mean(mrr_opt):.4f}")

    delta_p1 = np.mean(p1_opt) - np.mean(p1_orig)
    delta_mrr = np.mean(mrr_opt) - np.mean(mrr_orig)
    logger.info(f"Delta P@1: {delta_p1:+.4f}")
    logger.info(f"Delta MRR: {delta_mrr:+.4f}")

    # Per-tool 비교
    improved = sum(
        1 for t in shared_tools if scores_optimized[t]["p_at_1"] > scores_original[t]["p_at_1"]
    )
    degraded = sum(
        1 for t in shared_tools if scores_optimized[t]["p_at_1"] < scores_original[t]["p_at_1"]
    )
    same = len(shared_tools) - improved - degraded
    logger.info(f"Per-tool: {improved} improved, {degraded} degraded, {same} same")

    if delta_p1 >= 0.05:
        logger.info("RESULT: Optimization IMPROVES retrieval (+5pp or more)")
    elif delta_p1 >= 0:
        logger.info("RESULT: Optimization has MARGINAL positive effect")
    else:
        logger.info("RESULT: Optimization DEGRADES retrieval — investigate")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieval A/B Evaluation")
    parser.add_argument("--tools", default="data/raw/servers.jsonl")
    parser.add_argument("--ground-truth", default="data/ground_truth/seed_set.jsonl")
    parser.add_argument(
        "--optimized",
        default="data/verification/grounded_optimization_results.jsonl",
    )
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
