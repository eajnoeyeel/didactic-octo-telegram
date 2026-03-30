"""Tests for disambiguation prompt redesign — sibling name contamination removal."""

from description_optimizer.optimizer.prompts import (
    _build_grounded_guidance,
    build_grounded_prompt,
)


class TestDisambiguationPromptRedesign:
    """Verify prompts no longer list sibling tool names in disambiguation guidance."""

    def test_grounded_guidance_no_sibling_names_in_disambiguation(self) -> None:
        """Disambiguation guidance should NOT mention sibling tool names."""
        guidance = _build_grounded_guidance(
            weak_dimensions=["disambiguation"],
            dimension_scores={"disambiguation": 0.1},
            input_schema=None,
            sibling_tools=[
                {"tool_name": "add", "description": "Adds two numbers"},
                {"tool_name": "subtract", "description": "Subtracts numbers"},
            ],
        )
        # Should NOT list sibling tool names for comparison
        assert "sibling tools: add" not in guidance.lower()
        assert "subtract" not in guidance.lower()
        assert "Differentiate from these sibling tools" not in guidance

    def test_grounded_guidance_uses_target_only_language(self) -> None:
        """Disambiguation guidance should focus on target tool's unique qualities."""
        guidance = _build_grounded_guidance(
            weak_dimensions=["disambiguation"],
            dimension_scores={"disambiguation": 0.2},
            input_schema=None,
            sibling_tools=[
                {"tool_name": "mean", "description": "Calculates the mean"},
            ],
        )
        # Should contain target-focused language
        assert "unique" in guidance.lower() or "specific" in guidance.lower()

    def test_grounded_prompt_sibling_section_removed(self) -> None:
        """build_grounded_prompt should NOT include sibling tools section."""
        prompt = build_grounded_prompt(
            original="Calculates the median of a list of numbers",
            tool_id="math::median",
            input_schema={"properties": {"numbers": {"type": "array"}}, "required": ["numbers"]},
            sibling_tools=[
                {"tool_name": "mean", "description": "Calculates the mean"},
                {"tool_name": "mode", "description": "Calculates the mode"},
            ],
            weak_dimensions=["disambiguation"],
            dimension_scores={"disambiguation": 0.1},
        )
        assert "Other tools on this server" not in prompt
        # Sibling tool names should not appear as listed items
        assert "- mean:" not in prompt.lower()
        assert "- mode:" not in prompt.lower()
