"""GT 도구에 대한 grounded description optimization.

P@1 A/B 평가를 위해 GT에 존재하는 도구만 선별하여 최적화.

Usage:
    PYTHONPATH=src uv run python scripts/optimize_gt_tools.py
"""

from __future__ import annotations

import asyncio
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

GT_PATH = Path("data/ground_truth/seed_set.jsonl")
RAW_DATA = Path("data/raw/servers.jsonl")
OUTPUT_PATH = Path("data/verification/gt_optimized_descriptions.jsonl")


def load_gt_tool_ids() -> set[str]:
    """GT에서 unique correct_tool_id 추출."""
    tool_ids: set[str] = set()
    with open(GT_PATH) as f:
        for line in f:
            entry = json.loads(line.strip())
            tool_ids.add(entry["correct_tool_id"])
    return tool_ids


def load_pool() -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """servers.jsonl에서 tool_id -> tool_data, server_id -> tools 매핑."""
    tool_lookup: dict[str, dict] = {}
    server_tools: dict[str, list[dict]] = {}

    with open(RAW_DATA) as f:
        for line in f:
            server = json.loads(line.strip())
            sid = server["server_id"]
            tools: list[dict] = []
            for t in server.get("tools", []):
                tid = t["tool_id"]
                tool_data = {
                    "tool_id": tid,
                    "server_id": sid,
                    "tool_name": t["tool_name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("input_schema"),
                }
                tool_lookup[tid] = tool_data
                tools.append(tool_data)
            server_tools[sid] = tools

    return tool_lookup, server_tools


async def main() -> None:
    gt_tool_ids = load_gt_tool_ids()
    tool_lookup, server_tools = load_pool()

    # GT에서 pool에 존재하는 도구만 선별
    available = sorted(tid for tid in gt_tool_ids if tid in tool_lookup)
    missing = gt_tool_ids - set(available)
    logger.info(
        f"GT tools: {len(gt_tool_ids)}, "
        f"Available in pool: {len(available)}, "
        f"Missing: {len(missing)}"
    )
    if missing:
        logger.warning(f"Missing tools (not in pool): {sorted(missing)}")

    # Pipeline 구성
    settings = Settings()
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    embedder = OpenAIEmbedder(api_key=settings.openai_api_key)
    analyzer = HeuristicAnalyzer()
    optimizer = LLMDescriptionOptimizer(client=openai_client)
    gate = QualityGate(min_similarity=0.75)
    pipeline = OptimizationPipeline(
        analyzer=analyzer,
        optimizer=optimizer,
        embedder=embedder,
        gate=gate,
    )

    # 최적화 실행
    results: list[dict] = []
    for i, tid in enumerate(available):
        tool_data = tool_lookup[tid]
        sid = tool_data["server_id"]

        tool = MCPTool(
            tool_id=tid,
            server_id=sid,
            tool_name=tool_data["tool_name"],
            description=tool_data["description"],
            input_schema=tool_data.get("input_schema"),
        )

        siblings = [
            MCPTool(
                tool_id=s["tool_id"],
                server_id=s["server_id"],
                tool_name=s["tool_name"],
                description=s.get("description", ""),
                input_schema=s.get("input_schema"),
            )
            for s in server_tools[sid]
            if s["tool_id"] != tid
        ]

        logger.info(f"Optimizing [{i + 1}/{len(available)}]: {tid}")
        result = await pipeline.run_with_tool(tool, sibling_tools=siblings)

        entry = {
            "tool_id": tid,
            "original_description": tool.description,
            "optimized_description": result.optimized_description,
            "retrieval_description": result.retrieval_description,
            "geo_score_before": result.geo_score_before,
            "geo_score_after": result.geo_score_after,
            "status": result.status.value,
            "skip_reason": result.skip_reason,
            "improvement": (result.geo_score_after or 0) - (result.geo_score_before or 0),
        }
        results.append(entry)

    # 결과 저장
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 요약
    success = sum(1 for r in results if r["status"] == "success")
    rejected = sum(1 for r in results if r["status"] == "gate_rejected")
    logger.info(
        f"Results: {success} success, {rejected} gate_rejected / {len(results)} total"
    )
    logger.info(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
