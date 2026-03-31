"""Robustness tests for LLMDescriptionOptimizer — error handling and edge cases."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from description_optimizer.models import AnalysisReport, DimensionScore
from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer

ALL_DIMS = [
    "clarity",
    "disambiguation",
    "parameter_coverage",
    "fluency",
    "stats",
    "precision",
]


def _make_report(desc: str = "test", geo_uniform: float = 0.3) -> AnalysisReport:
    return AnalysisReport(
        tool_id="s::t",
        original_description=desc,
        dimension_scores=[
            DimensionScore(dimension=d, score=geo_uniform, explanation="test") for d in ALL_DIMS
        ],
    )


def _mock_client_with_content(content: str) -> AsyncMock:
    client = AsyncMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response.choices = [mock_choice]
    client.chat.completions.create.return_value = mock_response
    return client


class TestMalformedJSON:
    """Verify the optimizer raises on malformed or incomplete JSON responses."""

    async def test_invalid_json_raises(self) -> None:
        client = _mock_client_with_content("This is not JSON")
        optimizer = LLMDescriptionOptimizer(client=client)
        report = _make_report()

        with pytest.raises(json.JSONDecodeError):
            await optimizer.optimize(report)

    async def test_missing_optimized_description_key(self) -> None:
        content = json.dumps({"wrong_key": "value", "search_description": "desc"})
        client = _mock_client_with_content(content)
        optimizer = LLMDescriptionOptimizer(client=client)
        report = _make_report()

        result = await optimizer.optimize(report)
        assert result["optimized_description"] == "desc"
        assert result["retrieval_description"] == "desc"

    async def test_missing_search_description_key(self) -> None:
        content = json.dumps({"optimized_description": "value", "wrong": "desc"})
        client = _mock_client_with_content(content)
        optimizer = LLMDescriptionOptimizer(client=client)
        report = _make_report()

        with pytest.raises(ValueError, match="search_description"):
            await optimizer.optimize(report)

    async def test_empty_json_object(self) -> None:
        content = json.dumps({})
        client = _mock_client_with_content(content)
        optimizer = LLMDescriptionOptimizer(client=client)
        report = _make_report()

        with pytest.raises(ValueError):
            await optimizer.optimize(report)

    async def test_null_content(self) -> None:
        client = AsyncMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_response.choices = [mock_choice]
        client.chat.completions.create.return_value = mock_response

        optimizer = LLMDescriptionOptimizer(client=client)
        report = _make_report()

        with pytest.raises((TypeError, json.JSONDecodeError)):
            await optimizer.optimize(report)


class TestExtraKeysInResponse:
    """Verify the optimizer tolerates extra keys in the LLM JSON response."""

    async def test_extra_keys_accepted(self) -> None:
        content = json.dumps(
            {
                "optimized_description": "Optimized tool description.",
                "search_description": "Search-ready description.",
                "extra_field": "ignored value",
                "another_extra": 42,
            }
        )
        client = _mock_client_with_content(content)
        optimizer = LLMDescriptionOptimizer(client=client)
        report = _make_report()

        result = await optimizer.optimize(report)

        assert result["optimized_description"] == "Optimized tool description."
        assert result["retrieval_description"] == "Search-ready description."
        assert result["search_description"] == "Search-ready description."
        assert "extra_field" not in result


class TestEmptyDescriptions:
    """Verify the optimizer handles edge cases in returned description values."""

    async def test_empty_optimized_description(self) -> None:
        content = json.dumps(
            {
                "optimized_description": "",
                "search_description": "Some search desc",
            }
        )
        client = _mock_client_with_content(content)
        optimizer = LLMDescriptionOptimizer(client=client)
        report = _make_report()

        result = await optimizer.optimize(report)

        assert result["optimized_description"] == ""
        assert result["retrieval_description"] == "Some search desc"
        assert result["search_description"] == "Some search desc"

    async def test_very_long_response(self) -> None:
        long_text = "A" * 2500
        content = json.dumps(
            {
                "optimized_description": long_text,
                "search_description": "Short search description.",
            }
        )
        client = _mock_client_with_content(content)
        optimizer = LLMDescriptionOptimizer(client=client)
        report = _make_report()

        result = await optimizer.optimize(report)

        assert len(result["optimized_description"]) >= 2500
        assert result["retrieval_description"] == "Short search description."
        assert result["search_description"] == "Short search description."


class TestAPIFailures:
    """Verify the optimizer propagates API-level exceptions."""

    async def test_openai_api_error_propagates(self) -> None:
        client = AsyncMock()
        client.chat.completions.create.side_effect = Exception("API rate limit")
        optimizer = LLMDescriptionOptimizer(client=client)
        report = _make_report()

        with pytest.raises(Exception, match="API rate limit"):
            await optimizer.optimize(report)


class TestWeakDimensionsInPrompt:
    """Verify that weak dimensions are correctly reflected in the prompt."""

    async def test_all_weak_dimensions_included(self) -> None:
        """With geo=0.2 (all dims below 0.5 threshold), all 6 dims should appear in prompt."""
        captured_messages: list[list[dict]] = []

        async def capture_create(**kwargs: object) -> MagicMock:
            captured_messages.append(kwargs.get("messages", []))  # type: ignore[arg-type]
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = json.dumps(
                {
                    "optimized_description": "Improved description.",
                    "search_description": "Search description.",
                }
            )
            mock_response.choices = [mock_choice]
            return mock_response

        client = AsyncMock()
        client.chat.completions.create.side_effect = capture_create

        optimizer = LLMDescriptionOptimizer(client=client)
        report = _make_report(geo_uniform=0.2)

        await optimizer.optimize(report)

        assert len(captured_messages) == 1
        user_prompt = captured_messages[0][1]["content"]
        for dim in ALL_DIMS:
            assert dim in user_prompt

    async def test_no_weak_dimensions(self) -> None:
        """With geo=0.8 (all dims above 0.5 threshold), prompt should indicate adequate state."""
        captured_messages: list[list[dict]] = []

        async def capture_create(**kwargs: object) -> MagicMock:
            captured_messages.append(kwargs.get("messages", []))  # type: ignore[arg-type]
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = json.dumps(
                {
                    "optimized_description": "Already good description.",
                    "search_description": "Good search description.",
                }
            )
            mock_response.choices = [mock_choice]
            return mock_response

        client = AsyncMock()
        client.chat.completions.create.side_effect = capture_create

        optimizer = LLMDescriptionOptimizer(client=client)
        report = _make_report(geo_uniform=0.8)

        await optimizer.optimize(report)

        assert len(captured_messages) == 1
        user_prompt = captured_messages[0][1]["content"]
        # When no dimensions are weak, the prompt should reflect that
        assert "none" in user_prompt.lower() or "adequate" in user_prompt.lower()
