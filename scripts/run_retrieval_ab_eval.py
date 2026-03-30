"""Retrieval A/B Evaluation — retrieval text 비교 (원본 vs 최적화 description).

Description 최적화의 궁극적 검증: "최적화된 retrieval description이 실제 검색 성능을 높이는가?"

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
    """최적화된 retrieval description 로드 (성공 건만, legacy fallback 지원)."""
    optimized: dict[str, str] = {}
    with open(opt_path) as f:
        for line in f:
            entry = json.loads(line.strip())
            if entry.get("status") == "success":
                retrieval_text = (
                    entry.get("retrieval_description")
                    or entry.get("search_description")
                    or entry.get("optimized_description")
                )
                if retrieval_text:
                    optimized[entry["tool_id"]] = retrieval_text
    return optimized


async def compute_retrieval_scores(
    embedder: "Embedder",
    tool_descriptions: dict[str, str],
    relevant_queries: dict[str, list[str]],
    top_k: int,
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
        recall_at_k = sum(1 for r in ranks if r <= top_k) / len(ranks) if ranks else 0
        mrr = sum(1.0 / r for r in ranks) / len(ranks) if ranks else 0
        results[tool_id] = {
            "p_at_1": p_at_1,
            "recall_at_k": recall_at_k,
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

    from config import Settings
    from embedding.openai_embedder import OpenAIEmbedder

    settings = Settings()
    embedder = OpenAIEmbedder(api_key=settings.openai_api_key)

    # Condition A: 원본 description
    logger.info("=== Condition A: Original descriptions ===")
    scores_original = await compute_retrieval_scores(
        embedder, tool_descriptions, relevant_queries, top_k=args.top_k
    )

    # Condition B: 최적화 description
    logger.info("=== Condition B: Optimized descriptions ===")
    optimized_pool = dict(tool_descriptions)
    for tool_id, opt_desc in optimized_descriptions.items():
        if tool_id in optimized_pool:
            optimized_pool[tool_id] = opt_desc
    scores_optimized = await compute_retrieval_scores(
        embedder, optimized_pool, relevant_queries, top_k=args.top_k
    )

    # 비교 리포트
    shared_tools = set(scores_original.keys()) & set(scores_optimized.keys())
    p1_orig = [scores_original[t]["p_at_1"] for t in shared_tools]
    p1_opt = [scores_optimized[t]["p_at_1"] for t in shared_tools]
    recall_orig = [scores_original[t]["recall_at_k"] for t in shared_tools]
    recall_opt = [scores_optimized[t]["recall_at_k"] for t in shared_tools]
    mrr_orig = [scores_original[t]["mrr"] for t in shared_tools]
    mrr_opt = [scores_optimized[t]["mrr"] for t in shared_tools]

    logger.info("=" * 60)
    logger.info("RETRIEVAL A/B EVALUATION REPORT")
    logger.info("=" * 60)
    logger.info(f"Tools evaluated: {len(shared_tools)}")
    logger.info(
        f"Condition A (Original):  Recall@{args.top_k}={np.mean(recall_orig):.4f}, "
        f"MRR={np.mean(mrr_orig):.4f}, P@1={np.mean(p1_orig):.4f}"
    )
    logger.info(
        f"Condition B (Optimized): Recall@{args.top_k}={np.mean(recall_opt):.4f}, "
        f"MRR={np.mean(mrr_opt):.4f}, P@1={np.mean(p1_opt):.4f}"
    )

    delta_recall = np.mean(recall_opt) - np.mean(recall_orig)
    delta_p1 = np.mean(p1_opt) - np.mean(p1_orig)
    delta_mrr = np.mean(mrr_opt) - np.mean(mrr_orig)
    logger.info(f"Delta Recall@{args.top_k}: {delta_recall:+.4f}")
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

    if delta_recall > 0 and delta_mrr >= 0:
        logger.info("RESULT: Optimization IMPROVES retrieval on primary metrics")
    elif delta_recall >= 0 and delta_mrr >= 0:
        logger.info("RESULT: Optimization is neutral-to-positive on retrieval")
    else:
        logger.info("RESULT: Optimization DEGRADES retrieval — investigate")

    # 결과 JSON 저장
    output_path = (
        Path(args.output)
        if args.output
        else Path("data/verification/retrieval_ab_report.json")
    )
    report = {
        "n_tools": len(shared_tools),
        "n_queries": sum(scores_original[t]["n_queries"] for t in shared_tools),
        "k_used": args.top_k,
        "condition_a": {
            "name": "original",
            "recall_at_k": float(np.mean(recall_orig)),
            "p_at_1": float(np.mean(p1_orig)),
            "mrr": float(np.mean(mrr_orig)),
        },
        "condition_b": {
            "name": "retrieval_description",
            "recall_at_k": float(np.mean(recall_opt)),
            "p_at_1": float(np.mean(p1_opt)),
            "mrr": float(np.mean(mrr_opt)),
        },
        "delta_recall_at_k": float(delta_recall),
        "delta_p_at_1": float(delta_p1),
        "delta_mrr": float(delta_mrr),
        "per_tool_improved": improved,
        "per_tool_degraded": degraded,
        "per_tool_same": same,
        "per_tool_details": {
            t: {
                "original_p1": scores_original[t]["p_at_1"],
                "optimized_p1": scores_optimized[t]["p_at_1"],
                "original_recall_at_k": scores_original[t]["recall_at_k"],
                "optimized_recall_at_k": scores_optimized[t]["recall_at_k"],
                "delta_p1": scores_optimized[t]["p_at_1"] - scores_original[t]["p_at_1"],
                "original_mrr": scores_original[t]["mrr"],
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
    parser.add_argument("--top-k", type=int, default=10, help="Recall@K cutoff")
    parser.add_argument("--output", default=None, help="Report JSON output path")
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
