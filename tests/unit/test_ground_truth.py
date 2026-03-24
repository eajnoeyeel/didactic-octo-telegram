"""Tests for ground truth loading and utility functions."""

from pathlib import Path

import pytest

from data.ground_truth import (
    QualityGate,
    QualityGateError,
    load_ground_truth,
    merge_ground_truth,
    split_by_difficulty,
)
from models import Category, Difficulty, GroundTruthEntry


def make_entry(
    query_id: str = "gt-gen-001",
    difficulty: str = "easy",
    category: str = "general",
    ambiguity: str = "low",
    source: str = "manual_seed",
    manually_verified: bool = True,
    alternative_tools: list[str] | None = None,
) -> GroundTruthEntry:
    return GroundTruthEntry(
        query_id=query_id,
        query=f"test query {query_id}",
        correct_server_id="EthanHenrickson/math-mcp",
        correct_tool_id="EthanHenrickson/math-mcp::add",
        difficulty=difficulty,
        category=category,
        ambiguity=ambiguity,
        source=source,
        manually_verified=manually_verified,
        author="test",
        created_at="2026-03-24",
        alternative_tools=alternative_tools,
    )


def write_jsonl(entries: list[GroundTruthEntry], path: Path) -> None:
    with open(path, "w") as f:
        for e in entries:
            f.write(e.model_dump_json() + "\n")


class TestLoadGroundTruth:
    def test_loads_all_entries(self, tmp_path):
        entries = [make_entry("gt-001"), make_entry("gt-002")]
        p = tmp_path / "gt.jsonl"
        write_jsonl(entries, p)
        loaded = load_ground_truth(p)
        assert len(loaded) == 2

    def test_returns_ground_truth_entry_objects(self, tmp_path):
        p = tmp_path / "gt.jsonl"
        write_jsonl([make_entry()], p)
        loaded = load_ground_truth(p)
        assert isinstance(loaded[0], GroundTruthEntry)

    def test_filter_by_difficulty(self, tmp_path):
        entries = [
            make_entry("gt-001", difficulty="easy"),
            make_entry("gt-002", difficulty="medium"),
            make_entry("gt-003", difficulty="easy"),
        ]
        p = tmp_path / "gt.jsonl"
        write_jsonl(entries, p)
        loaded = load_ground_truth(p, difficulty=Difficulty.EASY)
        assert len(loaded) == 2
        assert all(e.difficulty == Difficulty.EASY for e in loaded)

    def test_filter_by_category(self, tmp_path):
        entries = [
            make_entry("gt-001", category="general"),
            make_entry("gt-002", category="code"),
        ]
        p = tmp_path / "gt.jsonl"
        write_jsonl(entries, p)
        loaded = load_ground_truth(p, category=Category.GENERAL)
        assert len(loaded) == 1
        assert loaded[0].category == Category.GENERAL

    def test_filter_only_verified(self, tmp_path):
        entries = [
            make_entry("gt-001", source="manual_seed", manually_verified=True),
            make_entry("gt-002", source="llm_synthetic", manually_verified=False),
        ]
        p = tmp_path / "gt.jsonl"
        write_jsonl(entries, p)
        loaded = load_ground_truth(p, only_verified=True)
        assert len(loaded) == 1
        assert loaded[0].manually_verified is True

    def test_raises_if_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_ground_truth(Path("/nonexistent/path.jsonl"))

    def test_skips_blank_lines(self, tmp_path):
        p = tmp_path / "gt.jsonl"
        entry = make_entry()
        p.write_text(entry.model_dump_json() + "\n\n")
        loaded = load_ground_truth(p)
        assert len(loaded) == 1


class TestMergeGroundTruth:
    def test_merges_two_files(self, tmp_path):
        p1 = tmp_path / "a.jsonl"
        p2 = tmp_path / "b.jsonl"
        write_jsonl([make_entry("gt-001")], p1)
        write_jsonl([make_entry("gt-002")], p2)
        merged = merge_ground_truth(p1, p2)
        assert len(merged) == 2

    def test_raises_on_duplicate_query_id(self, tmp_path):
        p1 = tmp_path / "a.jsonl"
        p2 = tmp_path / "b.jsonl"
        write_jsonl([make_entry("gt-001")], p1)
        write_jsonl([make_entry("gt-001")], p2)  # duplicate
        with pytest.raises(ValueError, match="duplicate query_id"):
            merge_ground_truth(p1, p2)


