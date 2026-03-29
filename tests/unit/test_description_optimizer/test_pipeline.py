"""Tests for OptimizationPipeline — orchestrates analyze -> optimize -> gate."""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from description_optimizer.models import (
    AnalysisReport,
    DimensionScore,
    OptimizationStatus,
    OptimizedDescription,
)
from description_optimizer.pipeline import OptimizationPipeline
from description_optimizer.quality_gate import FullGateResult, GateResult
from models import MCPTool

ALL_DIMS = [
    "clarity",
    "disambiguation",
    "parameter_coverage",
    "fluency",
    "stats",
    "precision",
]


def _make_report(geo: float, desc: str = "test") -> AnalysisReport:
    return AnalysisReport(
        tool_id="s::t",
        original_description=desc,
        dimension_scores=[
            DimensionScore(dimension=d, score=geo, explanation="test") for d in ALL_DIMS
        ],
    )


@pytest.fixture
def mock_analyzer() -> AsyncMock:
    analyzer = AsyncMock()
    analyzer.analyze.return_value = _make_report(0.3, "original desc")
    return analyzer


@pytest.fixture
def mock_optimizer() -> AsyncMock:
    optimizer = AsyncMock()
    optimizer.optimize.return_value = {
        "optimized_description": "improved desc",
        "search_description": "search desc",
    }
    return optimizer


@pytest.fixture
def mock_embedder() -> AsyncMock:
    embedder = AsyncMock()
    # Return similar vectors for each call pair (original, optimized)
    embedder.embed_one.return_value = np.array([0.95, 0.1, 0.05])
    return embedder


@pytest.fixture
def mock_gate() -> MagicMock:
    gate = MagicMock()
    gate.evaluate.return_value = FullGateResult(
        passed=True,
        geo_result=GateResult(passed=True, reason="ok"),
        similarity_result=GateResult(passed=True, reason="ok", similarity=0.95),
    )
    return gate


@pytest.fixture
def pipeline(
    mock_analyzer: AsyncMock,
    mock_optimizer: AsyncMock,
    mock_embedder: AsyncMock,
    mock_gate: MagicMock,
) -> OptimizationPipeline:
    return OptimizationPipeline(
        analyzer=mock_analyzer,
        optimizer=mock_optimizer,
        embedder=mock_embedder,
        gate=mock_gate,
    )


class TestPipelineSuccess:
    async def test_full_pipeline(self, pipeline: OptimizationPipeline) -> None:
        result = await pipeline.run("s::t", "original desc")
        assert isinstance(result, OptimizedDescription)
        assert result.status == OptimizationStatus.SUCCESS
        assert result.optimized_description == "improved desc"
        assert result.search_description == "search desc"

    async def test_calls_analyzer_first(
        self,
        pipeline: OptimizationPipeline,
        mock_analyzer: AsyncMock,
    ) -> None:
        await pipeline.run("s::t", "test")
        # Analyzer is called twice: once for original, once for re-analysis
        assert mock_analyzer.analyze.call_count == 2
        mock_analyzer.analyze.assert_any_call("s::t", "test")

    async def test_calls_optimizer_with_report(
        self,
        pipeline: OptimizationPipeline,
        mock_optimizer: AsyncMock,
    ) -> None:
        await pipeline.run("s::t", "test")
        mock_optimizer.optimize.assert_called_once()

    async def test_calls_gate_with_embeddings(
        self,
        pipeline: OptimizationPipeline,
        mock_gate: MagicMock,
    ) -> None:
        await pipeline.run("s::t", "test")
        mock_gate.evaluate.assert_called_once()


class TestPipelineSkip:
    async def test_skip_when_high_geo_score(
        self,
        pipeline: OptimizationPipeline,
        mock_analyzer: AsyncMock,
    ) -> None:
        mock_analyzer.analyze.return_value = _make_report(0.85, "already great")
        result = await pipeline.run("s::t", "already great")
        assert result.status == OptimizationStatus.SKIPPED
        assert result.skip_reason is not None

    async def test_skip_preserves_original(
        self,
        pipeline: OptimizationPipeline,
        mock_analyzer: AsyncMock,
    ) -> None:
        mock_analyzer.analyze.return_value = _make_report(0.85, "already great")
        result = await pipeline.run("s::t", "already great")
        assert result.original_description == "already great"
        assert result.optimized_description == "already great"


class TestPipelineGateRejection:
    async def test_gate_rejected(
        self,
        pipeline: OptimizationPipeline,
        mock_gate: MagicMock,
    ) -> None:
        mock_gate.evaluate.return_value = FullGateResult(
            passed=False,
            geo_result=GateResult(passed=False, reason="GEO decreased"),
            similarity_result=GateResult(passed=True, reason="ok", similarity=0.9),
        )
        result = await pipeline.run("s::t", "test")
        assert result.status == OptimizationStatus.GATE_REJECTED


class TestPipelineBatch:
    async def test_batch_optimize(self, pipeline: OptimizationPipeline) -> None:
        tools = [("s::t1", "desc 1"), ("s::t2", "desc 2"), ("s::t3", "desc 3")]
        results = await pipeline.run_batch(tools)
        assert len(results) == 3
        assert all(isinstance(r, OptimizedDescription) for r in results)


