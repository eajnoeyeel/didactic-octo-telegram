"""Tests for data models."""

import pytest

from models import (
    TOOL_ID_SEPARATOR,
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
            server_id="srv", tool_name="t", tool_id="srv::t",
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


class TestGroundTruthEntry:
    def test_create(self):
        gt = GroundTruthEntry(
            query="search github issues",
            correct_server_id="@smithery-ai/github",
            correct_tool_id="@smithery-ai/github::search_issues",
        )
        assert gt.difficulty is None
        assert gt.manually_verified is False
