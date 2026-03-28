"""CLI script to optimize MCP tool descriptions.

Usage:
    uv run python scripts/optimize_descriptions.py
    uv run python scripts/optimize_descriptions.py --input data/raw/servers.jsonl
    uv run python scripts/optimize_descriptions.py --dry-run
    uv run python scripts/optimize_descriptions.py --skip-threshold 0.8
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


async def main(args: argparse.Namespace) -> None:
    settings = Settings()
    input_path = Path(args.input)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return

    # Load servers and extract tools
    tools: list[tuple[str, str | None]] = []
    with open(input_path) as f:
        for line in f:
            server = json.loads(line.strip())
            for tool in server.get("tools", []):
                tool_id = f"{server['server_id']}::{tool['tool_name']}"
                tools.append((tool_id, tool.get("description")))

    logger.info(f"Loaded {len(tools)} tools from {input_path}")

    if args.dry_run:
        # Dry run: only analyze, don't optimize
        analyzer = HeuristicAnalyzer()
        for tool_id, desc in tools:
            report = await analyzer.analyze(tool_id, desc or "")
            weak = report.weak_dimensions()
            logger.info(f"{tool_id}: GEO={report.geo_score:.3f}, weak=[{', '.join(weak)}]")
        return

    # Full pipeline
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    analyzer = HeuristicAnalyzer()
    optimizer = LLMDescriptionOptimizer(client=openai_client)
    embedder = OpenAIEmbedder(client=openai_client)
    gate = QualityGate(min_similarity=0.85)
    pipeline = OptimizationPipeline(
        analyzer=analyzer,
        optimizer=optimizer,
        embedder=embedder,
        gate=gate,
        skip_threshold=args.skip_threshold,
    )

    results = await pipeline.run_batch(tools)

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

    # Print improvement summary
    if success > 0:
        avg_improvement = (
            sum(r.improvement for r in results if r.status == OptimizationStatus.SUCCESS) / success
        )
        logger.info(f"Average GEO improvement: +{avg_improvement:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize MCP tool descriptions")
    parser.add_argument("--input", default="data/raw/servers.jsonl")
    parser.add_argument("--output", default="data/optimized/descriptions.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="Only analyze, don't optimize")
    parser.add_argument("--skip-threshold", type=float, default=0.75)
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
