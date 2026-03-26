# Phase 4: Ground Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full Ground Truth infrastructure — schema upgrade, loading utilities, quality gate, synthetic generation script, and a 20-entry pilot seed set from the 3 currently available servers.

**Architecture:** `GroundTruthEntry` in `src/models.py` is upgraded to the full schema (enums + validators). `src/data/ground_truth.py` provides pure loading utilities and a `QualityGate` for synthetic GT validation. `scripts/generate_ground_truth.py` orchestrates LLM-based generation. `data/ground_truth/seed_set.jsonl` holds 20 manually curated entries (pilot set) from the 3 crawled servers: instagram, math-mcp, clay-mcp.

**Tech Stack:** Python 3.12, Pydantic v2 (`model_validator`), OpenAI async API, pytest + pytest-asyncio, loguru, pathlib

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/models.py` | Add `Difficulty`, `Ambiguity`, `Category` enums; upgrade `GroundTruthEntry` full schema + validators |
| Modify | `tests/unit/test_models.py` | Update `TestGroundTruthEntry` for new required fields + validator tests |
| Create | `src/data/ground_truth.py` | `load_ground_truth`, `merge_ground_truth`, `split_by_difficulty`, `QualityGate`, `generate_synthetic_gt` |
| Create | `src/data/__init__.py` | (update if needed) |
| Create | `tests/unit/test_ground_truth.py` | Unit tests for all ground_truth.py functions |
| Create | `scripts/generate_ground_truth.py` | CLI: generate synthetic GT from servers.jsonl |
| Create | `data/ground_truth/seed_set.jsonl` | 20-entry pilot seed set (manual, verified) |

---

## Task 1: Upgrade GroundTruthEntry Model

**Files:**
- Modify: `src/models.py`
- Modify: `tests/unit/test_models.py`

Current `GroundTruthEntry` is a simplified Phase 0 placeholder. This task upgrades it to the full schema with enums and cross-field validators.

- [ ] **Step 1: Write failing tests** (append to `tests/unit/test_models.py`)

Add these imports at the top of `test_models.py`:
```python
from models import Ambiguity, Category, Difficulty
```

Append this class:
```python
class TestGroundTruthEntryFull:
    """Tests for the full Phase 4 GroundTruthEntry schema."""

    def _base(self, **overrides) -> dict:
        """Minimal valid entry — override individual fields per test."""
        base = {
            "query_id": "gt-gen-001",
            "query": "add two numbers",
            "correct_server_id": "EthanHenrickson/math-mcp",
            "correct_tool_id": "EthanHenrickson/math-mcp::add",
            "difficulty": "easy",
            "category": "general",
            "ambiguity": "low",
            "source": "manual_seed",
            "manually_verified": True,
            "author": "test",
            "created_at": "2026-03-24",
        }
        base.update(overrides)
        return base

    def test_create_valid_entry(self):
        gt = GroundTruthEntry(**self._base())
        assert gt.query_id == "gt-gen-001"
        assert gt.difficulty == Difficulty.EASY
        assert gt.category == Category.GENERAL
        assert gt.ambiguity == Ambiguity.LOW
        assert gt.alternative_tools is None
        assert gt.notes is None

    def test_difficulty_enum_values(self):
        for val in ("easy", "medium", "hard"):
            gt = GroundTruthEntry(**self._base(difficulty=val))
            assert gt.difficulty.value == val

    def test_category_enum_values(self):
        for cat in ("search", "code", "database", "communication",
                    "productivity", "science", "finance", "general"):
            gt = GroundTruthEntry(**self._base(category=cat))
            assert gt.category.value == cat

    def test_hard_difficulty_requires_non_low_ambiguity(self):
        with pytest.raises(ValueError, match="hard difficulty"):
            GroundTruthEntry(**self._base(difficulty="hard", ambiguity="low"))

    def test_hard_with_medium_ambiguity_is_valid(self):
        gt = GroundTruthEntry(**self._base(
            difficulty="hard",
            ambiguity="medium",
            alternative_tools=["EthanHenrickson/math-mcp::subtract"],
        ))
        assert gt.difficulty == Difficulty.HARD

    def test_medium_ambiguity_requires_alternative_tools(self):
        with pytest.raises(ValueError, match="alternative_tools"):
            GroundTruthEntry(**self._base(ambiguity="medium"))

    def test_high_ambiguity_requires_alternative_tools(self):
        with pytest.raises(ValueError, match="alternative_tools"):
            GroundTruthEntry(**self._base(ambiguity="high"))

    def test_medium_ambiguity_with_alternatives_is_valid(self):
        gt = GroundTruthEntry(**self._base(
            ambiguity="medium",
            alternative_tools=["EthanHenrickson/math-mcp::subtract"],
        ))
        assert gt.ambiguity == Ambiguity.MEDIUM

    def test_manual_seed_requires_manually_verified_true(self):
        with pytest.raises(ValueError, match="manually_verified"):
            GroundTruthEntry(**self._base(
                source="manual_seed", manually_verified=False
            ))

    def test_llm_synthetic_can_be_unverified(self):
        gt = GroundTruthEntry(**self._base(
            source="llm_synthetic", manually_verified=False
        ))
        assert gt.source == "llm_synthetic"
        assert gt.manually_verified is False

    def test_correct_tool_id_must_start_with_server_id(self):
        with pytest.raises(ValueError):
            GroundTruthEntry(**self._base(
                correct_server_id="server-a",
                correct_tool_id="server-b::tool",
            ))

    def test_with_notes(self):
        gt = GroundTruthEntry(**self._base(notes="test note"))
        assert gt.notes == "test note"
