"""Tests for grounded optimization context and prompt building."""

from description_optimizer.models import OptimizationContext
from description_optimizer.optimizer.prompts import build_grounded_prompt


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


def test_grounded_prompt_includes_input_schema():
    schema = {
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "File ID"},
            "id": {"type": "string", "description": "Comment ID"},
        },
        "required": ["file", "id"],
    }
    prompt = build_grounded_prompt(
        original="Deletes a comment from a file.",
        tool_id="slack::delete_comment",
        input_schema=schema,
        sibling_tools=[],
        weak_dimensions=["parameter_coverage"],
        dimension_scores={"parameter_coverage": 0.1, "clarity": 0.5},
    )
    assert '"file"' in prompt
    assert '"id"' in prompt
    assert "File ID" in prompt


def test_grounded_prompt_includes_sibling_tools():
    siblings = [
        {"tool_name": "add_comment", "description": "Adds a comment."},
        {"tool_name": "get_file", "description": "Gets file info."},
    ]
    prompt = build_grounded_prompt(
        original="Deletes a comment.",
        tool_id="slack::delete_comment",
        input_schema=None,
        sibling_tools=siblings,
        weak_dimensions=["disambiguation"],
        dimension_scores={"disambiguation": 0.1, "clarity": 0.5},
    )
    assert "add_comment" in prompt
    assert "get_file" in prompt


def test_grounded_prompt_anti_hallucination_rules():
    prompt = build_grounded_prompt(
        original="A tool.",
        tool_id="test::tool",
        input_schema=None,
        sibling_tools=[],
        weak_dimensions=["fluency"],
        dimension_scores={"fluency": 0.0, "clarity": 0.3},
    )
    # Must contain anti-hallucination instruction
    lower = prompt.lower()
    assert "do not invent" in lower or "do not add" in lower or "never invent" in lower


def test_grounded_prompt_no_schema_skips_parameter_section():
    prompt = build_grounded_prompt(
        original="A tool.",
        tool_id="test::tool",
        input_schema=None,
        sibling_tools=[],
        weak_dimensions=["clarity"],
        dimension_scores={"clarity": 0.2},
    )
    assert "Input Schema" not in prompt


def test_grounded_prompt_augmentation_instruction():
    prompt = build_grounded_prompt(
        original="Deletes a comment from a file.",
        tool_id="test::tool",
        input_schema=None,
        sibling_tools=[],
        weak_dimensions=["clarity"],
        dimension_scores={"clarity": 0.2},
    )
    lower = prompt.lower()
    assert "preserve" in lower or "keep" in lower or "augment" in lower


def test_query_aware_prompt_includes_queries():
    """Query-aware prompt includes relevant search queries."""
    from description_optimizer.models import OptimizationContext
    from description_optimizer.optimizer.prompts import build_query_aware_prompt

    context = OptimizationContext(
        tool_id="slack::send_message",
        original_description="Send a message",
        input_schema={"type": "object", "properties": {"channel": {"type": "string"}}},
    )
    prompt = build_query_aware_prompt(
        context, relevant_queries=["send a message on slack", "post to a channel"]
    )
    assert "send a message on slack" in prompt
    assert "post to a channel" in prompt


def test_query_aware_prompt_includes_schema():
    """Query-aware prompt includes input_schema when available."""
    from description_optimizer.models import OptimizationContext
    from description_optimizer.optimizer.prompts import build_query_aware_prompt

    context = OptimizationContext(
        tool_id="test::tool",
        original_description="Do something",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
    )
    prompt = build_query_aware_prompt(context, relevant_queries=[])
    assert "query" in prompt


def test_query_aware_prompt_anti_hallucination():
    """Query-aware prompt includes anti-hallucination rules."""
    from description_optimizer.models import OptimizationContext
    from description_optimizer.optimizer.prompts import build_query_aware_prompt

    context = OptimizationContext(tool_id="test::tool", original_description="Do something")
    prompt = build_query_aware_prompt(context, relevant_queries=["find test tool"])
    assert "NEVER" in prompt or "never" in prompt.lower()
