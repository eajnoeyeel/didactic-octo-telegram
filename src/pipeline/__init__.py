"""Pipeline strategies for MCP Discovery Platform."""

from pipeline.confidence import compute_confidence
from pipeline.flat import FlatStrategy
from pipeline.sequential import SequentialStrategy
from pipeline.strategy import PipelineStrategy, StrategyRegistry

__all__ = [
    "PipelineStrategy",
    "StrategyRegistry",
    "compute_confidence",
    "FlatStrategy",
    "SequentialStrategy",
]
