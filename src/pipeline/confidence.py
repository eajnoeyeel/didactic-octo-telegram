"""Gap-based confidence branching for retrieval results."""

from models import SearchResult


def compute_confidence(
    results: list[SearchResult],
    gap_threshold: float = 0.15,
) -> tuple[float, bool]:
    """Compute confidence score and disambiguation flag from ranked results.

    Uses the score gap between rank-1 and rank-2 to determine confidence.
    A small gap means the top two results are close — the LLM may need to
    ask for clarification (disambiguation_needed=True).

    Args:
        results: Ranked SearchResults, highest score first.
        gap_threshold: Minimum gap for a clear winner. Default 0.15 (from config).

    Returns:
        (confidence, needs_disambiguation):
            confidence: Score of the top result (0.0 if no results).
            needs_disambiguation: True if gap < threshold or no results.
    """
    if not results:
        return 0.0, True

    confidence = results[0].score

    if len(results) == 1:
        return confidence, False

    gap = results[0].score - results[1].score
    needs_disambiguation = gap < gap_threshold
    return confidence, needs_disambiguation
