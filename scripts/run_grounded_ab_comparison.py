"""Grounded vs Ungrounded A/B Comparison (fluency-based).

Re-runs BOTH ungrounded and grounded optimizations on the same 30-tool sample,
scoring all results with the current HeuristicAnalyzer (fluency instead of boundary).

Usage:
    PYTHONPATH=src uv run python scripts/run_grounded_ab_comparison.py
"""

import asyncio
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loguru import logger
from openai import AsyncOpenAI

from config import Settings
from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer
from description_optimizer.pipeline import OptimizationPipeline
from description_optimizer.quality_gate import QualityGate
from embedding.openai_embedder import OpenAIEmbedder
from models import MCPTool

VERIFICATION_DIR = Path("data/verification")
RAW_DATA = Path("data/raw/servers.jsonl")
SAMPLE_FILE = VERIFICATION_DIR / "sample_tools.json"
UNGROUNDED_RESULTS = VERIFICATION_DIR / "optimization_results.jsonl"
GROUNDED_RESULTS = VERIFICATION_DIR / "grounded_optimization_results.jsonl"

DIMS = ["clarity", "disambiguation", "parameter_coverage", "fluency", "stats", "precision"]


def load_tool_schemas() -> dict[str, dict]:
    """Build tool_id -> {input_schema, server_tools} lookup from raw data."""
    servers: dict[str, list[dict]] = {}
    tool_schemas: dict[str, dict] = {}

    with open(RAW_DATA) as f:
        for line in f:
            server = json.loads(line.strip())
            sid = server["server_id"]
            server_tools = []
            for t in server.get("tools", []):
                tid = f"{sid}::{t['tool_name']}"
                tool_schemas[tid] = {
                    "input_schema": t.get("input_schema"),
                    "server_id": sid,
                    "tool_name": t["tool_name"],
                }
                server_tools.append({
                    "tool_id": tid,
                    "tool_name": t["tool_name"],
                    "description": t.get("description") or "",
                    "input_schema": t.get("input_schema"),
                })
            servers[sid] = server_tools

    # Attach sibling info
    for tid, info in tool_schemas.items():
        sid = info["server_id"]
        info["siblings"] = [
            t for t in servers.get(sid, []) if t["tool_id"] != tid
        ]

    return tool_schemas


async def rescore_originals(sample: list[dict], analyzer: HeuristicAnalyzer) -> list[dict]:
    """Re-score all original descriptions with the current analyzer (fluency-based)."""
    for tool_data in sample:
        report = await analyzer.analyze(tool_data["tool_id"], tool_data["description"])
        tool_data["dimension_scores_original"] = {
            s.dimension: round(s.score, 4) for s in report.dimension_scores
        }
        tool_data["geo_score_original"] = round(report.geo_score, 4)
    return sample


async def run_optimization(
    sample: list[dict],
    tool_schemas: dict[str, dict],
    pipeline: OptimizationPipeline,
    analyzer: HeuristicAnalyzer,
    *,
    grounded: bool,
) -> list[dict]:
    """Run optimization on sample tools.

    Args:
        grounded: If True, use run_with_tool() with schema+siblings.
                  If False, use run() (legacy, no context).
    """
    label = "Grounded" if grounded else "Ungrounded"
    results = []

    for i, tool_data in enumerate(sample):
        tid = tool_data["tool_id"]
        schema_info = tool_schemas.get(tid, {})

        if grounded:
            mcp_tool = MCPTool(
                server_id=tool_data["server_id"],
                tool_name=tool_data["tool_name"],
                tool_id=tid,
                description=tool_data["description"],
                input_schema=schema_info.get("input_schema"),
            )
            sibling_tools = [
                MCPTool(
                    server_id=tool_data["server_id"],
                    tool_name=sib["tool_name"],
                    tool_id=sib["tool_id"],
                    description=sib["description"],
                    input_schema=sib.get("input_schema"),
                )
                for sib in schema_info.get("siblings", [])[:8]
            ]
            logger.info(
                f"[{i + 1}/{len(sample)}] {label} optimizing {tid} "
                f"(schema={'yes' if mcp_tool.input_schema else 'no'}, "
                f"siblings={len(sibling_tools)})"
            )
            result = await pipeline.run_with_tool(mcp_tool, sibling_tools=sibling_tools)
        else:
            logger.info(f"[{i + 1}/{len(sample)}] {label} optimizing {tid}")
            result = await pipeline.run(tid, tool_data["description"])

        record = json.loads(result.model_dump_json())
        record["dimension_scores_original"] = tool_data["dimension_scores_original"]

        if result.status.value == "success":
            report_after = await analyzer.analyze(tid, result.optimized_description)
            record["dimension_scores_after"] = {
                s.dimension: round(s.score, 4) for s in report_after.dimension_scores
            }
        else:
            record["dimension_scores_after"] = tool_data["dimension_scores_original"]

        results.append(record)

    return results


