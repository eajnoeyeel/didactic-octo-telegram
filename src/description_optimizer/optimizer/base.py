"""Abstract base class for description optimizers."""

from abc import ABC, abstractmethod

from description_optimizer.models import AnalysisReport


class DescriptionOptimizer(ABC):
    """ABC for optimizing MCP tool descriptions.

    Takes an AnalysisReport (with weak dimension info) and produces
    an optimized description + search description.
    """

    @abstractmethod
    async def optimize(self, report: AnalysisReport) -> dict[str, str]:
        """Optimize a tool description based on its analysis report.

        Args:
            report: AnalysisReport with GEO scores and weak dimensions.

        Returns:
            Dict with keys: 'optimized_description', 'search_description'.
        """
        ...
