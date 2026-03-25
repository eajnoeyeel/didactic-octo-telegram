"""Tests for data models."""

import pytest

from models import (
    TOOL_ID_SEPARATOR,
    Ambiguity,
    Category,
    Difficulty,
    FindBestToolRequest,
    FindBestToolResponse,
    GroundTruthEntry,
    MCPServer,
    MCPServerSummary,
    MCPTool,
    SearchResult,
)


class TestToolIdSeparator:
    def test_separator_is_double_colon(self):
        assert TOOL_ID_SEPARATOR == "::"


class TestMCPServerSummary:
    def test_create_with_defaults(self):
        summary = MCPServerSummary(
            qualified_name="@smithery-ai/github",
            display_name="GitHub MCP",
        )
        assert summary.qualified_name == "@smithery-ai/github"
        assert summary.display_name == "GitHub MCP"
        assert summary.description is None
        assert summary.use_count == 0
        assert summary.is_verified is False
        assert summary.is_deployed is False

    def test_create_full(self):
        summary = MCPServerSummary(
            qualified_name="@smithery-ai/github",
            display_name="GitHub MCP",
            description="GitHub integration",
            use_count=1500,
            is_verified=True,
            is_deployed=True,
        )
        assert summary.use_count == 1500
        assert summary.is_verified is True


class TestMCPServer:
    def test_create_with_defaults(self):
        server = MCPServer(server_id="@smithery-ai/github", name="GitHub MCP")
        assert server.server_id == "@smithery-ai/github"
        assert server.name == "GitHub MCP"
        assert server.description is None
        assert server.homepage is None
        assert server.tools == []

    def test_create_with_tools(self):
        tool = MCPTool(
            server_id="@smithery-ai/github",
            tool_name="search_issues",
            tool_id="@smithery-ai/github::search_issues",
            description="Search GitHub issues",
        )
        server = MCPServer(
            server_id="@smithery-ai/github",
            name="GitHub MCP",
            tools=[tool],
        )
        assert len(server.tools) == 1
        assert server.tools[0].tool_name == "search_issues"


class TestMCPTool:
    def test_create_valid(self):
        tool = MCPTool(
            server_id="@smithery-ai/github",
            tool_name="search_issues",
            tool_id="@smithery-ai/github::search_issues",
            description="Search GitHub issues",
        )
        assert tool.tool_id == "@smithery-ai/github::search_issues"
        assert tool.server_id == "@smithery-ai/github"
        assert tool.tool_name == "search_issues"

    def test_tool_id_validator_rejects_wrong_format(self):
        with pytest.raises(ValueError, match="tool_id must be"):
            MCPTool(
                server_id="@smithery-ai/github",
                tool_name="search_issues",
                tool_id="wrong-format",
            )

    def test_tool_id_validator_rejects_slash_separator(self):
        with pytest.raises(ValueError, match="tool_id must be"):
            MCPTool(
                server_id="@smithery-ai/github",
                tool_name="search_issues",
                tool_id="@smithery-ai/github/search_issues",
            )

    def test_parameter_names_from_input_schema(self):
        tool = MCPTool(
            server_id="srv",
            tool_name="t",
            tool_id="srv::t",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        )
        assert tool.parameter_names == ["query", "limit"]

    def test_parameter_names_empty_when_no_schema(self):
        tool = MCPTool(
            server_id="srv",
            tool_name="t",
            tool_id="srv::t",
        )
        assert tool.parameter_names == []

    def test_parameter_names_empty_when_no_properties(self):
        tool = MCPTool(
            server_id="srv",
            tool_name="t",
            tool_id="srv::t",
            input_schema={"type": "object"},
        )
        assert tool.parameter_names == []


class TestSearchResult:
    def test_create(self):
        tool = MCPTool(
            server_id="srv",
            tool_name="t",
            tool_id="srv::t",
        )
        result = SearchResult(tool=tool, score=0.95, rank=1)
        assert result.score == 0.95
        assert result.rank == 1
        assert result.reason is None


class TestFindBestToolRequest:
    def test_defaults(self):
        req = FindBestToolRequest(query="send email")
        assert req.top_k == 3
        assert req.strategy == "sequential"


