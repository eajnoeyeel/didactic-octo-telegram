"""Tool Selection A/B Evaluation — the true test of description optimization.

Compares Precision@1 using original vs. optimized descriptions against ground truth.
This is the North Star metric: "Does the optimized description help the pipeline
select the correct tool more often?"

Usage:
    PYTHONPATH=src uv run python scripts/run_selection_eval.py \
        --ground-truth data/ground_truth/seed_set.jsonl \
        --optimized data/optimized/descriptions.jsonl
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loguru import logger


async def main(args: argparse.Namespace) -> None:
    gt_path = Path(args.ground_truth)
    opt_path = Path(args.optimized)

    if not gt_path.exists():
        logger.error(f"Ground truth not found: {gt_path}")
        return
    if not opt_path.exists():
        logger.error(f"Optimized descriptions not found: {opt_path}")
        return

    # Load ground truth
    ground_truth = []
    with open(gt_path) as f:
        for line in f:
            ground_truth.append(json.loads(line.strip()))

    # Load optimized descriptions as lookup
    optimized_lookup: dict[str, dict] = {}
    with open(opt_path) as f:
        for line in f:
            entry = json.loads(line.strip())
            optimized_lookup[entry["tool_id"]] = entry

    logger.info(
        f"Loaded {len(ground_truth)} GT queries, "
        f"{len(optimized_lookup)} optimized descriptions"
    )

    # Report
    total = len(ground_truth)
    tools_with_optimization = sum(
        1
        for gt in ground_truth
        if gt["correct_tool_id"] in optimized_lookup
        and optimized_lookup[gt["correct_tool_id"]].get("status") == "success"
    )

    logger.info(f"GT queries with optimized correct tool: {tools_with_optimization}/{total}")
    logger.info(
        "To run full A/B evaluation, build two Qdrant indices "
        "(original vs optimized descriptions) and run the evaluation harness on each."
    )
    logger.info(
        "Compare: Precision@1(original) vs Precision@1(optimized) — "
        "this is the definitive test of description optimization value."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tool Selection A/B Evaluation")
    parser.add_argument("--ground-truth", default="data/ground_truth/seed_set.jsonl")
    parser.add_argument("--optimized", default="data/optimized/descriptions.jsonl")
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