def print_comparison_report(ungrounded: list[dict], grounded: list[dict]) -> None:
    # NOTE: print() used intentionally for CLI report output (not logging)
    def summarize(results: list[dict], label: str) -> dict:
        by_status: dict[str, int] = {}
        for r in results:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1

        success = [r for r in results if r["status"] == "success"]
        improvements = (
            [r["geo_score_after"] - r["geo_score_before"] for r in success]
            if success
            else []
        )

        print(f"\n{'=' * 60}")
        print(f"  {label}")
        print(f"{'=' * 60}")
        print(f"  Total: {len(results)}")
        for s, c in sorted(by_status.items()):
            print(f"    {s}: {c}")

        if success:
            avg_imp = sum(improvements) / len(improvements)
            print(f"\n  Success: {len(success)}/{len(results)}")
            print(f"  Avg GEO improvement: {avg_imp:+.4f}")
            print(f"  Min: {min(improvements):+.4f}")
            print(f"  Max: {max(improvements):+.4f}")

            print(f"\n  {'Dimension':25s} {'Before':>8s} {'After':>8s} {'Delta':>8s}")
            print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8}")
            dim_deltas = {}
            for dim in DIMS:
                befores = [r.get("dimension_scores_original", {}).get(dim, 0) for r in success]
                afters = [r.get("dimension_scores_after", {}).get(dim, 0) for r in success]
                avg_b = sum(befores) / len(befores)
                avg_a = sum(afters) / len(afters)
                delta = avg_a - avg_b
                dim_deltas[dim] = delta
                print(f"  {dim:25s} {avg_b:8.4f} {avg_a:8.4f} {delta:+8.4f}")

            return {
                "avg_improvement": avg_imp,
                "success_count": len(success),
                "dim_deltas": dim_deltas,
            }
        return {"avg_improvement": 0, "success_count": 0, "dim_deltas": {}}

    ug_stats = summarize(ungrounded, "UNGROUNDED (baseline)")
    gr_stats = summarize(grounded, "GROUNDED (new)")

    # Head-to-head comparison
    print(f"\n{'=' * 60}")
    print("  HEAD-TO-HEAD COMPARISON")
    print(f"{'=' * 60}")

    if ug_stats["success_count"] > 0 and gr_stats["success_count"] > 0:
        diff = gr_stats["avg_improvement"] - ug_stats["avg_improvement"]
        print("\n  Avg GEO improvement:")
        print(f"    Ungrounded: {ug_stats['avg_improvement']:+.4f}")
        print(f"    Grounded:   {gr_stats['avg_improvement']:+.4f}")
        verdict = "grounded better" if diff > 0 else "ungrounded better" if diff < 0 else "equal"
        print(f"    Difference: {diff:+.4f} ({verdict})")

        print("\n  Per-dimension delta comparison:")
        print(f"  {'Dimension':25s} {'Ungrounded':>12s} {'Grounded':>12s} {'Winner':>10s}")
        print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*10}")
        for dim in DIMS:
            ug_d = ug_stats["dim_deltas"].get(dim, 0)
            gr_d = gr_stats["dim_deltas"].get(dim, 0)
            winner = "grounded" if gr_d > ug_d else "ungrounded" if ug_d > gr_d else "tie"
            print(f"  {dim:25s} {ug_d:+12.4f} {gr_d:+12.4f} {winner:>10s}")

    # Per-tool comparison for shared successes
    ug_by_id = {r["tool_id"]: r for r in ungrounded if r["status"] == "success"}
    gr_by_id = {r["tool_id"]: r for r in grounded if r["status"] == "success"}
    shared = set(ug_by_id.keys()) & set(gr_by_id.keys())

    if shared:
        print(f"\n  Per-tool comparison (shared successes: {len(shared)}):")
        print(f"  {'Tool ID':50s} {'UG GEO':>8s} {'GR GEO':>8s} {'Winner':>10s}")
        print(f"  {'-'*50} {'-'*8} {'-'*8} {'-'*10}")
        ug_wins = gr_wins = ties = 0
        for tid in sorted(shared):
            ug_geo = ug_by_id[tid]["geo_score_after"]
            gr_geo = gr_by_id[tid]["geo_score_after"]
            if gr_geo > ug_geo:
                winner = "grounded"
                gr_wins += 1
            elif ug_geo > gr_geo:
                winner = "ungrounded"
                ug_wins += 1
            else:
                winner = "tie"
                ties += 1
            short_id = tid[:48] + ".." if len(tid) > 50 else tid
            print(f"  {short_id:50s} {ug_geo:8.4f} {gr_geo:8.4f} {winner:>10s}")

        print(f"\n  Score: Grounded {gr_wins} — Ungrounded {ug_wins} — Tie {ties}")

    # Check for regressions
    gr_rejected = [r for r in grounded if r["status"] == "gate_rejected"]
    ug_rejected = [r for r in ungrounded if r["status"] == "gate_rejected"]
    print(f"\n  Gate rejections: Ungrounded={len(ug_rejected)}, Grounded={len(gr_rejected)}")

    if gr_rejected:
        print("\n  Grounded rejection reasons:")
        for r in gr_rejected:
            print(f"    {r['tool_id'][:50]}: {r.get('skip_reason', 'N/A')[:80]}")

    if ug_rejected:
        print("\n  Ungrounded rejection reasons:")
        for r in ug_rejected:
            print(f"    {r['tool_id'][:50]}: {r.get('skip_reason', 'N/A')[:80]}")


