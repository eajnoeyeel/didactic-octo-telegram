"""Tests for scripts/run_e0.py — E0 experiment CLI & helpers."""

import json
import sys
from pathlib import Path

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import pytest
from run_e0 import _load_pool_server_ids


class TestLoadPoolServerIds:
    """Test deterministic server subset selection."""

    def _write_pool(self, tmp_path: Path, server_ids: list[str]) -> Path:
        """Write a minimal JSONL pool file."""
        pool_path = tmp_path / "pool.jsonl"
        lines = [json.dumps({"server_id": sid, "name": sid, "tools": []}) for sid in server_ids]
        pool_path.write_text("\n".join(lines))
        return pool_path

    def test_no_pool_size_returns_all_sorted(self, tmp_path: Path) -> None:
        pool_path = self._write_pool(tmp_path, ["charlie", "alpha", "bravo"])
        result = _load_pool_server_ids(pool_path, pool_size=None)
        assert result == ["alpha", "bravo", "charlie"]

    def test_pool_size_returns_first_n_sorted(self, tmp_path: Path) -> None:
        pool_path = self._write_pool(tmp_path, ["delta", "charlie", "alpha", "bravo"])
        result = _load_pool_server_ids(pool_path, pool_size=2)
        assert result == ["alpha", "bravo"]

    def test_pool_size_exceeding_total_returns_all(self, tmp_path: Path) -> None:
        pool_path = self._write_pool(tmp_path, ["bravo", "alpha"])
        result = _load_pool_server_ids(pool_path, pool_size=999)
        assert result == ["alpha", "bravo"]

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            _load_pool_server_ids(Path("/nonexistent/pool.jsonl"))
