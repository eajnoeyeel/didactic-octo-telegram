"""CLI script to optimize MCP tool descriptions with grounded optimization.

Usage:
    uv run python scripts/optimize_descriptions.py
    uv run python scripts/optimize_descriptions.py --input data/raw/servers.jsonl
    uv run python scripts/optimize_descriptions.py --dry-run
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loguru import logger
from openai import AsyncOpenAI

from config import Settings
from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import OptimizationStatus
from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer
from description_optimizer.pipeline import OptimizationPipeline
from description_optimizer.quality_gate import QualityGate
from embedding.openai_embedder import OpenAIEmbedder
from models import MCPTool


def load_tools_with_siblings(input_path: Path) -> list[tuple[MCPTool, list[MCPTool]]]:
    """Load MCPTool objects grouped by server for sibling context."""
    tools_with_siblings: list[tuple[MCPTool, list[MCPTool]]] = []

    with open(input_path) as f:
        for line in f:
            server = json.loads(line.strip())
            server_tools = []
            for t in server.get("tools", []):
                tool = MCPTool(
                    server_id=server["server_id"],
                    tool_name=t["tool_name"],
                    tool_id=f"{server['server_id']}::{t['tool_name']}",
                    description=t.get("description"),
                    input_schema=t.get("input_schema"),
                )
                server_tools.append(tool)

            for tool in server_tools:
                siblings = [s for s in server_tools if s.tool_id != tool.tool_id]
                tools_with_siblings.append((tool, siblings))

    return tools_with_siblings


async def main(args: argparse.Namespace) -> None:
    settings = Settings()
    input_path = Path(args.input)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return

    tools_with_siblings = load_tools_with_siblings(input_path)
    logger.info(f"Loaded {len(tools_with_siblings)} tools from {input_path}")

    if args.dry_run:
        analyzer = HeuristicAnalyzer()
        for tool, _ in tools_with_siblings:
            report = await analyzer.analyze(tool.tool_id, tool.description or "")
            weak = report.weak_dimensions()
            has_schema = "yes" if tool.input_schema else "no"
            weak_str = ", ".join(weak)
            logger.info(
                f"{tool.tool_id}: GEO={report.geo_score:.3f} "
                f"schema={has_schema} weak=[{weak_str}]"
            )
        return

    # Full pipeline with grounded optimization
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    analyzer = HeuristicAnalyzer()
    optimizer = LLMDescriptionOptimizer(client=openai_client)
    embedder = OpenAIEmbedder(api_key=settings.openai_api_key)
    gate = QualityGate(min_similarity=0.85)
    pipeline = OptimizationPipeline(
        analyzer=analyzer,
        optimizer=optimizer,
        embedder=embedder,
        gate=gate,
        skip_threshold=args.skip_threshold,
    )

    results = await pipeline.run_batch_with_tools(tools_with_siblings)

    # Summary
    success = sum(1 for r in results if r.status == OptimizationStatus.SUCCESS)
    skipped = sum(1 for r in results if r.status == OptimizationStatus.SKIPPED)
    failed = sum(1 for r in results if r.status == OptimizationStatus.FAILED)
    rejected = sum(1 for r in results if r.status == OptimizationStatus.GATE_REJECTED)

    logger.info(
        f"Optimization complete: {success} success, {skipped} skipped, "
        f"{failed} failed, {rejected} gate-rejected"
    )

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for r in results:
            f.write(r.model_dump_json() + "\n")

    logger.info(f"Results saved to {output_path}")

    if success > 0:
        avg_improvement = (
            sum(r.improvement for r in results if r.status == OptimizationStatus.SUCCESS) / success
        )
        logger.info(f"Average GEO improvement: +{avg_improvement:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize MCP tool descriptions (grounded)")
    parser.add_argument("--input", default="data/raw/servers.jsonl")
    parser.add_argument("--output", default="data/optimized/descriptions.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="Only analyze, don't optimize")
    parser.add_argument("--skip-threshold", type=float, default=0.75)
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
