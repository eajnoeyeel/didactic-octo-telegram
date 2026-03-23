"""Tests for QdrantStore — Qdrant Cloud wrapper."""

import uuid

import pytest

from models import MCPTool, TOOL_ID_SEPARATOR
from retrieval.qdrant_store import MCP_DISCOVERY_NAMESPACE, QdrantStore


@pytest.fixture
def sample_tool() -> MCPTool:
    return MCPTool(
        server_id="@smithery-ai/github",
        tool_name="search_issues",
        tool_id="@smithery-ai/github::search_issues",
        description="Search GitHub issues by query",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    )


@pytest.fixture
def tool_no_description() -> MCPTool:
    return MCPTool(
        server_id="@test/srv",
        tool_name="no_desc",
        tool_id="@test/srv::no_desc",
    )


class TestBuildToolText:
    def test_with_description(self, sample_tool):
        text = QdrantStore.build_tool_text(sample_tool)
        assert text == "search_issues: Search GitHub issues by query"

    def test_without_description(self, tool_no_description):
        text = QdrantStore.build_tool_text(tool_no_description)
        assert text == "no_desc"


class TestToolToPayload:
    def test_contains_required_fields(self, sample_tool):
        payload = QdrantStore.tool_to_payload(sample_tool)
        assert payload["tool_id"] == "@smithery-ai/github::search_issues"
        assert payload["server_id"] == "@smithery-ai/github"
        assert payload["tool_name"] == "search_issues"
        assert payload["description"] == "Search GitHub issues by query"
        assert payload["input_schema"] is not None

    def test_none_description(self, tool_no_description):
        payload = QdrantStore.tool_to_payload(tool_no_description)
        assert payload["description"] is None


class TestPayloadToTool:
    def test_roundtrip(self, sample_tool):
        payload = QdrantStore.tool_to_payload(sample_tool)
        restored = QdrantStore.payload_to_tool(payload)
        assert restored.tool_id == sample_tool.tool_id
        assert restored.server_id == sample_tool.server_id
        assert restored.tool_name == sample_tool.tool_name
        assert restored.description == sample_tool.description


class TestGeneratePointId:
    def test_deterministic(self):
        id1 = QdrantStore.generate_point_id("@test/srv::tool")
        id2 = QdrantStore.generate_point_id("@test/srv::tool")
        assert id1 == id2

    def test_different_ids_for_different_tools(self):
        id1 = QdrantStore.generate_point_id("@a/srv::tool1")
        id2 = QdrantStore.generate_point_id("@a/srv::tool2")
        assert id1 != id2

    def test_returns_valid_uuid_string(self):
        result = QdrantStore.generate_point_id("@test/srv::tool")
        parsed = uuid.UUID(result)
        assert str(parsed) == result

    def test_uses_uuid5(self):
        tool_id = "@test/srv::tool"
        expected = str(uuid.uuid5(MCP_DISCOVERY_NAMESPACE, tool_id))
        assert QdrantStore.generate_point_id(tool_id) == expected


class TestMCPDiscoveryNamespace:
    def test_is_valid_uuid(self):
        assert isinstance(MCP_DISCOVERY_NAMESPACE, uuid.UUID)

    def test_is_fixed_value(self):
        assert str(MCP_DISCOVERY_NAMESPACE) == "7f1b3d4e-2a5c-4b8f-9e6d-1c0a3f5b7d9e"