```

Also update the existing `TestGroundTruthEntry.test_create` — the old test will fail because the new model has required fields. Replace the old test:
```python
class TestGroundTruthEntry:
    def test_legacy_test_replaced_by_full_schema(self):
        """Old simplified schema is gone. Full schema tested in TestGroundTruthEntryFull."""
        pass
```

- [ ] **Step 2: Run tests to verify FAIL**

```bash
cd /Users/iyeonjae/Desktop/shockwave/mcp-discovery
uv run pytest tests/unit/test_models.py::TestGroundTruthEntryFull -v
```
Expected: `ImportError: cannot import name 'Ambiguity'`

- [ ] **Step 3: Upgrade `src/models.py`**

Add after the `TOOL_ID_SEPARATOR` constant and before `MCPServerSummary`:

```python
from enum import Enum
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator
```

(Replace the existing imports to include `Enum`, `Field`, `model_validator`.)

Add these enums right after `TOOL_ID_SEPARATOR = "::"`:

```python
class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Ambiguity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Category(str, Enum):
    SEARCH = "search"
    CODE = "code"
    DATABASE = "database"
    COMMUNICATION = "communication"
    PRODUCTIVITY = "productivity"
    SCIENCE = "science"
    FINANCE = "finance"
    GENERAL = "general"
```

Replace the existing `GroundTruthEntry` class entirely:

```python
class GroundTruthEntry(BaseModel):
    """Ground Truth entry — a single (query, correct_tool) pair for evaluation.

    Full Phase 4 schema. See docs/design/ground-truth-schema.md for field semantics.
    """

    # Identity
    query_id: str = Field(description="Unique ID, e.g. 'gt-search-001'")
    query: str = Field(description="Natural language query")

    # Ground truth labels
    correct_server_id: str = Field(description="Correct MCP server ID")
    correct_tool_id: str = Field(description="Correct tool ID (server_id::tool_name)")

    # Classification
    difficulty: Difficulty
    category: Category
    ambiguity: Ambiguity

    # Provenance
    source: str = Field(description="'manual_seed' | 'llm_synthetic' | 'llm_verified'")
    manually_verified: bool = False
    author: str = Field(description="Author ID or model name")
    created_at: str = Field(description="ISO 8601 date")

    # Optional — graded relevance for NDCG@5
    alternative_tools: list[str] | None = None
    notes: str | None = None

    @field_validator("correct_tool_id")
    @classmethod
    def validate_tool_id_matches_server(cls, v: str, info) -> str:
        server_id = info.data.get("correct_server_id", "")
        if server_id and not v.startswith(f"{server_id}{TOOL_ID_SEPARATOR}"):
            raise ValueError(
                f"correct_tool_id '{v}' must start with '{server_id}{TOOL_ID_SEPARATOR}'"
            )
        return v

    @model_validator(mode="after")
    def validate_cross_field_rules(self) -> "GroundTruthEntry":
        # hard difficulty requires non-low ambiguity
        if self.difficulty == Difficulty.HARD and self.ambiguity == Ambiguity.LOW:
            raise ValueError(
                "hard difficulty requires ambiguity 'medium' or 'high', got 'low'"
            )
        # medium/high ambiguity requires alternative_tools
        if self.ambiguity in (Ambiguity.MEDIUM, Ambiguity.HIGH):
            if not self.alternative_tools:
                raise ValueError(
                    f"ambiguity '{self.ambiguity.value}' requires non-empty alternative_tools"
                )
        # manual_seed must be manually verified
        if self.source == "manual_seed" and not self.manually_verified:
            raise ValueError(
                "source='manual_seed' entries must have manually_verified=True"
            )
        return self
