"""LLM-based description optimizer using GPT-4o-mini."""

import json

from loguru import logger
from openai import AsyncOpenAI

from description_optimizer.models import AnalysisReport
from description_optimizer.optimizer.base import DescriptionOptimizer
from description_optimizer.optimizer.prompts import SYSTEM_PROMPT, build_optimization_prompt


class LLMDescriptionOptimizer(DescriptionOptimizer):
    """Optimizes tool descriptions using GPT-4o-mini with dimension-aware prompting."""

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature

    async def optimize(self, report: AnalysisReport) -> dict[str, str]:
        """Optimize a description based on its GEO analysis report.

        Args:
            report: AnalysisReport with dimension scores.

        Returns:
            Dict with 'optimized_description' and 'search_description'.
        """
        weak_dims = report.weak_dimensions(threshold=0.5)
        dim_scores = {s.dimension: s.score for s in report.dimension_scores}

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

        if "optimized_description" not in result or "search_description" not in result:
            logger.error(f"LLM response missing required keys: {list(result.keys())}")
            msg = "LLM response must contain 'optimized_description' and 'search_description'"
            raise ValueError(msg)

        logger.info(
            f"Optimized {report.tool_id}: "
            f"weak_dims={weak_dims}, "
            f"original_len={len(report.original_description)}, "
            f"optimized_len={len(result['optimized_description'])}"
        )

        return {
            "optimized_description": result["optimized_description"],
            "search_description": result["search_description"],
        }