async def main() -> None:
    settings = Settings()
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    analyzer = HeuristicAnalyzer()
    optimizer = LLMDescriptionOptimizer(client=openai_client)
    embedder = OpenAIEmbedder(api_key=settings.openai_api_key)
    gate = QualityGate(min_similarity=0.75)
    pipeline = OptimizationPipeline(
        analyzer=analyzer,
        optimizer=optimizer,
        embedder=embedder,
        gate=gate,
        skip_threshold=0.75,
    )

    with open(SAMPLE_FILE) as f:
        sample = json.load(f)

    tool_schemas = load_tool_schemas()

    # Step 1: Re-score originals with current analyzer (fluency-based)
    logger.info("Re-scoring original descriptions with fluency-based analyzer...")
    sample = await rescore_originals(sample, analyzer)

    # Step 2: Run ungrounded optimization (no context)
    logger.info("=" * 60)
    logger.info("Running UNGROUNDED optimization...")
    logger.info("=" * 60)
    ungrounded = await run_optimization(
        copy.deepcopy(sample), tool_schemas, pipeline, analyzer, grounded=False
    )
    with open(UNGROUNDED_RESULTS, "w") as f:
        for r in ungrounded:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    logger.info(f"Ungrounded results saved to {UNGROUNDED_RESULTS}")

    # Step 3: Run grounded optimization (with schema + siblings)
    logger.info("=" * 60)
    logger.info("Running GROUNDED optimization...")
    logger.info("=" * 60)
    grounded = await run_optimization(
        copy.deepcopy(sample), tool_schemas, pipeline, analyzer, grounded=True
    )
    with open(GROUNDED_RESULTS, "w") as f:
        for r in grounded:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    logger.info(f"Grounded results saved to {GROUNDED_RESULTS}")

    # Step 4: Print comparison
    print_comparison_report(ungrounded, grounded)

    # Save updated sample with fluency-based scores
    with open(SAMPLE_FILE, "w") as f:
        json.dump(sample, f, indent=2, ensure_ascii=False)
    logger.info(f"Updated sample scores saved to {SAMPLE_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
