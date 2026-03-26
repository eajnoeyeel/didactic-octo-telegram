"""Evaluation harness: runs a pipeline strategy against ground truth queries."""

from __future__ import annotations

import time

from loguru import logger

from evaluation.metrics import (
    EvalResult,
    PerQueryResult,
    compute_confusion_rate,
    compute_ece,
    compute_latency_stats,
    compute_mrr,
    compute_ndcg_at_5,
    compute_precision_at_1,
    compute_recall_at_k,
)
from models import GroundTruthEntry
from pipeline.confidence import compute_confidence
from pipeline.strategy import PipelineStrategy


async def evaluate(
    strategy: PipelineStrategy,
    queries: list[GroundTruthEntry],
    top_k: int = 10,
    gap_threshold: float = 0.15,
) -> EvalResult:
    """Run strategy on all queries and compute all evaluation metrics.

    Args:
        strategy: Pipeline strategy to evaluate (FlatStrategy, SequentialStrategy, …).
        queries: Ground truth entries to evaluate against.
        top_k: Number of results to retrieve per query (also K for Recall@K).
        gap_threshold: Confidence gap threshold passed to compute_confidence().

    Returns:
        EvalResult with all 7 metrics computed over the full query set.
    """
    strategy_name = type(strategy).__name__
    logger.info(f"evaluate: strategy={strategy_name}, n_queries={len(queries)}, top_k={top_k}")

    per_query: list[PerQueryResult] = []
    ndcg_scores: list[float] = []
    confidences: list[float] = []
    correct_flags: list[bool] = []
    latencies_ms: list[float] = []

    for entry in queries:
        t_start = time.perf_counter()
        results = await strategy.search(entry.query, top_k=top_k)
        latency_ms = (time.perf_counter() - t_start) * 1000.0

        confidence, _ = compute_confidence(results, gap_threshold)
        retrieved_ids = [r.tool.tool_id for r in results]

        top_1_correct = bool(results and results[0].tool.tool_id == entry.correct_tool_id)
        in_top_k = entry.correct_tool_id in retrieved_ids

        rank_of_correct: int | None = None
        for i, r in enumerate(results):
            if r.tool.tool_id == entry.correct_tool_id:
                rank_of_correct = i + 1
                break

        per_query.append(
            PerQueryResult(
                query_id=entry.query_id,
                top_1_correct=top_1_correct,
                in_top_k=in_top_k,
                rank_of_correct=rank_of_correct,
                confidence=confidence,
                latency_ms=latency_ms,
                retrieved_tool_ids=retrieved_ids,
            )
        )
        ndcg_scores.append(compute_ndcg_at_5(results, entry))
        confidences.append(confidence)
        correct_flags.append(top_1_correct)
        latencies_ms.append(latency_ms)

    p50, p95, p99, mean_lat = compute_latency_stats(latencies_ms)
    result = EvalResult(
        strategy_name=strategy_name,
        n_queries=len(queries),
        k_used=top_k,
        precision_at_1=compute_precision_at_1(per_query),
        recall_at_k=compute_recall_at_k(per_query),
        mrr=compute_mrr(per_query),
        ndcg_at_5=sum(ndcg_scores) / len(ndcg_scores) if ndcg_scores else 0.0,
        confusion_rate=compute_confusion_rate(per_query),
        ece=compute_ece(confidences, correct_flags),
        latency_p50=p50,
        latency_p95=p95,
        latency_p99=p99,
        latency_mean=mean_lat,
        per_query=per_query,
    )
    logger.info(
        f"evaluate done: P@1={result.precision_at_1:.3f}, "
        f"R@{top_k}={result.recall_at_k:.3f}, MRR={result.mrr:.3f}, "
        f"NDCG@5={result.ndcg_at_5:.3f}, ECE={result.ece:.3f}"
    )
    return result
