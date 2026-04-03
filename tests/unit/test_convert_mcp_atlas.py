"""Tests for scripts/convert_mcp_atlas.py — MCP-Atlas per-step GT decomposition (ADR-0012)."""

import json
import sys
from pathlib import Path

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import pytest
from convert_mcp_atlas import (
    BOILERPLATE_BLOCKLIST,
    build_ground_truth_entry,
    extract_substantive_steps,
    filter_steps_to_pool,
    is_boilerplate,
    parse_trajectory,
    score_task_pool_coverage,
    select_tasks_by_pool_coverage,
    split_tool_name,
)

from src.models import TOOL_ID_SEPARATOR

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_trajectory() -> list[dict]:
    """3 tool calls: github_search_repositories, github_get_repository, fetch_fetch."""
    return [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "github_search_repositories",
                        "arguments": '{"query": "machine learning"}',
                    },
                    "id": "call_001",
                    "type": "function",
                },
            ],
        },
        {"role": "tool", "content": '{"items": []}', "name": None},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "github_get_repository",
                        "arguments": '{"owner": "org", "repo": "ml-lib"}',
                    },
                    "id": "call_002",
                    "type": "function",
                },
            ],
        },
        {"role": "tool", "content": '{"full_name": "org/ml-lib"}', "name": None},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "fetch_fetch",
                        "arguments": '{"url": "https://example.com"}',
                    },
                    "id": "call_003",
                    "type": "function",
                },
            ],
        },
        {"role": "tool", "content": "page content", "name": None},
    ]


@pytest.fixture()
def trajectory_with_boilerplate() -> list[dict]:
    """2 boilerplate + 1 substantive tool call."""
    return [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "filesystem_list_allowed_directories",
                        "arguments": "{}",
                    },
                    "id": "call_bp1",
                    "type": "function",
                },
            ],
        },
        {"role": "tool", "content": "['/home']", "name": None},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "desktop-commander_get_config",
                        "arguments": "{}",
                    },
                    "id": "call_bp2",
                    "type": "function",
                },
            ],
        },
        {"role": "tool", "content": "{}", "name": None},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "github_search_repositories",
                        "arguments": '{"query": "test"}',
                    },
                    "id": "call_sub",
                    "type": "function",
                },
            ],
        },
        {"role": "tool", "content": '{"items": []}', "name": None},
    ]


# ===========================================================================
# TestSplitToolName
# ===========================================================================


class TestSplitToolName:
    """Test MCP-Atlas tool name → (server_id, tool_name) splitting."""

    def test_simple_server(self):
        """'github_search_repositories' → ('github', 'search_repositories')."""
        server_id, tool_name = split_tool_name("github_search_repositories")
        assert server_id == "github"
        assert tool_name == "search_repositories"

    def test_hyphenated_server(self):
        """'brave-search_brave_web_search' → ('brave-search', 'brave_web_search')."""
        server_id, tool_name = split_tool_name("brave-search_brave_web_search")
        assert server_id == "brave-search"
        assert tool_name == "brave_web_search"

    def test_multi_hyphen_server(self):
        """'cli-mcp-server_show_security_rules' → ('cli-mcp-server', 'show_security_rules')."""
        server_id, tool_name = split_tool_name("cli-mcp-server_show_security_rules")
        assert server_id == "cli-mcp-server"
        assert tool_name == "show_security_rules"

    def test_single_word_tool(self):
        """'fetch_fetch' → ('fetch', 'fetch')."""
        server_id, tool_name = split_tool_name("fetch_fetch")
        assert server_id == "fetch"
        assert tool_name == "fetch"

    def test_unknown_format_best_effort(self):
        """Single word without underscore → (word, '')."""
        server_id, tool_name = split_tool_name("sometool")
        assert server_id == "sometool"
        assert tool_name == ""


# ===========================================================================
# TestIsBoilerplate
# ===========================================================================


class TestIsBoilerplate:
    """Test boilerplate blocklist detection."""

    def test_known_boilerplate_filesystem(self):
        assert is_boilerplate("filesystem_list_allowed_directories") is True

    def test_known_boilerplate_cli(self):
        assert is_boilerplate("cli-mcp-server_show_security_rules") is True

    def test_known_boilerplate_desktop(self):
        assert is_boilerplate("desktop-commander_get_config") is True

    def test_substantive_tool(self):
        assert is_boilerplate("github_search_repositories") is False

    def test_blocklist_has_known_items(self):
        """Blocklist contains all documented boilerplate items."""
        expected = {
            "filesystem_list_allowed_directories",
            "cli-mcp-server_show_security_rules",
            "desktop-commander_get_config",
            "memory_list_memories",
        }
        assert expected.issubset(BOILERPLATE_BLOCKLIST)


