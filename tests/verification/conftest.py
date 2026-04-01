"""Shared fixtures for HeuristicAnalyzer verification tests."""

import pytest

from description_optimizer.analyzer.heuristic import HeuristicAnalyzer


@pytest.fixture
def analyzer() -> HeuristicAnalyzer:
    return HeuristicAnalyzer()
