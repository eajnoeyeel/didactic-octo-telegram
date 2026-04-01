"""Abstract base class for description analyzers."""

from abc import ABC, abstractmethod

from description_optimizer.models import AnalysisReport


class DescriptionAnalyzer(ABC):
    """ABC for GEO dimension scoring of MCP tool descriptions."""

    @abstractmethod
    async def analyze(self, tool_id: str, description: str | None) -> AnalysisReport:
        """Analyze a tool description and return a GEO AnalysisReport.

        Args:
            tool_id: The tool identifier in `server_id::tool_name` format.
            description: The tool description text. None or empty string is valid input.

        Returns:
            AnalysisReport with scores for all 6 GEO dimensions.
        """
        ...
