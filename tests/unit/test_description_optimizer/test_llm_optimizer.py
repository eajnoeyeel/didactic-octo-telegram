"""Tests for LLMDescriptionOptimizer — dimension-aware rewriting."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from description_optimizer.models import AnalysisReport, DimensionScore, OptimizationContext
from description_optimizer.optimizer.base import DescriptionOptimizer
from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer
from description_optimizer.optimizer.prompts import (
    build_optimization_prompt,
    build_search_description_prompt,
)


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    client = AsyncMock()
    # Mock the chat.completions.create response
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = (
        '{"optimized_description": "Improved description text", '
        '"search_description": "search optimized text"}'
    )
    mock_response.choices = [mock_choice]
    client.chat.completions.create.return_value = mock_response
    return client


@pytest.fixture
def optimizer(mock_openai_client: AsyncMock) -> LLMDescriptionOptimizer:
    return LLMDescriptionOptimizer(client=mock_openai_client)


@pytest.fixture
def sample_report() -> AnalysisReport:
    return AnalysisReport(
        tool_id="github::search_issues",
        original_description="Search GitHub issues.",
        dimension_scores=[
            DimensionScore(dimension="clarity", score=0.4, explanation="weak"),
            DimensionScore(dimension="disambiguation", score=0.2, explanation="missing"),
            DimensionScore(dimension="parameter_coverage", score=0.3, explanation="weak"),
            DimensionScore(dimension="fluency", score=0.1, explanation="missing"),
            DimensionScore(dimension="stats", score=0.0, explanation="none"),
            DimensionScore(dimension="precision", score=0.3, explanation="weak"),
        ],
    )


class TestLLMOptimizerIsABC:
    def test_implements_abc(self, optimizer: LLMDescriptionOptimizer) -> None:
        assert isinstance(optimizer, DescriptionOptimizer)


class TestOptimize:
    async def test_calls_openai(
        self,
        optimizer: LLMDescriptionOptimizer,
        sample_report: AnalysisReport,
        mock_openai_client: AsyncMock,
    ) -> None:
        await optimizer.optimize(sample_report)
        mock_openai_client.chat.completions.create.assert_called_once()

    async def test_returns_optimized_and_search(
        self,
        optimizer: LLMDescriptionOptimizer,
        sample_report: AnalysisReport,
    ) -> None:
        result = await optimizer.optimize(sample_report)
        assert result["optimized_description"] == "Improved description text"
        assert result["search_description"] == "search optimized text"

    async def test_includes_weak_dimensions_in_prompt(
        self,
        optimizer: LLMDescriptionOptimizer,
        sample_report: AnalysisReport,
        mock_openai_client: AsyncMock,
    ) -> None:
        await optimizer.optimize(sample_report)
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages", call_args[1].get("messages", []))
        user_msg = next(m for m in messages if m["role"] == "user")
        # All dimensions are weak (<0.5), so all should be mentioned
        assert "clarity" in user_msg["content"]
        assert "disambiguation" in user_msg["content"]


class TestPromptBuilding:
    def test_optimization_prompt_contains_weak_dims(self) -> None:
        weak = ["clarity", "fluency"]
        prompt = build_optimization_prompt(
            original="Search tool",
            tool_id="s::t",
            weak_dimensions=weak,
            dimension_scores={"clarity": 0.3, "fluency": 0.1},
        )
        assert "clarity" in prompt
        assert "fluency" in prompt
        assert "Search tool" in prompt

    def test_optimization_prompt_preserves_original(self) -> None:
        prompt = build_optimization_prompt(
            original="My special tool for X",
            tool_id="s::t",
            weak_dimensions=["clarity"],
            dimension_scores={"clarity": 0.3},
        )
        assert "My special tool for X" in prompt

    def test_search_description_prompt(self) -> None:
        prompt = build_search_description_prompt(
            optimized="An improved tool description.",
            tool_id="s::t",
        )
        assert "An improved tool description" in prompt


@pytest.fixture
def sample_context() -> OptimizationContext:
    return OptimizationContext(
        tool_id="slack::SLACK_DELETE_COMMENT",
        original_description="Deletes a comment from a file.",
        input_schema={
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File ID"},
                "id": {"type": "string", "description": "Comment ID"},
            },
            "required": ["file", "id"],
        },
        sibling_tools=[
            {"tool_name": "SLACK_ADD_COMMENT", "description": "Adds a comment to a file."},
        ],
    )


@pytest.fixture
def sample_report_for_context() -> AnalysisReport:
    return AnalysisReport(
        tool_id="slack::SLACK_DELETE_COMMENT",
        original_description="Deletes a comment from a file.",
        dimension_scores=[
            DimensionScore(dimension="clarity", score=0.35, explanation="low"),
            DimensionScore(dimension="disambiguation", score=0.0, explanation="none"),
            DimensionScore(dimension="parameter_coverage", score=0.0, explanation="none"),
            DimensionScore(dimension="fluency", score=0.0, explanation="none"),
            DimensionScore(dimension="stats", score=0.0, explanation="none"),
            DimensionScore(dimension="precision", score=0.0, explanation="none"),
        ],
    )


class TestOptimizeWithContext:
    async def test_optimize_with_context_passes_schema_to_prompt(
        self,
        sample_report_for_context: AnalysisReport,
        sample_context: OptimizationContext,
    ) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = '{"optimized_description": "improved", "search_description": "search"}'
        mock_client.chat.completions.create.return_value = mock_response

        optimizer = LLMDescriptionOptimizer(client=mock_client)
        result = await optimizer.optimize(sample_report_for_context, context=sample_context)

        assert result["optimized_description"] == "improved"
        # Verify the prompt sent to OpenAI contains schema info
        call_args = mock_client.chat.completions.create.call_args
        user_message = call_args.kwargs["messages"][1]["content"]
        assert '"file"' in user_message
        assert '"id"' in user_message

    async def test_optimize_without_context_still_works(
        self,
        sample_report_for_context: AnalysisReport,
    ) -> None:
        """Backward compatibility: optimize() without context uses old prompt."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = '{"optimized_description": "improved", "search_description": "search"}'
        mock_client.chat.completions.create.return_value = mock_response

        optimizer = LLMDescriptionOptimizer(client=mock_client)
        result = await optimizer.optimize(sample_report_for_context)

        assert result["optimized_description"] == "improved"