```

- [ ] **Step 4: Run tests to verify PASS**

```bash
uv run pytest tests/unit/test_models.py -v
```
Expected: All tests PASS (including new `TestGroundTruthEntryFull`)

- [ ] **Step 5: Run full suite — check no regressions**

```bash
uv run pytest tests/ -v
```
Expected: All pass.

- [ ] **Step 6: Lint**

```bash
uv run ruff check src/ tests/
```

- [ ] **Step 7: Commit**

```bash
git add src/models.py tests/unit/test_models.py
git commit -m "feat(models): upgrade GroundTruthEntry to full Phase 4 schema with enums"
```

---

## Task 2: Ground Truth Loading Utilities

**Files:**
- Create: `src/data/ground_truth.py`
- Create: `tests/unit/test_ground_truth.py`

Pure functions: `load_ground_truth`, `merge_ground_truth`, `split_by_difficulty`.

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_ground_truth.py
"""Tests for ground truth loading and utility functions."""
import json
import tempfile
from pathlib import Path

import pytest

from models import Ambiguity, Category, Difficulty, GroundTruthEntry
from data.ground_truth import load_ground_truth, merge_ground_truth, split_by_difficulty


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
        correct_tool_id=f"EthanHenrickson/math-mcp::add",
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
```

- [ ] **Step 2: Run tests to verify FAIL**

```bash
uv run pytest tests/unit/test_ground_truth.py -v
```
Expected: `ModuleNotFoundError: No module named 'data.ground_truth'`

- [ ] **Step 3: Create `src/data/ground_truth.py`**

```python
"""Ground Truth loading, filtering, and splitting utilities."""

from pathlib import Path

from loguru import logger

from models import Difficulty, Category, GroundTruthEntry


def load_ground_truth(
    path: Path,
    difficulty: Difficulty | None = None,
    category: Category | None = None,
    only_verified: bool = False,
) -> list[GroundTruthEntry]:
    """Load and optionally filter a JSONL ground truth file.

    Args:
        path: Path to .jsonl file (one GroundTruthEntry per line).
        difficulty: If set, return only entries with this difficulty.
        category: If set, return only entries in this category.
        only_verified: If True, return only manually_verified=True entries.

    Returns:
        List of validated GroundTruthEntry objects.

    Raises:
        FileNotFoundError: if path does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {path}")

    entries: list[GroundTruthEntry] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        entry = GroundTruthEntry.model_validate_json(line)
        if difficulty is not None and entry.difficulty != difficulty:
            continue
        if category is not None and entry.category != category:
            continue
        if only_verified and not entry.manually_verified:
            continue
        entries.append(entry)

    logger.info(f"Loaded {len(entries)} ground truth entries from {path}")
    return entries


def merge_ground_truth(*paths: Path) -> list[GroundTruthEntry]:
    """Merge multiple JSONL files into one list.

    Raises:
        ValueError: if any query_id appears more than once across all files.
    """
    all_entries: list[GroundTruthEntry] = []
    seen_ids: set[str] = set()

    for path in paths:
        for entry in load_ground_truth(path):
            if entry.query_id in seen_ids:
                raise ValueError(
                    f"duplicate query_id '{entry.query_id}' found in {path}"
                )
            seen_ids.add(entry.query_id)
            all_entries.append(entry)

    logger.info(f"Merged {len(all_entries)} entries from {len(paths)} files")
    return all_entries


def split_by_difficulty(
    entries: list[GroundTruthEntry],
) -> dict[Difficulty, list[GroundTruthEntry]]:
    """Group entries by difficulty level.

    Always returns all three keys (EASY, MEDIUM, HARD), even if some are empty.

    Args:
        entries: Flat list of GroundTruthEntry objects.

    Returns:
        Dict mapping each Difficulty to its entries.
    """
    groups: dict[Difficulty, list[GroundTruthEntry]] = {
        Difficulty.EASY: [],
        Difficulty.MEDIUM: [],
        Difficulty.HARD: [],
    }
    for entry in entries:
        groups[entry.difficulty].append(entry)
    return groups
```

- [ ] **Step 4: Run tests to verify PASS**