class TestPipelineEmptyDescription:
    async def test_empty_description(self, pipeline: OptimizationPipeline) -> None:
        result = await pipeline.run("s::t", "")
        assert isinstance(result, OptimizedDescription)

    async def test_none_description(self, pipeline: OptimizationPipeline) -> None:
        result = await pipeline.run("s::t", None)
        assert isinstance(result, OptimizedDescription)


def _make_report_with_tool_id(tool_id: str, desc: str, geo: float = 0.3) -> AnalysisReport:
    return AnalysisReport(
        tool_id=tool_id,
        original_description=desc,
        dimension_scores=[
            DimensionScore(dimension=d, score=geo, explanation="test") for d in ALL_DIMS
        ],
    )


async def test_run_with_tool_passes_context_to_optimizer() -> None:
    """Pipeline.run_with_tool() should build OptimizationContext from MCPTool and pass it."""
    tool = MCPTool(
        server_id="slack",
        tool_name="DELETE_COMMENT",
        tool_id="slack::DELETE_COMMENT",
        description="Deletes a comment.",
        input_schema={"type": "object", "properties": {"id": {"type": "string"}}},
    )
    sibling_tools = [
        MCPTool(
            server_id="slack",
            tool_name="ADD_COMMENT",
            tool_id="slack::ADD_COMMENT",
            description="Adds a comment.",
        ),
    ]

    analyzer = AsyncMock()
    analyzer.analyze.return_value = _make_report_with_tool_id(
        "slack::DELETE_COMMENT", "Deletes a comment.", 0.3
    )

    optimizer = AsyncMock()
    optimizer.optimize.return_value = {
        "optimized_description": "Deletes a comment. Requires `id` parameter.",
        "search_description": "delete comment slack",
    }

    embedder = AsyncMock()
    embedder.embed_one.return_value = np.ones(10)

    gate = MagicMock()
    gate.evaluate.return_value = FullGateResult(
        passed=True,
        geo_result=GateResult(passed=True, reason="ok"),
        similarity_result=GateResult(passed=True, reason="ok", similarity=0.95),
    )

    pipeline = OptimizationPipeline(
        analyzer=analyzer,
        optimizer=optimizer,
        embedder=embedder,
        gate=gate,
    )

    result = await pipeline.run_with_tool(tool, sibling_tools=sibling_tools)

    assert result.status == OptimizationStatus.SUCCESS
    # Verify optimizer was called with context
    call_args = optimizer.optimize.call_args
    context = call_args.kwargs.get("context") or (
        call_args.args[1] if len(call_args.args) > 1 else None
    )
    assert context is not None
    assert context.input_schema == tool.input_schema
    assert len(context.sibling_tools) == 1


async def test_pipeline_rejects_hallucinated_params() -> None:
    """Pipeline should reject optimization that hallucinates parameters."""
    tool = MCPTool(
        server_id="test",
        tool_name="tool1",
        tool_id="test::tool1",
        description="A test tool.",
        input_schema={
            "type": "object",
            "properties": {"real_param": {"type": "string"}},
        },
    )

    analyzer = AsyncMock()
    analyzer.analyze.return_value = _make_report_with_tool_id("test::tool1", "A test tool.", 0.3)

    optimizer = AsyncMock()
    # LLM hallucinates a `query` parameter
    optimizer.optimize.return_value = {
        "optimized_description": "A test tool. Accepts `query` string and `limit` integer.",
        "search_description": "test tool",
    }

    embedder = AsyncMock()
    embedder.embed_one.return_value = np.ones(10)

    from description_optimizer.quality_gate import QualityGate

    gate = QualityGate(min_similarity=0.0)  # Relax similarity to isolate hallucination gate

    pipeline = OptimizationPipeline(
        analyzer=analyzer,
        optimizer=optimizer,
        embedder=embedder,
        gate=gate,
    )

    result = await pipeline.run_with_tool(tool, sibling_tools=[])
    assert result.status == OptimizationStatus.GATE_REJECTED
    assert "hallucinated" in result.skip_reason.lower() or "Hallucinated" in result.skip_reason


async def test_run_with_tool_batch() -> None:
    """run_batch_with_tools should process a list of (MCPTool, siblings) tuples."""
    tool = MCPTool(
        server_id="test",
        tool_name="tool1",
        tool_id="test::tool1",
        description="Tool 1.",
    )

    analyzer = AsyncMock()
    analyzer.analyze.return_value = _make_report_with_tool_id("test::tool1", "Tool 1.", 0.3)

    optimizer = AsyncMock()
    optimizer.optimize.return_value = {
        "optimized_description": "Improved Tool 1.",
        "search_description": "tool 1 search",
    }

    embedder = AsyncMock()
    embedder.embed_one.return_value = np.ones(10)

    gate = MagicMock()
    gate.evaluate.return_value = FullGateResult(
        passed=True,
        geo_result=GateResult(passed=True, reason="ok"),
        similarity_result=GateResult(passed=True, reason="ok", similarity=0.95),
    )

    pipeline = OptimizationPipeline(
        analyzer=analyzer,
        optimizer=optimizer,
        embedder=embedder,
        gate=gate,
    )

    results = await pipeline.run_batch_with_tools([(tool, [])])
    assert len(results) == 1
    assert results[0].status == OptimizationStatus.SUCCESS