class TestFindBestToolResponse:
    def test_create(self):
        resp = FindBestToolResponse(
            query="send email",
            results=[],
            confidence=0.85,
            disambiguation_needed=False,
            strategy_used="sequential",
            latency_ms=120.5,
        )
        assert resp.confidence == 0.85


class TestGroundTruthEntryFull:
    """Tests for the full Phase 4 GroundTruthEntry schema."""

    def _base(self, **overrides) -> dict:
        """Minimal valid entry — override individual fields per test."""
        base = {
            "query_id": "gt-gen-001",
            "query": "add two numbers",
            "correct_server_id": "EthanHenrickson/math-mcp",
            "correct_tool_id": "EthanHenrickson/math-mcp::add",
            "difficulty": "easy",
            "category": "general",
            "ambiguity": "low",
            "source": "manual_seed",
            "manually_verified": True,
            "author": "test",
            "created_at": "2026-03-24",
        }
        base.update(overrides)
        return base

    def test_create_valid_entry(self):
        gt = GroundTruthEntry(**self._base())
        assert gt.query_id == "gt-gen-001"
        assert gt.difficulty == Difficulty.EASY
        assert gt.category == Category.GENERAL
        assert gt.ambiguity == Ambiguity.LOW
        assert gt.alternative_tools is None
        assert gt.notes is None

    def test_difficulty_enum_values(self):
        for val in ("easy", "medium"):
            gt = GroundTruthEntry(**self._base(difficulty=val))
            assert gt.difficulty.value == val
        # hard requires non-low ambiguity
        gt = GroundTruthEntry(
            **self._base(
                difficulty="hard",
                ambiguity="medium",
                alternative_tools=["EthanHenrickson/math-mcp::subtract"],
            )
        )
        assert gt.difficulty.value == "hard"

    def test_category_enum_values(self):
        for cat in (
            "search",
            "code",
            "database",
            "communication",
            "productivity",
            "science",
            "finance",
            "general",
        ):
            gt = GroundTruthEntry(**self._base(category=cat))
            assert gt.category.value == cat

    def test_hard_difficulty_requires_non_low_ambiguity(self):
        with pytest.raises(ValueError, match="hard difficulty"):
            GroundTruthEntry(**self._base(difficulty="hard", ambiguity="low"))

    def test_hard_with_medium_ambiguity_is_valid(self):
        gt = GroundTruthEntry(
            **self._base(
                difficulty="hard",
                ambiguity="medium",
                alternative_tools=["EthanHenrickson/math-mcp::subtract"],
            )
        )
        assert gt.difficulty == Difficulty.HARD

    def test_medium_ambiguity_requires_alternative_tools(self):
        with pytest.raises(ValueError, match="alternative_tools"):
            GroundTruthEntry(**self._base(ambiguity="medium"))

    def test_high_ambiguity_requires_alternative_tools(self):
        with pytest.raises(ValueError, match="alternative_tools"):
            GroundTruthEntry(**self._base(ambiguity="high"))

    def test_medium_ambiguity_with_alternatives_is_valid(self):
        gt = GroundTruthEntry(
            **self._base(
                ambiguity="medium",
                alternative_tools=["EthanHenrickson/math-mcp::subtract"],
            )
        )
        assert gt.ambiguity == Ambiguity.MEDIUM

    def test_manual_seed_requires_manually_verified_true(self):
        with pytest.raises(ValueError, match="manually_verified"):
            GroundTruthEntry(**self._base(source="manual_seed", manually_verified=False))

    def test_llm_synthetic_can_be_unverified(self):
        gt = GroundTruthEntry(**self._base(source="llm_synthetic", manually_verified=False))
        assert gt.source == "llm_synthetic"
        assert gt.manually_verified is False

    def test_correct_tool_id_must_start_with_server_id(self):
        with pytest.raises(ValueError):
            GroundTruthEntry(
                **self._base(
                    correct_server_id="server-a",
                    correct_tool_id="server-b::tool",
                )
            )

    def test_with_notes(self):
        gt = GroundTruthEntry(**self._base(notes="test note"))
        assert gt.notes == "test note"
