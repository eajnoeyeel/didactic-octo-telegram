"""LLM-based description optimizer using GPT-4o-mini."""

import json

from loguru import logger
from openai import AsyncOpenAI

from description_optimizer.models import AnalysisReport, OptimizationContext
from description_optimizer.optimizer.base import DescriptionOptimizer
from description_optimizer.optimizer.prompts import (
    SYSTEM_PROMPT,
    build_grounded_prompt,
    build_optimization_prompt,
)


class LLMDescriptionOptimizer(DescriptionOptimizer):
    """Optimizes tool descriptions using GPT-4o-mini with retrieval-aware prompting."""

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature

    async def optimize(
        self,
        report: AnalysisReport,
        context: OptimizationContext | None = None,
    ) -> dict[str, str]:
        """Optimize a description for retrieval while keeping GEO diagnostics available.

        Args:
            report: AnalysisReport with dimension scores.
            context: Optional grounding context with input_schema and sibling tools.

        Returns:
            Dict with 'optimized_description' and 'retrieval_description'.
        """
        weak_dims = report.weak_dimensions(threshold=0.5)
        dim_scores = {s.dimension: s.score for s in report.dimension_scores}

        if context:
            prompt = build_grounded_prompt(
                original=report.original_description,
                tool_id=report.tool_id,
                input_schema=context.input_schema,
                sibling_tools=context.sibling_tools,
                weak_dimensions=weak_dims,
                dimension_scores=dim_scores,
            )
        else:
            prompt = build_optimization_prompt(
                original=report.original_description,
                tool_id=report.tool_id,
                weak_dimensions=weak_dims,
                dimension_scores=dim_scores,
            )

        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response as JSON: {content[:200]}")
            raise

        retrieval_description = (
            result["retrieval_description"]
            if "retrieval_description" in result
            else result.get("search_description")
        )
        optimized_description = (
            result["optimized_description"]
            if "optimized_description" in result
            else retrieval_description
        )

        if optimized_description is None or retrieval_description is None:
            logger.error(f"LLM response missing required keys: {list(result.keys())}")
            msg = (
                "LLM response must contain 'optimized_description' and "
                "'retrieval_description' (or legacy 'search_description')"
            )
            raise ValueError(msg)

        logger.info(
            f"Optimized {report.tool_id}: "
            f"weak_dims={weak_dims}, "
            f"grounded={'yes' if context else 'no'}, "
            f"original_len={len(report.original_description)}, "
            f"optimized_len={len(optimized_description)}, "
            f"retrieval_len={len(retrieval_description)}"
        )

        return {
            "optimized_description": optimized_description,
            "retrieval_description": retrieval_description,
            "search_description": retrieval_description,
        }