```bash
uv run pytest tests/unit/test_ground_truth.py -v
```
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/data/ground_truth.py tests/unit/test_ground_truth.py
git commit -m "feat(data): add ground truth loading utilities"
```

---

## Task 3: Quality Gate for Synthetic GT

**Files:**
- Modify: `src/data/ground_truth.py` (append)
- Modify: `tests/unit/test_ground_truth.py` (append)

- [ ] **Step 1: Write failing tests** (append to `tests/unit/test_ground_truth.py`)

Add to imports: `from data.ground_truth import QualityGate, QualityGateError`

```python
class TestQualityGate:
    def _make_entries_with_distribution(
        self, n_easy: int, n_medium: int, n_hard: int
    ) -> list[GroundTruthEntry]:
        entries = []
        for i in range(n_easy):
            entries.append(make_entry(f"e-{i}", difficulty="easy"))
        for i in range(n_medium):
            entries.append(make_entry(
                f"m-{i}",
                difficulty="medium",
                ambiguity="medium",
                alternative_tools=["EthanHenrickson/math-mcp::subtract"],
            ))
        for i in range(n_hard):
            entries.append(make_entry(
                f"h-{i}",
                difficulty="hard",
                ambiguity="medium",
                alternative_tools=["EthanHenrickson/math-mcp::subtract"],
            ))
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
            make_entry("m-1", difficulty="medium",
                       ambiguity="medium",
                       alternative_tools=["EthanHenrickson/math-mcp::subtract"]),
        ]
        # Manually set query that doesn't contain tool name
        entries[0] = entries[0].model_copy(update={"query": "find the middle value"})
        gate = QualityGate()
        gate.check_no_tool_name_leakage(entries, tool_names=["add", "subtract", "median"])  # no raise

    def test_tool_name_leakage_fails_for_medium(self):
        entry = make_entry(
            "m-1", difficulty="medium",
            ambiguity="medium",
            alternative_tools=["EthanHenrickson/math-mcp::subtract"],
        )
        entry = entry.model_copy(update={"query": "use the add function on two numbers"})
        gate = QualityGate()
        with pytest.raises(QualityGateError, match="keyword leakage"):
            gate.check_no_tool_name_leakage([entry], tool_names=["add", "subtract"])
```

- [ ] **Step 2: Run tests to verify FAIL**

```bash
uv run pytest tests/unit/test_ground_truth.py::TestQualityGate -v
```
Expected: `ImportError: cannot import name 'QualityGate'`

- [ ] **Step 3: Append `QualityGate` to `src/data/ground_truth.py`**

```python

class QualityGateError(Exception):
    """Raised when synthetic GT fails a quality check."""


class QualityGate:
    """Validates synthetic ground truth against quality criteria.

    Checks:
    - Difficulty distribution matches seed set (within tolerance)
    - Medium/Hard queries do not contain tool names (keyword leakage)
    """

    DIFFICULTY_TOLERANCE = 0.15

    def check_difficulty_distribution(
        self,
        synthetic: list[GroundTruthEntry],
        seed: list[GroundTruthEntry],
    ) -> None:
        """Raise QualityGateError if synthetic distribution deviates > 15% from seed.

        Args:
            synthetic: LLM-generated entries to validate.
            seed: Reference seed set defining the target distribution.

        Raises:
            QualityGateError: if any difficulty's proportion deviates too much.
        """
        if not synthetic:
            raise QualityGateError("Synthetic set is empty")

        n_synthetic = len(synthetic)
        n_seed = len(seed)

        for diff in Difficulty:
            seed_count = sum(1 for e in seed if e.difficulty == diff)
            synth_count = sum(1 for e in synthetic if e.difficulty == diff)
            seed_ratio = seed_count / n_seed if n_seed > 0 else 0.0
            synth_ratio = synth_count / n_synthetic
            deviation = abs(synth_ratio - seed_ratio)
            if deviation > self.DIFFICULTY_TOLERANCE:
                raise QualityGateError(
                    f"difficulty distribution check failed for '{diff.value}': "
                    f"seed={seed_ratio:.0%}, synthetic={synth_ratio:.0%}, "
                    f"deviation={deviation:.0%} > tolerance={self.DIFFICULTY_TOLERANCE:.0%}"
                )

    def check_no_tool_name_leakage(
        self,
        entries: list[GroundTruthEntry],
        tool_names: list[str],
    ) -> None:
        """Raise QualityGateError if medium/hard queries contain any tool name.

        Easy queries are allowed to contain tool names (that's what makes them easy).
        Medium and Hard must NOT contain tool names — they should require semantic search.

        Args:
            entries: Entries to check.
            tool_names: List of tool names to look for (lowercase comparison).

        Raises:
            QualityGateError: listing all violating queries.
        """
        violations = []
        for entry in entries:
            if entry.difficulty == Difficulty.EASY:
                continue
            query_lower = entry.query.lower()
            for tool_name in tool_names:
                if tool_name.lower() in query_lower:
                    violations.append(
                        f"[{entry.query_id}] query '{entry.query}' "
                        f"contains tool name '{tool_name}'"
                    )
                    break
        if violations:
            raise QualityGateError(
                f"keyword leakage in {len(violations)} entries:\n"
                + "\n".join(violations)
            )
