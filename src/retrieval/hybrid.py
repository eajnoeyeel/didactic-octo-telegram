"""Reciprocal Rank Fusion for hybrid search result merging."""

from __future__ import annotations

from models import SearchResult


def rrf_score(rank: int, k: int = 60) -> float:
    """RRF score: 1 / (k + rank). k=60 is the Cormack et al. standard."""
    return 1.0 / (k + rank)


def merge_results(
    *result_lists: list[SearchResult],
    k: int = 60,
    top_n: int = 10,
) -> list[SearchResult]:
    """Merge ranked lists via RRF. Sums scores per tool_id, returns top_n."""
    fused: dict[str, float] = {}
    best: dict[str, SearchResult] = {}

    for result_list in result_lists:
        for r in result_list:
            tid = r.tool.tool_id
            fused[tid] = fused.get(tid, 0.0) + rrf_score(r.rank, k)
            if tid not in best or r.score > best[tid].score:
                best[tid] = r

    sorted_ids = sorted(fused, key=lambda tid: fused[tid], reverse=True)[:top_n]

    return [
        SearchResult(
            tool=best[tid].tool,
            score=fused[tid],
            rank=rank,
            reason=best[tid].reason,
        )
        for rank, tid in enumerate(sorted_ids, start=1)
    ]
