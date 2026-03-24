"""Ground Truth loading, filtering, and splitting utilities."""

from pathlib import Path

from loguru import logger

from models import Category, Difficulty, GroundTruthEntry


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
                raise ValueError(f"duplicate query_id '{entry.query_id}' found in {path}")
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
                        f"[{entry.query_id}] query '{entry.query}' contains tool name '{tool_name}'"
                    )
                    break
        if violations:
            raise QualityGateError(
                f"keyword leakage in {len(violations)} entries:\n" + "\n".join(violations)
            )