class TestSplitByDifficulty:
    def test_splits_into_three_groups(self):
        entries = [
            make_entry("gt-001", difficulty="easy"),
            make_entry(
                "gt-002",
                difficulty="medium",
                ambiguity="medium",
                alternative_tools=["EthanHenrickson/math-mcp::subtract"],
            ),
            make_entry(
                "gt-003",
                difficulty="hard",
                ambiguity="medium",
                alternative_tools=["EthanHenrickson/math-mcp::subtract"],
            ),
        ]
        groups = split_by_difficulty(entries)
        assert len(groups[Difficulty.EASY]) == 1
        assert len(groups[Difficulty.MEDIUM]) == 1
        assert len(groups[Difficulty.HARD]) == 1

    def test_missing_difficulty_returns_empty_list(self):
        entries = [make_entry("gt-001", difficulty="easy")]
        groups = split_by_difficulty(entries)
        assert groups[Difficulty.MEDIUM] == []
        assert groups[Difficulty.HARD] == []

    def test_returns_all_three_keys(self):
        groups = split_by_difficulty([])
        assert set(groups.keys()) == {Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD}


class TestQualityGate:
    def _make_entries_with_distribution(
        self, n_easy: int, n_medium: int, n_hard: int
    ) -> list[GroundTruthEntry]:
        entries = []
        for i in range(n_easy):
            entries.append(make_entry(f"e-{i}", difficulty="easy"))
        for i in range(n_medium):
            entries.append(
                make_entry(
                    f"m-{i}",
                    difficulty="medium",
                    ambiguity="medium",
                    alternative_tools=["EthanHenrickson/math-mcp::subtract"],
                )
            )
        for i in range(n_hard):
            entries.append(
                make_entry(
                    f"h-{i}",
                    difficulty="hard",
                    ambiguity="medium",
                    alternative_tools=["EthanHenrickson/math-mcp::subtract"],
                )
            )
        return entries

    def test_passes_when_distribution_matches_seed(self):
        # seed: 4 easy, 4 medium, 2 hard (40/40/20)
        seed = self._make_entries_with_distribution(4, 4, 2)
        # synthetic matches exactly
        synthetic = self._make_entries_with_distribution(8, 8, 4)
        gate = QualityGate()
        gate.check_difficulty_distribution(synthetic, seed)  # must not raise

    def test_fails_when_distribution_deviates_too_much(self):
        seed = self._make_entries_with_distribution(4, 4, 2)  # 40/40/20
        # synthetic: all easy (100/0/0) — far from seed
        synthetic = self._make_entries_with_distribution(20, 0, 0)
        gate = QualityGate()
        with pytest.raises(QualityGateError, match="difficulty distribution"):
            gate.check_difficulty_distribution(synthetic, seed)

    def test_fails_on_empty_synthetic(self):
        seed = self._make_entries_with_distribution(4, 4, 2)
        gate = QualityGate()
        with pytest.raises(QualityGateError):
            gate.check_difficulty_distribution([], seed)

    def test_no_tool_name_leakage_passes_when_clean(self):
        entries = [
            make_entry(
                "m-1",
                difficulty="medium",
                ambiguity="medium",
                alternative_tools=["EthanHenrickson/math-mcp::subtract"],
            ),
        ]
        # Manually set query that doesn't contain tool name
        entries[0] = entries[0].model_copy(update={"query": "find the middle value"})
        gate = QualityGate()
        gate.check_no_tool_name_leakage(
            entries, tool_names=["add", "subtract", "median"]
        )  # no raise

    def test_tool_name_leakage_fails_for_medium(self):
        entry = make_entry(
            "m-1",
            difficulty="medium",
            ambiguity="medium",
            alternative_tools=["EthanHenrickson/math-mcp::subtract"],
        )
        entry = entry.model_copy(update={"query": "use the add function on two numbers"})
        gate = QualityGate()
        with pytest.raises(QualityGateError, match="keyword leakage"):
            gate.check_no_tool_name_leakage([entry], tool_names=["add", "subtract"])
