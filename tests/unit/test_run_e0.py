"""Tests for scripts/run_e0.py — E0 experiment CLI & helpers."""

import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import pytest
from run_e0 import (
    SWEEP_SIZES,
    _build_result_payload,
    _eval_result_to_dict,
    _format_results_table,
    _format_sweep_table,
    _load_pool_server_ids,
    _save_json,
)

from evaluation.metrics import EvalResult


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


def _make_eval_result(name: str = "FlatStrategy") -> EvalResult:
    """Minimal EvalResult for testing."""
    return EvalResult(
        strategy_name=name,
        n_queries=10,
        n_failed=0,
        k_used=10,
        precision_at_1=0.5,
        recall_at_k=0.7,
        mrr=0.6,
        ndcg_at_5=0.55,
        confusion_rate=0.1,
        ece=0.05,
        latency_p50=100.0,
        latency_p95=200.0,
        latency_p99=300.0,
        latency_mean=120.0,
    )


class TestEvalResultToDict:
    def test_serializes_metrics(self) -> None:
        result = _make_eval_result()
        d = _eval_result_to_dict(result)
        assert d["name"] == "FlatStrategy"
        assert d["metrics"]["precision_at_1"] == 0.5
        assert d["metrics"]["latency_p95"] == 200.0
        assert d["n_queries"] == 10

    def test_excludes_per_query(self) -> None:
        d = _eval_result_to_dict(_make_eval_result())
        assert "per_query" not in d
        assert "per_query" not in d.get("metrics", {})

    def test_none_values_preserved(self) -> None:
        result = EvalResult(
            strategy_name="Test",
            n_queries=1,
            n_failed=0,
            k_used=10,
            precision_at_1=0.0,
            recall_at_k=0.0,
            mrr=0.0,
            ndcg_at_5=0.0,
            confusion_rate=None,
            ece=None,
            latency_p50=0.0,
            latency_p95=0.0,
            latency_p99=0.0,
            latency_mean=0.0,
        )
        d = _eval_result_to_dict(result)
        assert d["metrics"]["confusion_rate"] is None
        assert d["metrics"]["ece"] is None

    def test_json_serializable(self) -> None:
        d = _eval_result_to_dict(_make_eval_result())
        json.dumps(d)  # Should not raise


class TestBuildResultPayload:
    def test_schema_structure(self) -> None:
        payload = _build_result_payload(
            experiment="E0",
            pool_size=308,
            top_k=10,
            results=[_make_eval_result()],
        )
        assert payload["experiment"] == "E0"
        assert "timestamp" in payload
        assert payload["config"]["pool_size"] == 308
        assert payload["config"]["top_k"] == 10
        assert payload["config"]["embedding_model"] == "text-embedding-3-large"
        assert payload["config"]["gt_sources"] == ["seed_set", "mcp_atlas"]
        assert len(payload["strategies"]) == 1

    def test_timestamp_is_iso_format(self) -> None:
        payload = _build_result_payload("E0", 50, 10, [_make_eval_result()])
        datetime.fromisoformat(payload["timestamp"])  # Should not raise


class TestSaveJson:
    def test_creates_file_and_parents(self, tmp_path: Path) -> None:
        data = {"test": True}
        out_path = tmp_path / "sub" / "dir" / "out.json"
        _save_json(data, out_path)
        assert out_path.exists()
        assert json.loads(out_path.read_text()) == {"test": True}


class TestFormatResultsTable:
    def test_contains_strategy_names(self) -> None:
        r = _make_eval_result("FlatStrategy")
        s = _make_eval_result("SequentialStrategy")
        output = _format_results_table(r, s, n_entries=10, top_k=10)
        assert "FlatStrategy" in output
        assert "SequentialStrategy" in output

    def test_includes_pool_size_when_specified(self) -> None:
        r = _make_eval_result()
        output = _format_results_table(r, r, n_entries=10, top_k=10, pool_size=50)
        assert "pool=50" in output

    def test_omits_pool_size_when_none(self) -> None:
        r = _make_eval_result()
        output = _format_results_table(r, r, n_entries=10, top_k=10, pool_size=None)
        assert "pool=" not in output


class TestFormatSweepTable:
    def test_contains_all_pool_sizes(self) -> None:
        payloads = [
            _build_result_payload("E0", size, 10, [_make_eval_result()]) for size in [5, 50]
        ]
        output = _format_sweep_table(payloads)
        assert "5" in output
        assert "50" in output

    def test_contains_strategy_name(self) -> None:
        payloads = [_build_result_payload("E0", 5, 10, [_make_eval_result("FlatStrategy")])]
        output = _format_sweep_table(payloads)
        assert "FlatStrategy" in output


class TestSweepSizes:
    def test_sweep_sizes_constant(self) -> None:
        assert SWEEP_SIZES == [5, 20, 50, 100, 200, 308]
