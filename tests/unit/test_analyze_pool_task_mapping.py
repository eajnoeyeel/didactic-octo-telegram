"""Tests for pool-task mapping analysis."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from analyze_pool_task_mapping import (
    aggregate_server_stats,
    bucket_label,
    format_report,
    score_task,
)


class TestScoreTask:
    def test_fully_covered(self) -> None:
        calls = [
            {"name": "github_search_repositories"},
            {"name": "slack_post_message"},
        ]
        pool = {"github", "slack"}
        result = score_task(calls, pool)
        assert result["pool_ratio"] == 1.0
        assert result["pool_calls"] == 2
        assert result["total_calls"] == 2
        assert set(result["pool_servers"]) == {"github", "slack"}
        assert result["non_pool_servers"] == []

    def test_partially_covered(self) -> None:
        calls = [
            {"name": "github_search_repositories"},
            {"name": "brave-search_brave_web_search"},
        ]
        pool = {"github"}
        result = score_task(calls, pool)
        assert result["pool_ratio"] == 0.5
        assert result["pool_calls"] == 1
        assert result["non_pool_servers"] == ["brave-search"]

    def test_no_coverage(self) -> None:
        calls = [{"name": "brave-search_brave_web_search"}]
        pool = {"github"}
        result = score_task(calls, pool)
        assert result["pool_ratio"] == 0.0
        assert result["pool_calls"] == 0

    def test_empty_calls(self) -> None:
        result = score_task([], {"github"})
        assert result["pool_ratio"] == 0.0
        assert result["total_calls"] == 0

    def test_hyphenated_server(self) -> None:
        calls = [{"name": "cli-mcp-server_run_command"}]
        pool = {"cli-mcp-server"}
        result = score_task(calls, pool)
        assert result["pool_ratio"] == 1.0
        assert result["pool_servers"] == ["cli-mcp-server"]

    def test_multiple_calls_same_server(self) -> None:
        calls = [
            {"name": "github_search_repositories"},
            {"name": "github_create_issue"},
            {"name": "slack_post_message"},
        ]
        pool = {"github", "slack"}
        result = score_task(calls, pool)
        assert result["pool_calls"] == 3
        assert result["total_calls"] == 3
        assert result["pool_ratio"] == 1.0
        assert set(result["pool_servers"]) == {"github", "slack"}

    def test_servers_are_sorted(self) -> None:
        calls = [
            {"name": "slack_post_message"},
            {"name": "github_search_repositories"},
            {"name": "brave-search_brave_web_search"},
        ]
        pool = {"github", "slack"}
        result = score_task(calls, pool)
        assert result["pool_servers"] == ["github", "slack"]
        assert result["non_pool_servers"] == ["brave-search"]


class TestBucketLabel:
    def test_full_coverage(self) -> None:
        assert bucket_label(1.0) == "100%"

    def test_high_partial(self) -> None:
        assert bucket_label(0.75) == "50-99%"

    def test_low_partial(self) -> None:
        assert bucket_label(0.25) == "1-49%"

    def test_boundary_50(self) -> None:
        assert bucket_label(0.50) == "50-99%"

    def test_boundary_01(self) -> None:
        assert bucket_label(0.01) == "1-49%"

    def test_zero(self) -> None:
        assert bucket_label(0.0) == "0%"


class TestAggregateServerStats:
    def test_basic_aggregation(self) -> None:
        task_scores = [
            {
                "pool_servers": ["github"],
                "non_pool_servers": ["brave-search"],
                "_calls": [
                    {"name": "github_search_repositories"},
                    {"name": "brave-search_brave_web_search"},
                ],
                "pool_calls": 1,
                "total_calls": 2,
                "pool_ratio": 0.5,
            },
            {
                "pool_servers": ["github", "slack"],
                "non_pool_servers": [],
                "_calls": [
                    {"name": "github_create_issue"},
                    {"name": "slack_post_message"},
                ],
                "pool_calls": 2,
                "total_calls": 2,
                "pool_ratio": 1.0,
            },
        ]
        pool_stats, non_pool_stats = aggregate_server_stats(task_scores)
        assert pool_stats["github"]["task_count"] == 2
        assert pool_stats["github"]["call_count"] == 2
        assert pool_stats["slack"]["task_count"] == 1
        assert pool_stats["slack"]["call_count"] == 1
        assert non_pool_stats["brave-search"]["task_count"] == 1
        assert non_pool_stats["brave-search"]["call_count"] == 1

    def test_empty_input(self) -> None:
        pool_stats, non_pool_stats = aggregate_server_stats([])
        assert pool_stats == {}
        assert non_pool_stats == {}


class TestFormatReport:
    def test_contains_sections(self) -> None:
        task_scores = [
            {
                "pool_calls": 2,
                "total_calls": 2,
                "pool_ratio": 1.0,
                "pool_servers": ["github"],
                "non_pool_servers": [],
                "_calls": [
                    {"name": "github_search_repositories"},
                    {"name": "github_create_issue"},
                ],
            },
        ]
        pool_stats = {"github": {"task_count": 1, "call_count": 2}}
        non_pool_stats: dict[str, dict[str, int]] = {}
        report = format_report(task_scores, pool_stats, non_pool_stats)

        assert "POOL-TASK MAPPING ANALYSIS" in report
        assert "Total tasks analyzed: 1" in report
        assert "100%" in report
        assert "github" in report
        assert "Recommended task selection summary" in report

    def test_empty_tasks(self) -> None:
        report = format_report([], {}, {})
        assert "Total tasks analyzed: 0" in report
