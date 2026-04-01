"""Tests for run_retrieval_ab_eval.py — load functions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Import from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from run_retrieval_ab_eval import load_optimized, load_search_descriptions


class TestLoadOptimized:
    @pytest.fixture()
    def opt_jsonl(self, tmp_path: Path) -> Path:
        path = tmp_path / "opt.jsonl"
        entries = [
            {
                "tool_id": "server1::tool_a",
                "status": "success",
                "optimized_description": "Optimized A",
                "search_description": "Search A",
            },
            {
                "tool_id": "server1::tool_b",
                "status": "error",
                "optimized_description": "Should be skipped",
            },
            {
                "tool_id": "server2::tool_c",
                "status": "success",
                "optimized_description": "Optimized C",
                "search_description": "Search C",
            },
        ]
        path.write_text("\n".join(json.dumps(e) for e in entries))
        return path

    @pytest.mark.asyncio()
    async def test_load_optimized_success_only(self, opt_jsonl: Path) -> None:
        result = await load_optimized(opt_jsonl)
        assert len(result) == 2
        assert result["server1::tool_a"] == "Optimized A"
        assert result["server2::tool_c"] == "Optimized C"

    @pytest.mark.asyncio()
    async def test_load_optimized_skips_error(self, opt_jsonl: Path) -> None:
        result = await load_optimized(opt_jsonl)
        assert "server1::tool_b" not in result

    @pytest.mark.asyncio()
    async def test_load_optimized_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("")
        result = await load_optimized(path)
        assert result == {}


class TestLoadSearchDescriptions:
    @pytest.fixture()
    def opt_jsonl(self, tmp_path: Path) -> Path:
        path = tmp_path / "opt.jsonl"
        entries = [
            {
                "tool_id": "server1::tool_a",
                "status": "success",
                "optimized_description": "Optimized A",
                "search_description": "Search A short",
            },
            {
                "tool_id": "server1::tool_b",
                "status": "error",
                "search_description": "Should be skipped (error)",
            },
            {
                "tool_id": "server2::tool_c",
                "status": "success",
                "optimized_description": "Optimized C",
                # no search_description field
            },
            {
                "tool_id": "server2::tool_d",
                "status": "success",
                "optimized_description": "Optimized D",
                "search_description": "Search D short",
            },
        ]
        path.write_text("\n".join(json.dumps(e) for e in entries))
        return path

    @pytest.mark.asyncio()
    async def test_load_search_descriptions_success_only(self, opt_jsonl: Path) -> None:
        result = await load_search_descriptions(opt_jsonl)
        assert len(result) == 2
        assert result["server1::tool_a"] == "Search A short"
        assert result["server2::tool_d"] == "Search D short"

    @pytest.mark.asyncio()
    async def test_load_search_descriptions_skips_error(self, opt_jsonl: Path) -> None:
        result = await load_search_descriptions(opt_jsonl)
        assert "server1::tool_b" not in result

    @pytest.mark.asyncio()
    async def test_load_search_descriptions_skips_missing_field(self, opt_jsonl: Path) -> None:
        result = await load_search_descriptions(opt_jsonl)
        assert "server2::tool_c" not in result

    @pytest.mark.asyncio()
    async def test_load_search_descriptions_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("")
        result = await load_search_descriptions(path)
        assert result == {}
