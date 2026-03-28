"""Tests for grounded optimization context and prompt building."""

from description_optimizer.models import OptimizationContext


def test_optimization_context_with_schema():
    ctx = OptimizationContext(
        tool_id="slack::SLACK_DELETE_A_COMMENT_ON_A_FILE",
        original_description="Deletes a specific comment from a file in Slack.",
        input_schema={
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File ID"},
                "id": {"type": "string", "description": "Comment ID"},
            },
            "required": ["file", "id"],
        },
        sibling_tools=[
            {
                "tool_name": "SLACK_ADD_A_COMMENT_ON_A_FILE",
                "description": "Adds a comment to a file.",
            },
            {"tool_name": "SLACK_GET_FILE_INFO", "description": "Gets information about a file."},
        ],
    )
    assert ctx.tool_id == "slack::SLACK_DELETE_A_COMMENT_ON_A_FILE"
    assert ctx.input_schema is not None
    assert "file" in ctx.input_schema["properties"]
    assert len(ctx.sibling_tools) == 2


def test_optimization_context_without_schema():
    ctx = OptimizationContext(
        tool_id="test::tool",
        original_description="A test tool.",
        input_schema=None,
        sibling_tools=[],
    )
    assert ctx.input_schema is None
    assert ctx.sibling_tools == []


def test_optimization_context_parameter_names():
    ctx = OptimizationContext(
        tool_id="test::tool",
        original_description="A test tool.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
        sibling_tools=[],
    )
    assert ctx.parameter_names == ["query", "limit"]


def test_optimization_context_parameter_names_no_schema():
    ctx = OptimizationContext(
        tool_id="test::tool",
        original_description="A test tool.",
        input_schema=None,
        sibling_tools=[],
    )
    assert ctx.parameter_names == []