```

- [ ] **Step 4: Run tests to verify PASS**

```bash
uv run pytest tests/unit/test_ground_truth.py -v
```
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/data/ground_truth.py tests/unit/test_ground_truth.py
git commit -m "feat(data): add QualityGate for synthetic ground truth validation"
```

---

## Task 4: Synthetic Generation Script

**Files:**
- Modify: `src/data/ground_truth.py` (append `generate_synthetic_gt`)
- Create: `scripts/generate_ground_truth.py`
- Modify: `tests/unit/test_ground_truth.py` (append one integration-guarded test)

- [ ] **Step 1: Append `generate_synthetic_gt` to `src/data/ground_truth.py`**

(No failing test first — this function calls OpenAI, tested with integration guard.)

Add import at top of `ground_truth.py`:
```python
import json
from openai import AsyncOpenAI
from models import Difficulty, Category, GroundTruthEntry, MCPServer
```

Append to `src/data/ground_truth.py`:

```python

_SYNTHETIC_PROMPT = """You are generating test queries for a tool recommendation system.

Tool: {tool_name}
Server ID: {server_id}
Description: {description}

Generate 10 natural language queries a user would write when they need this tool.
Distribute difficulty: 4 Easy, 4 Medium, 2 Hard.

Rules:
- Do NOT include the exact tool_name in Medium or Hard queries
- Vary sentence structures (question, command, statement of need)
- Hard queries must be genuinely ambiguous (another tool could also match)

Return a JSON array of 10 objects:
[
  {{
    "query": "...",
    "difficulty": "easy|medium|hard",
    "ambiguity": "low|medium|high",
    "alternative_tool_names": [],
    "notes": "why this difficulty/ambiguity"
  }},
  ...
]"""


async def generate_synthetic_gt(
    servers: list[MCPServer],
    client: AsyncOpenAI,
    model: str = "gpt-4o-mini",
    author: str = "gpt-4o-mini",
    created_at: str = "2026-03-24",
    category_map: dict[str, Category] | None = None,
) -> list[GroundTruthEntry]:
    """Generate synthetic ground truth entries using LLM for each tool.

    Generates 10 queries per tool. Filters out entries that fail basic validation.
    Does NOT run QualityGate — caller must do that.

    Args:
        servers: MCPServer list to generate queries for.
        client: AsyncOpenAI client (caller provides key).
        model: OpenAI model to use.
        author: Author field in generated entries.
        created_at: ISO 8601 date string.
        category_map: Optional server_id → Category override.

    Returns:
        List of GroundTruthEntry objects (unverified, source='llm_synthetic').
    """
    entries: list[GroundTruthEntry] = []
    counter = 1

    for server in servers:
        server_category = (
            category_map.get(server.server_id, Category.GENERAL)
            if category_map
            else Category.GENERAL
        )
        for tool in server.tools:
            prompt = _SYNTHETIC_PROMPT.format(
                tool_name=tool.tool_name,
                server_id=server.server_id,
                description=tool.description or tool.tool_name,
            )
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                )
                raw = response.choices[0].message.content or "[]"
                items = json.loads(raw)
            except Exception as e:
                logger.warning(f"Skipping {tool.tool_id}: LLM call failed: {e}")
                continue

            for item in items:
                query_id = f"gt-synth-{counter:04d}"
                alt_tool_names = item.get("alternative_tool_names", [])
                alt_tool_ids = [
                    f"{server.server_id}{TOOL_ID_SEPARATOR}{n}" for n in alt_tool_names
                ] or None
                difficulty_val = item.get("difficulty", "medium")
                ambiguity_val = item.get("ambiguity", "low")

                # Ensure consistency: hard requires non-low ambiguity
                if difficulty_val == "hard" and ambiguity_val == "low":
                    ambiguity_val = "medium"
                    alt_tool_ids = alt_tool_ids or [
                        f"{server.server_id}{TOOL_ID_SEPARATOR}other"
                    ]

                # Ensure medium/high has alternatives
                if ambiguity_val in ("medium", "high") and not alt_tool_ids:
                    ambiguity_val = "low"

                try:
                    entry = GroundTruthEntry(
                        query_id=query_id,
                        query=item["query"],
                        correct_server_id=server.server_id,
                        correct_tool_id=tool.tool_id,
                        difficulty=difficulty_val,
                        category=server_category,
                        ambiguity=ambiguity_val,
                        source="llm_synthetic",
                        manually_verified=False,
                        author=author,
                        created_at=created_at,
                        alternative_tools=alt_tool_ids,
                        notes=item.get("notes"),
                    )
                    entries.append(entry)
                    counter += 1
                except Exception as e:
                    logger.warning(f"Skipping malformed entry for {tool.tool_id}: {e}")

    logger.info(f"Generated {len(entries)} synthetic entries for {len(servers)} servers")
    return entries
```

