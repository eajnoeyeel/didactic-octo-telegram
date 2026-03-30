"""Comparison verification script for Description Optimizer.

Runs the full optimization pipeline on a representative sample of MCP tools,
generates before/after GEO score comparisons, and produces a human-readable report.

Usage:
    # Phase 1: Sample selection + dry-run analysis only (no API key needed)
    PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase sample

    # Phase 2: Full optimization (requires OPENAI_API_KEY in .env)
    PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase optimize

    # Phase 3: Generate comparison report from saved results
    PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase report

    # All phases at once
    PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase all
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from loguru import logger

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from description_optimizer.analyzer.heuristic import HeuristicAnalyzer

SAMPLE_SIZE = 30
VERIFICATION_DIR = Path("data/verification")
RAW_DATA = Path("data/raw/servers.jsonl")
SAMPLE_FILE = VERIFICATION_DIR / "sample_tools.json"


def load_all_tools() -> list[dict]:
    """Load all tools from servers.jsonl with server context."""
    tools = []
    with open(RAW_DATA) as f:
        for line in f:
            server = json.loads(line.strip())
            for tool in server.get("tools", []):
                tool_id = f"{server['server_id']}::{tool['tool_name']}"
                tools.append(
                    {
                        "tool_id": tool_id,
                        "server_id": server["server_id"],
                        "tool_name": tool["tool_name"],
                        "description": tool.get("description") or "",
                        "input_schema": tool.get("input_schema"),
                    }
                )
    return tools


async def select_representative_sample(tools: list[dict]) -> list[dict]:
    """Select SAMPLE_SIZE tools via stratified sampling by GEO score tier.

    Tiers:
        - low:    GEO < 0.10  (majority of tools — select 10)
        - medium: 0.10 <= GEO < 0.30  (select 10)
        - high:   GEO >= 0.30  (select 10, or fewer if not enough)
    """
    import random

    random.seed(42)  # Reproducible

    analyzer = HeuristicAnalyzer()
    scored: list[tuple[dict, float]] = []

    for tool in tools:
        report = await analyzer.analyze(tool["tool_id"], tool["description"])
        tool["geo_score_original"] = round(report.geo_score, 4)
        tool["dimension_scores_original"] = {
            s.dimension: round(s.score, 4) for s in report.dimension_scores
        }
        scored.append((tool, report.geo_score))

    # Stratify
    low = [t for t, g in scored if g < 0.10]
    medium = [t for t, g in scored if 0.10 <= g < 0.30]
    high = [t for t, g in scored if g >= 0.30]

    logger.info(f"Distribution: low={len(low)}, medium={len(medium)}, high={len(high)}")

    # Sample 10 from each tier (or all if fewer)
    sample = []
    sample.extend(random.sample(low, min(10, len(low))))
    sample.extend(random.sample(medium, min(10, len(medium))))
    sample.extend(random.sample(high, min(10, len(high))))

    logger.info(f"Selected {len(sample)} tools for verification")
    return sample


async def phase_sample():
    """Phase 1: Select sample and save to file."""
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    tools = load_all_tools()
    logger.info(f"Loaded {len(tools)} tools from {RAW_DATA}")

    sample = await select_representative_sample(tools)

    with open(SAMPLE_FILE, "w") as f:
        json.dump(sample, f, indent=2, ensure_ascii=False)

    logger.info(f"Sample saved to {SAMPLE_FILE}")

    # Print summary
    print("\n=== SAMPLE SELECTION SUMMARY ===")
    print(f"Total tools: {len(tools)}")
    print(f"Sample size: {len(sample)}")
    print("\nGEO Score Distribution in Sample:")
    for tool in sorted(sample, key=lambda t: t["geo_score_original"]):
        print(f"  {tool['geo_score_original']:.4f}  {tool['tool_id'][:60]}")


async def phase_optimize():
    """Phase 2: Run full optimization pipeline on sample tools."""
    from openai import AsyncOpenAI

    from config import Settings
    from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer
    from description_optimizer.pipeline import OptimizationPipeline
    from description_optimizer.quality_gate import QualityGate
    from embedding.openai_embedder import OpenAIEmbedder

    if not SAMPLE_FILE.exists():
        logger.error(f"Sample file not found: {SAMPLE_FILE}. Run --phase sample first.")
        return

    with open(SAMPLE_FILE) as f:
        sample = json.load(f)

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
    )

    results_file = VERIFICATION_DIR / "optimization_results.jsonl"
    with open(results_file, "w") as f:
        for i, tool in enumerate(sample):
            logger.info(f"[{i + 1}/{len(sample)}] Optimizing {tool['tool_id']}")
            from models import MCPTool

            mcp_tool = MCPTool(
                server_id=tool["server_id"],
                tool_name=tool["tool_name"],
                tool_id=tool["tool_id"],
                description=tool["description"],
                input_schema=tool.get("input_schema"),
            )
            result = await pipeline.run_with_tool(mcp_tool, sibling_tools=[])
            # Enrich with original and after dimension scores
            record = json.loads(result.model_dump_json())
            record["dimension_scores_original"] = tool["dimension_scores_original"]
            # Re-analyze optimized description for per-dimension after scores
            if result.status.value == "success":
                report_after = await analyzer.analyze(
                    tool["tool_id"], result.optimized_description
                )
                record["dimension_scores_after"] = {
                    s.dimension: round(s.score, 4) for s in report_after.dimension_scores
                }
            else:
                record["dimension_scores_after"] = tool["dimension_scores_original"]
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()  # Write after each tool for crash safety

    logger.info(f"Results saved to {results_file}")

    # Quick summary
    results = []
    with open(results_file) as f:
        for line in f:
            results.append(json.loads(line.strip()))

    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    rejected = sum(1 for r in results if r["status"] == "gate_rejected")

    print("\n=== OPTIMIZATION SUMMARY ===")
    print(f"Success: {success}, Failed: {failed}, Gate Rejected: {rejected}")

    if success > 0:
        improvements = [
            r["geo_score_after"] - r["geo_score_before"]
            for r in results
            if r["status"] == "success"
        ]
        avg = sum(improvements) / len(improvements)
        print(f"Average GEO improvement: +{avg:.4f}")
        print(f"Min improvement: +{min(improvements):.4f}")
        print(f"Max improvement: +{max(improvements):.4f}")


async def phase_report():
    """Phase 3: Generate comparison report from optimization results."""
    results_file = VERIFICATION_DIR / "optimization_results.jsonl"
    if not results_file.exists():
        logger.error(f"Results file not found: {results_file}. Run --phase optimize first.")
        return

    results = []
    with open(results_file) as f:
        for line in f:
            results.append(json.loads(line.strip()))

    analyzer = HeuristicAnalyzer()

    # Re-analyze optimized descriptions to get per-dimension after scores
    for r in results:
        if r["status"] == "success":
            report_after = await analyzer.analyze(r["tool_id"], r["optimized_description"])
            r["dimension_scores_after"] = {
                s.dimension: round(s.score, 4) for s in report_after.dimension_scores
            }
        else:
            r["dimension_scores_after"] = r.get("dimension_scores_original", {})

    report_path = VERIFICATION_DIR / "comparison_report.md"
    with open(report_path, "w") as f:
        _write_report(f, results)

    logger.info(f"Report saved to {report_path}")
    print(f"\n=== Report generated: {report_path} ===")


def _write_report(f, results: list[dict]) -> None:
    """Write the full comparison report to a file handle."""
    dims = ["clarity", "disambiguation", "parameter_coverage", "fluency", "stats", "precision"]

    f.write("# Description Optimizer 비교 검증 리포트\n\n")
    f.write("> 생성 시각: 스크립트 실행 시점\n")
    f.write(f"> 샘플 크기: {len(results)} tools\n\n")

    # --- Section 1: Overall Summary ---
    f.write("## 1. 전체 요약\n\n")
    status_counts = {}
    for r in results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    f.write("| Status | Count |\n|--------|-------|\n")
    for status, count in sorted(status_counts.items()):
        f.write(f"| {status} | {count} |\n")

    success = [r for r in results if r["status"] == "success"]
    if success:
        improvements = [r["geo_score_after"] - r["geo_score_before"] for r in success]
        f.write(f"\n**성공 건수:** {len(success)}\n")
        f.write(f"**평균 GEO 개선:** +{sum(improvements) / len(improvements):.4f}\n")
        f.write(f"**최소 개선:** +{min(improvements):.4f}\n")
        f.write(f"**최대 개선:** +{max(improvements):.4f}\n\n")

    # --- Section 2: Dimension-Level Analysis ---
    f.write("## 2. 차원별 Before/After 분석\n\n")
    f.write("| Dimension | Avg Before | Avg After | Avg Δ | Improved% |\n")
    f.write("|-----------|-----------|----------|-------|----------|\n")

    for dim in dims:
        befores = []
        afters = []
        for r in success:
            b = r.get("dimension_scores_original", {}).get(dim, 0)
            a = r.get("dimension_scores_after", {}).get(dim, 0)
            befores.append(b)
            afters.append(a)

        if befores:
            avg_b = sum(befores) / len(befores)
            avg_a = sum(afters) / len(afters)
            delta = avg_a - avg_b
            improved_pct = sum(1 for b, a in zip(befores, afters) if a > b) / len(befores) * 100
            f.write(f"| {dim} | {avg_b:.4f} | {avg_a:.4f} | {delta:+.4f} | {improved_pct:.0f}% |\n")

    # --- Section 3: Per-Tool Side-by-Side ---
    f.write("\n## 3. Tool별 Side-by-Side 비교\n\n")

    for i, r in enumerate(results):
        f.write(f"### Tool {i + 1}: `{r['tool_id']}`\n\n")
        f.write(f"**Status:** {r['status']}\n")
        f.write(f"**GEO:** {r['geo_score_before']:.4f} → {r['geo_score_after']:.4f}")
        if r["status"] == "success":
            delta = r["geo_score_after"] - r["geo_score_before"]
            f.write(f" ({delta:+.4f})")
        f.write("\n\n")

        if r.get("skip_reason"):
            f.write(f"**Skip/Reject Reason:** {r['skip_reason']}\n\n")

        # Dimension comparison table
        f.write("| Dimension | Before | After | Δ |\n")
        f.write("|-----------|--------|-------|---|\n")
        for dim in dims:
            b = r.get("dimension_scores_original", {}).get(dim, 0)
            a = r.get("dimension_scores_after", {}).get(dim, 0)
            delta = a - b
            f.write(f"| {dim} | {b:.4f} | {a:.4f} | {delta:+.4f} |\n")

        f.write("\n**Original:**\n")
        f.write(f"```\n{r['original_description'][:500]}\n```\n\n")

        if r["status"] == "success":
            f.write("**Optimized:**\n")
            f.write(f"```\n{r['optimized_description'][:500]}\n```\n\n")
            f.write("**Retrieval Description:**\n")
            retrieval_text = r.get("retrieval_description") or r.get("search_description", "N/A")
            f.write(f"```\n{retrieval_text[:300]}\n```\n\n")

        f.write("---\n\n")

    # --- Section 4: Quality Gate Analysis ---
    f.write("## 4. Quality Gate 분석\n\n")
    rejected = [r for r in results if r["status"] == "gate_rejected"]
    failed = [r for r in results if r["status"] == "failed"]

    f.write(f"- **Gate Rejected:** {len(rejected)} tools\n")
    f.write(f"- **Failed (optimizer error):** {len(failed)} tools\n\n")

    if rejected:
        f.write("### Rejection Details\n\n")
        for r in rejected:
            f.write(f"- `{r['tool_id']}`: {r.get('skip_reason', 'N/A')}\n")

    if failed:
        f.write("\n### Failure Details\n\n")
        for r in failed:
            f.write(f"- `{r['tool_id']}`: {r.get('skip_reason', 'N/A')}\n")

    # --- Section 5: Verdict ---
    f.write("\n## 5. 검증 결론\n\n")
    f.write("아래 체크리스트를 사람이 직접 확인:\n\n")
    f.write("- [ ] 성공한 최적화의 GEO 개선이 양수인가?\n")
    f.write("- [ ] 6개 차원 중 최소 4개가 개선되었는가?\n")
    f.write("- [ ] 최적화된 설명이 원본의 의미를 보존하는가? (Section 3 side-by-side 확인)\n")
    f.write("- [ ] 최적화된 설명에 환각(hallucination)이 없는가?\n")
    f.write("- [ ] Quality Gate가 나쁜 최적화를 적절히 걸러냈는가?\n")
    f.write("- [ ] retrieval_description이 벡터 검색에 적합한 키워드를 포함하는가?\n")
    f.write("- [ ] retrieval_description의 길이가 적절한가? (15-60 words 권장)\n")


async def main(args: argparse.Namespace) -> None:
    if args.phase in ("sample", "all"):
        await phase_sample()
    if args.phase in ("optimize", "all"):
        await phase_optimize()
    if args.phase in ("report", "all"):
        await phase_report()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Description Optimizer Comparison Verification")
    parser.add_argument(
        "--phase",
        choices=["sample", "optimize", "report", "all"],
        default="all",
        help="Which phase to run",
    )
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