# ===========================================================================
# TestParseTrajectory
# ===========================================================================


class TestParseTrajectory:
    """Test TRAJECTORY JSON → tool call list extraction."""

    def test_extracts_tool_calls(self, sample_trajectory):
        """Should extract 3 tool calls from sample trajectory."""
        calls = parse_trajectory(sample_trajectory)
        assert len(calls) == 3
        assert calls[0]["name"] == "github_search_repositories"
        assert calls[1]["name"] == "github_get_repository"
        assert calls[2]["name"] == "fetch_fetch"

    def test_preserves_arguments(self, sample_trajectory):
        """Arguments string is preserved in output."""
        calls = parse_trajectory(sample_trajectory)
        assert calls[0]["arguments"] == '{"query": "machine learning"}'

    def test_empty_trajectory(self):
        """Empty trajectory → empty list."""
        assert parse_trajectory([]) == []


# ===========================================================================
# TestExtractSubstantiveSteps
# ===========================================================================


class TestExtractSubstantiveSteps:
    """Test boilerplate filtering from tool calls."""

    def test_filters_boilerplate(self, trajectory_with_boilerplate):
        """Should filter 2 boilerplate, keep 1 substantive."""
        calls = parse_trajectory(trajectory_with_boilerplate)
        substantive = extract_substantive_steps(calls)
        assert len(substantive) == 1
        assert substantive[0]["name"] == "github_search_repositories"

    def test_all_substantive(self, sample_trajectory):
        """No boilerplate → all calls retained."""
        calls = parse_trajectory(sample_trajectory)
        substantive = extract_substantive_steps(calls)
        assert len(substantive) == 3


# ===========================================================================
# TestBuildGroundTruthEntry
# ===========================================================================


class TestBuildGroundTruthEntry:
    """Test GT entry construction with ADR-0012 fields."""

    def test_basic_entry(self):
        """All required fields are populated correctly."""
        entry = build_ground_truth_entry(
            task_id="task-abc-123",
            task_index=5,
            step_index=2,
            tool_call_name="github_search_repositories",
            query="Find ML repos on GitHub",
            prompt="Search for machine learning repositories",
        )

        assert entry["query_id"] == "gt-atlas-005-s02"
        assert entry["query"] == "Find ML repos on GitHub"
        assert entry["correct_server_id"] == "github"
        assert entry["correct_tool_id"] == f"github{TOOL_ID_SEPARATOR}search_repositories"
        assert entry["source"] == "external_mcp_atlas"
        assert entry["manually_verified"] is True
        assert entry["task_type"] == "single_step"
        assert entry["origin_task_id"] == "task-abc-123"
        assert entry["step_index"] == 2

    def test_query_id_format(self):
        """query_id follows 'gt-atlas-{task_index:03d}-s{step_index:02d}' format."""
        entry = build_ground_truth_entry(
            task_id="task-xyz",
            task_index=42,
            step_index=7,
            tool_call_name="brave-search_brave_web_search",
            query="Search the web",
            prompt="Use brave search",
        )

        assert entry["query_id"] == "gt-atlas-042-s07"
        assert entry["correct_server_id"] == "brave-search"
        assert entry["correct_tool_id"] == f"brave-search{TOOL_ID_SEPARATOR}brave_web_search"


class TestProcessTasksWithPoolFilter:
    """ADR-0012 pool filter: only pool-resident servers included in GT."""

    def test_steps_outside_pool_filtered_out(self) -> None:
        allowed = frozenset({"github"})
        tool_calls = [
            {"name": "github_search_repositories", "arguments": "{}"},
            {"name": "brave-search_brave_web_search", "arguments": "{}"},
        ]
        filtered = [tc for tc in tool_calls if split_tool_name(tc["name"])[0] in allowed]
        assert len(filtered) == 1
        assert filtered[0]["name"] == "github_search_repositories"

    def test_none_allowed_servers_includes_all(self) -> None:
        tool_calls = [
            {"name": "github_search_repositories"},
            {"name": "brave-search_brave_web_search"},
        ]
        allowed: frozenset[str] | None = None
        result = (
            tool_calls
            if allowed is None
            else [tc for tc in tool_calls if split_tool_name(tc["name"])[0] in allowed]
        )
        assert len(result) == 2

    def test_all_steps_filtered_yields_empty(self) -> None:
        allowed = frozenset({"github"})
        tool_calls = [
            {"name": "brave-search_brave_web_search"},
            {"name": "notion_create_page"},
        ]
        filtered = [tc for tc in tool_calls if split_tool_name(tc["name"])[0] in allowed]
        assert len(filtered) == 0

    def test_load_pool_file_returns_frozenset(self, tmp_path: Path) -> None:
        pool_file = tmp_path / "pool.jsonl"
        pool_file.write_text(
            json.dumps({"server_id": "github", "tools": []})
            + "\n"
            + json.dumps({"server_id": "arxiv", "tools": []})
            + "\n"
        )
        ids: set[str] = set()
        for line in pool_file.read_text().splitlines():
            if line.strip():
                ids.add(json.loads(line)["server_id"])
        allowed = frozenset(ids)
        assert allowed == frozenset({"github", "arxiv"})