Also add `TOOL_ID_SEPARATOR` import at the top of `ground_truth.py` (needed for generate_synthetic_gt):
```python
from models import Difficulty, Category, GroundTruthEntry, MCPServer, TOOL_ID_SEPARATOR
```

- [ ] **Step 2: Create `scripts/generate_ground_truth.py`**

```python
#!/usr/bin/env python3
"""Generate synthetic ground truth from crawled server data.

Usage:
    uv run python scripts/generate_ground_truth.py \
        --servers data/raw/servers.jsonl \
        --output data/ground_truth/synthetic.jsonl \
        [--model gpt-4o-mini]
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Add src/ to path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger
from openai import AsyncOpenAI

from data.ground_truth import QualityGate, QualityGateError, generate_synthetic_gt, load_ground_truth
from models import MCPServer


def load_servers(path: Path) -> list[MCPServer]:
    servers = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        servers.append(MCPServer.model_validate_json(line))
    logger.info(f"Loaded {len(servers)} servers from {path}")
    return servers


async def main(args: argparse.Namespace) -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    servers = load_servers(Path(args.servers))
    client = AsyncOpenAI(api_key=api_key)

    entries = await generate_synthetic_gt(
        servers=servers,
        client=client,
        model=args.model,
        created_at=args.date,
    )

    # Run quality gate if seed set is available
    if args.seed and Path(args.seed).exists():
        seed = load_ground_truth(Path(args.seed), only_verified=True)
        gate = QualityGate()
        try:
            gate.check_difficulty_distribution(entries, seed)
            logger.info("Quality gate: difficulty distribution OK")
        except QualityGateError as e:
            logger.warning(f"Quality gate warning: {e}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        for entry in entries:
            f.write(entry.model_dump_json() + "\n")

    logger.info(f"Wrote {len(entries)} entries to {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--servers", default="data/raw/servers.jsonl")
    parser.add_argument("--output", default="data/ground_truth/synthetic.jsonl")
    parser.add_argument("--seed", default="data/ground_truth/seed_set.jsonl")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--date", default="2026-03-24")
    asyncio.run(main(parser.parse_args()))
```

- [ ] **Step 3: Add integration-guarded test** (append to `tests/unit/test_ground_truth.py`)

```python
import os
import pytest

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
async def test_generate_synthetic_gt_integration():
    """Integration test — only runs when OPENAI_API_KEY is set."""
    from openai import AsyncOpenAI
    from models import MCPServer, MCPTool
    from data.ground_truth import generate_synthetic_gt

    server = MCPServer(
        server_id="EthanHenrickson/math-mcp",
        name="Math-MCP",
        tools=[
            MCPTool(
                server_id="EthanHenrickson/math-mcp",
                tool_name="add",
                tool_id="EthanHenrickson/math-mcp::add",
                description="Adds two numbers together",
            )
        ],
    )
    client = AsyncOpenAI()
    entries = await generate_synthetic_gt([server], client)
    assert len(entries) > 0
    assert all(e.source == "llm_synthetic" for e in entries)
```

- [ ] **Step 4: Run unit tests (no API key needed)**

```bash
uv run pytest tests/unit/test_ground_truth.py -v
```
Expected: All non-integration tests PASS.

- [ ] **Step 5: Lint**

```bash
uv run ruff check src/ tests/ scripts/
```

- [ ] **Step 6: Commit**

```bash
git add src/data/ground_truth.py scripts/generate_ground_truth.py tests/unit/test_ground_truth.py
git commit -m "feat(data): add synthetic GT generation and generate_ground_truth.py script"
```

---

## Task 5: Pilot Seed Set (20 entries)

**Files:**
- Create: `data/ground_truth/seed_set.jsonl`

20 hand-curated entries from the 3 currently available servers. Serves as the pilot set for pipeline testing. Easy:Medium:Hard = 8:8:4.

**Available servers:**
- `instagram` — 16 tools (communication)
- `EthanHenrickson/math-mcp` — 22 tools (general)
- `clay-inc/clay-mcp` — 20 tools (productivity)

- [ ] **Step 1: Create directory**

```bash
mkdir -p /Users/iyeonjae/Desktop/shockwave/mcp-discovery/data/ground_truth
```

- [ ] **Step 2: Create `data/ground_truth/seed_set.jsonl`**

Write each entry as a single JSON line (no line breaks within entries):

