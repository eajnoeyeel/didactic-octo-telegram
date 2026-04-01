"""Integration tests for Description Optimizer pipeline.

Tests the full pipeline with mocked LLM but real analyzer and gate.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import OptimizationStatus
from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer
from description_optimizer.pipeline import OptimizationPipeline
from description_optimizer.quality_gate import QualityGate


def _make_similar_vectors(dim: int = 1536) -> tuple[np.ndarray, np.ndarray]:
    """Create two similar unit vectors (cosine sim > 0.95)."""
    rng = np.random.default_rng(42)
    base = rng.standard_normal(dim)
    base = base / np.linalg.norm(base)
    noise = rng.standard_normal(dim) * 0.05
    similar = base + noise
    similar = similar / np.linalg.norm(similar)
    return base, similar


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    """Mock OpenAI client that returns a realistic optimized description."""
    client = AsyncMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(
        {
            "optimized_description": (
                "Searches GitHub Issues matching a text query via the GitHub "
                "REST API v3. Use when you need to find bug reports or feature "
                "requests in a repository. Unlike the PR search tool, this only "
                "searches Issues. Cannot search across multiple repositories. "
                "Returns up to 100 results."
            ),
            "search_description": (
                "github issues search query bug report feature request "
                "repository REST API find issues text search filter"
            ),
        }
    )
    mock_response.choices = [mock_choice]
    client.chat.completions.create.return_value = mock_response
    return client


@pytest.fixture
def mock_embedder() -> AsyncMock:
    """Mock embedder returning similar vectors."""
    embedder = AsyncMock()
    base, similar = _make_similar_vectors()
    # Return alternating base/similar for each embed_one call
    embedder.embed_one.return_value = base
    return embedder


@pytest.fixture
def pipeline(mock_openai_client: AsyncMock, mock_embedder: AsyncMock) -> OptimizationPipeline:
    return OptimizationPipeline(
        analyzer=HeuristicAnalyzer(),
        optimizer=LLMDescriptionOptimizer(client=mock_openai_client),
        embedder=mock_embedder,
        gate=QualityGate(min_similarity=0.85),
        skip_threshold=0.75,
    )


class TestFullPipelineIntegration:
    async def test_poor_description_gets_optimized(self, pipeline: OptimizationPipeline) -> None:
        result = await pipeline.run("github::search_issues", "Search issues")
        assert result.status == OptimizationStatus.SUCCESS
        assert len(result.optimized_description) > len(result.original_description)
        assert result.geo_score_after >= result.geo_score_before

    async def test_batch_processing(
        self,
        pipeline: OptimizationPipeline,
    ) -> None:
        tools = [
            ("s::t1", "A search tool"),
            ("s::t2", "File reader"),
            ("s::t3", "Database connector"),
        ]
        results = await pipeline.run_batch(tools)
        assert len(results) == 3
