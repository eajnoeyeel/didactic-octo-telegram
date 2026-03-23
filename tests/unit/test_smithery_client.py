"""Tests for SmitheryClient — HTTP client for Smithery Registry API."""

import pytest

from data.smithery_client import SmitheryClient
from models import MCPServerSummary, MCPServer, TOOL_ID_SEPARATOR


# --- Fixtures: raw API responses ---

SAMPLE_LIST_ITEM = {
    "qualifiedName": "@anthropic/claude-code",
    "displayName": "Claude Code",
    "description": "AI coding assistant",
    "useCount": 5000,
    "createdAt": "2025-01-01T00:00:00Z",
    "verified": True,
    "isDeployed": True,
}

SAMPLE_LIST_ITEM_MINIMAL = {
    "qualifiedName": "@test/minimal",
    "displayName": "Minimal Server",
}

SAMPLE_DETAIL_RESPONSE = {
    "qualifiedName": "@anthropic/claude-code",
    "displayName": "Claude Code",
    "description": "AI coding assistant",
    "homepage": "https://claude.ai",
    "tools": [
        {
            "name": "run_command",
            "description": "Run a shell command",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                },
            },
        },
        {
            "name": "edit_file",
            "description": "Edit a file",
            "inputSchema": None,
        },
    ],
}

SAMPLE_DETAIL_NO_TOOLS = {
    "qualifiedName": "@test/empty",
    "displayName": "Empty Server",
    "description": "No tools",
}


class TestParseServerSummary:
    def test_full_fields(self):
        result = SmitheryClient.parse_server_summary(SAMPLE_LIST_ITEM)
        assert isinstance(result, MCPServerSummary)
        assert result.qualified_name == "@anthropic/claude-code"
        assert result.display_name == "Claude Code"
        assert result.description == "AI coding assistant"
        assert result.use_count == 5000
        assert result.is_verified is True
        assert result.is_deployed is True

    def test_minimal_fields(self):
        result = SmitheryClient.parse_server_summary(SAMPLE_LIST_ITEM_MINIMAL)
        assert result.qualified_name == "@test/minimal"
        assert result.use_count == 0
        assert result.is_verified is False
        assert result.is_deployed is False


class TestParseServerDetail:
    def test_with_tools(self):
        result = SmitheryClient.parse_server_detail(SAMPLE_DETAIL_RESPONSE)
        assert isinstance(result, MCPServer)
        assert result.server_id == "@anthropic/claude-code"
        assert result.name == "Claude Code"
        assert result.homepage == "https://claude.ai"
        assert len(result.tools) == 2

        tool0 = result.tools[0]
        assert tool0.tool_id == f"@anthropic/claude-code{TOOL_ID_SEPARATOR}run_command"
        assert tool0.tool_name == "run_command"
        assert tool0.description == "Run a shell command"
        assert tool0.input_schema is not None

        tool1 = result.tools[1]
        assert tool1.tool_id == f"@anthropic/claude-code{TOOL_ID_SEPARATOR}edit_file"
        assert tool1.input_schema is None

    def test_no_tools(self):
        result = SmitheryClient.parse_server_detail(SAMPLE_DETAIL_NO_TOOLS)
        assert result.server_id == "@test/empty"
        assert result.tools == []

    def test_tool_id_uses_separator_constant(self):
        result = SmitheryClient.parse_server_detail(SAMPLE_DETAIL_RESPONSE)
        for tool in result.tools:
            assert TOOL_ID_SEPARATOR in tool.tool_id
            parts = tool.tool_id.split(TOOL_ID_SEPARATOR)
            assert len(parts) == 2
            assert parts[0] == "@anthropic/claude-code"


class TestSmitheryClientInit:
    def test_default_rate_limit(self):
        client = SmitheryClient(base_url="https://example.com")
        assert client.rate_limit_seconds == 0.5

    def test_custom_rate_limit(self):
        client = SmitheryClient(base_url="https://example.com", rate_limit_seconds=1.0)
        assert client.rate_limit_seconds == 1.0


class TestFetchAllSummaries:
    async def test_stops_on_empty_page(self):
        client = SmitheryClient(base_url="https://example.com", rate_limit_seconds=0.0)
        calls = 0

        async def mock_fetch(page, page_size=50):
            nonlocal calls
            calls += 1
            if page == 1:
                return [
                    SmitheryClient.parse_server_summary(SAMPLE_LIST_ITEM),
                    SmitheryClient.parse_server_summary(SAMPLE_LIST_ITEM_MINIMAL),
                ], {"currentPage": 1, "totalPages": 5}
            return [], {}

        client.fetch_server_list = mock_fetch
        result = await client.fetch_all_summaries(max_pages=10)
        assert len(result) == 2
        assert calls == 2

    async def test_stops_on_max_pages(self):
        client = SmitheryClient(base_url="https://example.com", rate_limit_seconds=0.0)

        async def mock_fetch(page, page_size=50):
            return [SmitheryClient.parse_server_summary(SAMPLE_LIST_ITEM)], {
                "currentPage": page, "totalPages": 100,
            }

        client.fetch_server_list = mock_fetch
        result = await client.fetch_all_summaries(max_pages=3)
        assert len(result) == 3

    async def test_stops_on_last_page(self):
        client = SmitheryClient(base_url="https://example.com", rate_limit_seconds=0.0)

        async def mock_fetch(page, page_size=50):
            return [SmitheryClient.parse_server_summary(SAMPLE_LIST_ITEM)], {
                "currentPage": 2, "totalPages": 2,
            }

        client.fetch_server_list = mock_fetch
        result = await client.fetch_all_summaries(max_pages=10)
        assert len(result) == 1
