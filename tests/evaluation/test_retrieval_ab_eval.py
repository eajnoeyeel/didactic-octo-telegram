"""Tests for retrieval A/B evaluation helpers."""

from __future__ import annotations

import json

import pytest

from scripts.run_retrieval_ab_eval import load_optimized


class TestLoadOptimized:
    @pytest.mark.asyncio
    async def test_prefers_retrieval_description(self, tmp_path) -> None:
        path = tmp_path / "optimized.jsonl"
        rows = [
            {
                "tool_id": "srv::tool",
                "status": "success",
                "optimized_description": "human readable description",
                "retrieval_description": "dense retrieval text",
                "search_description": "legacy search text",
            }
        ]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

        loaded = await load_optimized(path)
        assert loaded == {"srv::tool": "dense retrieval text"}

    @pytest.mark.asyncio
    async def test_falls_back_to_legacy_search_description(self, tmp_path) -> None:
        path = tmp_path / "optimized.jsonl"
        rows = [
            {
                "tool_id": "srv::tool",
                "status": "success",
                "optimized_description": "human readable description",
                "search_description": "legacy search text",
            }
        ]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

        loaded = await load_optimized(path)
        assert loaded == {"srv::tool": "legacy search text"}