```
# Instagram — communication (6 entries: E2, M2, H2)
{"query_id":"gt-comm-001","query":"create a carousel post with multiple photos on Instagram","correct_server_id":"instagram","correct_tool_id":"instagram::INSTAGRAM_CREATE_CAROUSEL_CONTAINER","difficulty":"easy","category":"communication","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"키워드 'carousel post' 직접 매칭"}
{"query_id":"gt-comm-002","query":"get the comments on my Instagram post","correct_server_id":"instagram","correct_tool_id":"instagram::INSTAGRAM_GET_POST_COMMENTS","difficulty":"easy","category":"communication","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"키워드 'comments' 직접 매칭"}
{"query_id":"gt-comm-003","query":"see how my Instagram content is performing","correct_server_id":"instagram","correct_tool_id":"instagram::INSTAGRAM_GET_POST_INSIGHTS","difficulty":"medium","category":"communication","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"'performing' → 'insights' 의미적 연결"}
{"query_id":"gt-comm-004","query":"check the private messages in a conversation thread","correct_server_id":"instagram","correct_tool_id":"instagram::INSTAGRAM_GET_CONVERSATION","difficulty":"medium","category":"communication","ambiguity":"medium","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":["instagram::INSTAGRAM_LIST_ALL_MESSAGES"],"notes":"'private messages' → GET_CONVERSATION, but LIST_ALL_MESSAGES도 부분 적합"}
{"query_id":"gt-comm-005","query":"post something new for my followers to see","correct_server_id":"instagram","correct_tool_id":"instagram::INSTAGRAM_CREATE_POST","difficulty":"hard","category":"communication","ambiguity":"high","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":["instagram::INSTAGRAM_CREATE_CAROUSEL_CONTAINER","instagram::INSTAGRAM_CREATE_MEDIA_CONTAINER"],"notes":"'post something' 모호 — carousel/media/post 모두 가능"}
{"query_id":"gt-comm-006","query":"engage back with someone who replied to my content","correct_server_id":"instagram","correct_tool_id":"instagram::INSTAGRAM_REPLY_TO_COMMENT","difficulty":"hard","category":"communication","ambiguity":"high","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":["instagram::INSTAGRAM_SEND_TEXT_MESSAGE","instagram::INSTAGRAM_MARK_SEEN"],"notes":"'engage back' 모호 — reply to comment vs DM reply"}

# Math-MCP — general (7 entries: E3, M3, H1)
{"query_id":"gt-gen-001","query":"add two numbers together","correct_server_id":"EthanHenrickson/math-mcp","correct_tool_id":"EthanHenrickson/math-mcp::add","difficulty":"easy","category":"general","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"키워드 'add' 직접 매칭"}
{"query_id":"gt-gen-002","query":"find the maximum value in a list of numbers","correct_server_id":"EthanHenrickson/math-mcp","correct_tool_id":"EthanHenrickson/math-mcp::max","difficulty":"easy","category":"general","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"키워드 'maximum' → max 직접"}
{"query_id":"gt-gen-003","query":"calculate the sine of an angle","correct_server_id":"EthanHenrickson/math-mcp","correct_tool_id":"EthanHenrickson/math-mcp::sin","difficulty":"easy","category":"general","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"키워드 'sine' 직접"}
{"query_id":"gt-gen-004","query":"find the middle value in my dataset","correct_server_id":"EthanHenrickson/math-mcp","correct_tool_id":"EthanHenrickson/math-mcp::median","difficulty":"medium","category":"general","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"'middle value' → 'median' 의미적 연결"}
{"query_id":"gt-gen-005","query":"get the average of a set of numbers","correct_server_id":"EthanHenrickson/math-mcp","correct_tool_id":"EthanHenrickson/math-mcp::mean","difficulty":"medium","category":"general","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"'average' → 'mean' 의미적 연결"}
{"query_id":"gt-gen-006","query":"convert an angle measurement to a different unit","correct_server_id":"EthanHenrickson/math-mcp","correct_tool_id":"EthanHenrickson/math-mcp::degreesToRadians","difficulty":"medium","category":"general","ambiguity":"medium","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":["EthanHenrickson/math-mcp::radiansToDegrees"],"notes":"방향(도→라디안 vs 라디안→도) 모호"}
{"query_id":"gt-gen-007","query":"what is left over after dividing these two numbers","correct_server_id":"EthanHenrickson/math-mcp","correct_tool_id":"EthanHenrickson/math-mcp::modulo","difficulty":"hard","category":"general","ambiguity":"medium","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":["EthanHenrickson/math-mcp::division"],"notes":"'left over' → modulo, but 'division' 혼동 가능"}

# Clay-MCP — productivity (7 entries: E3, M3, H1)
{"query_id":"gt-prod-001","query":"search for contacts in my CRM by name","correct_server_id":"clay-inc/clay-mcp","correct_tool_id":"clay-inc/clay-mcp::searchContacts","difficulty":"easy","category":"productivity","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"키워드 'search contacts' 직접"}
{"query_id":"gt-prod-002","query":"create a new contact record in Clay","correct_server_id":"clay-inc/clay-mcp","correct_tool_id":"clay-inc/clay-mcp::createContact","difficulty":"easy","category":"productivity","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"키워드 'create contact' 직접"}
{"query_id":"gt-prod-003","query":"get full details for a contact by their ID","correct_server_id":"clay-inc/clay-mcp","correct_tool_id":"clay-inc/clay-mcp::getContact","difficulty":"easy","category":"productivity","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"키워드 'get contact' 직접"}
{"query_id":"gt-prod-004","query":"change the phone number for someone in my contacts","correct_server_id":"clay-inc/clay-mcp","correct_tool_id":"clay-inc/clay-mcp::updateContact","difficulty":"medium","category":"productivity","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"'change phone number' → updateContact 의미적 연결"}
{"query_id":"gt-prod-005","query":"find people in my contacts who might be the same person","correct_server_id":"clay-inc/clay-mcp","correct_tool_id":"clay-inc/clay-mcp::find_duplicates","difficulty":"medium","category":"productivity","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":null,"notes":"'same person' → find_duplicates 의미 연결"}
{"query_id":"gt-prod-006","query":"see what emails I recently received about a contact","correct_server_id":"clay-inc/clay-mcp","correct_tool_id":"clay-inc/clay-mcp::getRecentEmails","difficulty":"medium","category":"productivity","ambiguity":"medium","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":["clay-inc/clay-mcp::getEmails"],"notes":"recent vs all emails 모호"}
{"query_id":"gt-prod-007","query":"add a memo about a conversation I had with someone","correct_server_id":"clay-inc/clay-mcp","correct_tool_id":"clay-inc/clay-mcp::createNote","difficulty":"hard","category":"productivity","ambiguity":"medium","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-24","alternative_tools":["clay-inc/clay-mcp::updateContact","clay-inc/clay-mcp::getEvents"],"notes":"'memo/conversation' → note이지만 updateContact도 가능"}
```