# ===========================================================================
# TestFilterStepsToPool
# ===========================================================================


class TestFilterStepsToPool:
    """Tests for pool-based step filtering."""

    def test_filters_to_pool_servers(self):
        steps = [
            {"name": "github_search_repositories", "arguments": "{}", "call_index": 0},
            {"name": "brave-search_brave_web_search", "arguments": "{}", "call_index": 1},
            {"name": "slack_post_message", "arguments": "{}", "call_index": 2},
        ]
        pool = {"github", "slack"}
        result = filter_steps_to_pool(steps, pool)
        assert len(result) == 2
        assert result[0]["name"] == "github_search_repositories"
        assert result[1]["name"] == "slack_post_message"

    def test_empty_when_no_match(self):
        steps = [{"name": "brave-search_brave_web_search", "arguments": "{}", "call_index": 0}]
        assert filter_steps_to_pool(steps, {"github"}) == []

    def test_empty_steps_returns_empty(self):
        assert filter_steps_to_pool([], {"github"}) == []


# ===========================================================================
# TestScoreTaskPoolCoverage
# ===========================================================================


class TestScoreTaskPoolCoverage:
    """Tests for task pool coverage scoring."""

    def test_fully_covered(self):
        steps = [
            {"name": "github_search_repositories"},
            {"name": "slack_post_message"},
        ]
        result = score_task_pool_coverage(steps, {"github", "slack"})
        assert result["pool_ratio"] == 1.0
        assert result["pool_calls"] == 2
        assert result["total_calls"] == 2
        assert result["pool_servers"] == {"github", "slack"}

    def test_partially_covered(self):
        steps = [
            {"name": "github_search_repositories"},
            {"name": "brave-search_brave_web_search"},
        ]
        result = score_task_pool_coverage(steps, {"github"})
        assert result["pool_ratio"] == 0.5
        assert result["pool_calls"] == 1

    def test_no_coverage(self):
        steps = [{"name": "brave-search_brave_web_search"}]
        result = score_task_pool_coverage(steps, {"github"})
        assert result["pool_ratio"] == 0.0

    def test_empty_steps(self):
        result = score_task_pool_coverage([], {"github"})
        assert result["pool_ratio"] == 0.0


# ===========================================================================
# TestSelectTasksByPoolCoverage
# ===========================================================================


class TestSelectTasksByPoolCoverage:
    """Tests for pool-aware task selection."""

    def test_prefers_high_pool_ratio(self):
        scored = [
            (
                {"id": "a"},
                {"pool_ratio": 0.5, "pool_calls": 1, "total_calls": 2, "pool_servers": {"github"}},
            ),
            (
                {"id": "b"},
                {
                    "pool_ratio": 1.0,
                    "pool_calls": 3,
                    "total_calls": 3,
                    "pool_servers": {"github", "slack"},
                },
            ),
            (
                {"id": "c"},
                {"pool_ratio": 0.0, "pool_calls": 0, "total_calls": 3, "pool_servers": set()},
            ),
        ]
        selected = select_tasks_by_pool_coverage(scored, max_tasks=2)
        assert len(selected) == 2
        assert selected[0][0]["id"] == "b"  # highest ratio first
        assert selected[1][0]["id"] == "a"

    def test_excludes_zero_pool(self):
        scored = [
            (
                {"id": "a"},
                {"pool_ratio": 0.0, "pool_calls": 0, "total_calls": 3, "pool_servers": set()},
            ),
        ]
        assert select_tasks_by_pool_coverage(scored, max_tasks=10) == []

    def test_respects_max_tasks(self):
        scored = [
            (
                {"id": f"t{i}"},
                {"pool_ratio": 1.0, "pool_calls": 2, "total_calls": 2, "pool_servers": {"github"}},
            )
            for i in range(10)
        ]
        assert len(select_tasks_by_pool_coverage(scored, max_tasks=3)) == 3
