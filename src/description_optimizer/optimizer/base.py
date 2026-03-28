"""Abstract base class for description optimizers."""

from abc import ABC, abstractmethod

from description_optimizer.models import AnalysisReport, OptimizationContext


class DescriptionOptimizer(ABC):
    """ABC for optimizing MCP tool descriptions.

    Takes an AnalysisReport (with weak dimension info) and optionally
    an OptimizationContext (with input_schema + sibling tools) to produce
    an optimized description + search description.
    """

    @abstractmethod
    async def optimize(
        self,
        report: AnalysisReport,
        context: OptimizationContext | None = None,
    ) -> dict[str, str]:
        """Optimize a tool description based on its analysis report.

        Args:
            report: AnalysisReport with GEO scores and weak dimensions.
            context: Optional grounding context with input_schema and sibling tools.

        Returns:
            Dict with keys: 'optimized_description', 'search_description'.
        """
        ...
