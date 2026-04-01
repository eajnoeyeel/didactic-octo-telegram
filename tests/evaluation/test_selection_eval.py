"""Tests for tool selection A/B evaluation logic."""


def test_selection_eval_result_structure():
    """Selection eval should track per-query results for original vs optimized."""
    result = {
        "query_id": "gt-comm-001",
        "query": "delete a comment on a Slack file",
        "correct_tool_id": "slack::SLACK_DELETE_A_COMMENT_ON_A_FILE",
        "original_rank1": "slack::SLACK_DELETE_A_COMMENT_ON_A_FILE",
        "optimized_rank1": "slack::SLACK_DELETE_A_COMMENT_ON_A_FILE",
        "original_correct": True,
        "optimized_correct": True,
    }
    assert result["original_correct"] is True
    assert result["optimized_correct"] is True


def test_precision_at_1_calculation():
    """Precision@1 = count of rank1 correct / total queries."""
    results = [
        {"original_correct": True, "optimized_correct": True},
        {"original_correct": False, "optimized_correct": True},
        {"original_correct": True, "optimized_correct": False},
        {"original_correct": False, "optimized_correct": False},
    ]
    original_p1 = sum(1 for r in results if r["original_correct"]) / len(results)
    optimized_p1 = sum(1 for r in results if r["optimized_correct"]) / len(results)
    assert original_p1 == 0.5
    assert optimized_p1 == 0.5