- [ ] **Step 3: Validate the file loads correctly**

```bash
cd /Users/iyeonjae/Desktop/shockwave/mcp-discovery
python3 -c "
import sys
sys.path.insert(0, 'src')
from pathlib import Path
from data.ground_truth import load_ground_truth
entries = load_ground_truth(Path('data/ground_truth/seed_set.jsonl'))
print(f'Loaded: {len(entries)} entries')
from collections import Counter
diff = Counter(e.difficulty.value for e in entries)
cat = Counter(e.category.value for e in entries)
print(f'Difficulty: {dict(diff)}')
print(f'Category: {dict(cat)}')
"
```
Expected:
```
Loaded: 20 entries
Difficulty: {'easy': 8, 'medium': 8, 'hard': 4}
Category: {'communication': 6, 'general': 7, 'productivity': 7}
```

- [ ] **Step 4: Commit**

```bash
git add data/ground_truth/seed_set.jsonl
git commit -m "data(ground_truth): add 20-entry pilot seed set for E0 validation"
```

---

## Task 6: Final Integration Check

- [ ] **Step 1: Full test suite with coverage**

```bash
uv run pytest tests/ --cov=src -v
```
Expected: All PASS, coverage ≥ 80%

- [ ] **Step 2: Lint**

```bash
uv run ruff check src/ tests/ scripts/
```

- [ ] **Step 3: Verify seed file loads end-to-end with filters**

```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from pathlib import Path
from data.ground_truth import load_ground_truth, split_by_difficulty, merge_ground_truth
from models import Difficulty, Category

entries = load_ground_truth(Path('data/ground_truth/seed_set.jsonl'))
easy_only = load_ground_truth(Path('data/ground_truth/seed_set.jsonl'), difficulty=Difficulty.EASY)
verified = load_ground_truth(Path('data/ground_truth/seed_set.jsonl'), only_verified=True)
groups = split_by_difficulty(entries)
print(f'All: {len(entries)}, Easy filter: {len(easy_only)}, Verified: {len(verified)}')
print(f'Groups: {[(d.value, len(v)) for d, v in groups.items()]}')
"
```

- [ ] **Step 4: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "chore(ground_truth): Phase 4 integration verified"
```

---

## What's Next (Phase 4 → Phase 5)

- **Phase 5**: Evaluation harness — `src/evaluation/harness.py`, `src/evaluation/metrics/` (Precision@1, Recall@K, MRR, Confusion Rate, ECE, Spearman)
- **E0 prerequisite**: Reranker (Phase 6) needed before running full experiments. But the harness can be built and tested against mocked pipeline output.
- **Seed set expansion**: Once more servers are crawled (OQ-2), expand `seed_set.jsonl` to 80 entries across all 8 categories.
