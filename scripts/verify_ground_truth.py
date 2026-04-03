#!/usr/bin/env python3
"""Verify generated ground truth quality.

Usage:
    uv run python scripts/verify_ground_truth.py \\
        --synthetic data/ground_truth/synthetic.jsonl \\
        --seed data/ground_truth/seed_set.jsonl

    # Atlas-only verification:
    uv run python scripts/verify_ground_truth.py \\
        --atlas data/ground_truth/mcp_atlas.jsonl \\
        --seed data/ground_truth/seed_set.jsonl

    # All three sources:
    uv run python scripts/verify_ground_truth.py \\
        --atlas data/ground_truth/mcp_atlas.jsonl \\
        --synthetic data/ground_truth/synthetic.jsonl \\
        --seed data/ground_truth/seed_set.jsonl
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Add src/ to path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.ground_truth import (
    QualityGate,
    QualityGateError,
    load_ground_truth,
    merge_ground_truth,
    split_by_difficulty,
)
from models import Difficulty, GroundTruthEntry

# Short/common tool names that cause false-positive leakage (substring of common words)
FALSE_POSITIVE_TOOL_NAMES = {
    # Math-related
    "sin",
    "min",
    "max",
    "sum",
    "add",
    "tan",
    "cos",
    "log",
    "mode",
    "round",
    "mean",
    "median",
    "floor",
    "ceiling",
    "division",
    "multiply",
    "modulo",
    # Common English words that are also tool names
    "find",
    "count",
    "fetch",
    "aggregate",
    "search",
    "list",
    "get",
    "update",
    "delete",
    "create",
    "read",
    "write",
    "run",
    "execute",
    "send",
    "post",
    "translate",
    "calculate",
}


def print_header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_section(num: int, title: str) -> None:
    print(f"\n[{num}] {title}")
    print("-" * 40)


def check_tool_name_leakage(
    entries: list[GroundTruthEntry],
    label: str,
) -> bool:
    """Check for tool name leakage in medium/hard queries.

    Returns True if check passes (no real violations).
    """
    all_tool_names: set[str] = set()
    for entry in entries:
        tool_id = entry.correct_tool_id
        if "::" in tool_id:
            all_tool_names.add(tool_id.split("::")[-1])

    gate = QualityGate()

    try:
        gate.check_no_tool_name_leakage(entries, list(all_tool_names))
        print(f"  Tool name leakage ({label}): PASS (0 violations)")
        return True
    except QualityGateError:
        real_tool_names = [n for n in all_tool_names if n.lower() not in FALSE_POSITIVE_TOOL_NAMES]
        real_violations = []
        for entry in entries:
            if entry.difficulty == Difficulty.EASY:
                continue
            query_lower = entry.query.lower()
            for tn in real_tool_names:
                if tn.lower() in query_lower:
                    real_violations.append(
                        f"    [{entry.query_id}] '{entry.query}' contains '{tn}'"
                    )
                    break

        fp_names = all_tool_names - set(real_tool_names)
        print(f"  Tool name leakage ({label}): WARNING")
        print(f"    Short names excluded (false positives): {sorted(fp_names)}")
        print(f"    Real violations after filtering: {len(real_violations)}")
        if real_violations:
            for v in real_violations[:10]:
                print(v)
            if len(real_violations) > 10:
                print(f"    ... and {len(real_violations) - 10} more")
            return False
        else:
            print("    All leakage from short tool names (acceptable)")
            return True


def verify_atlas(
    atlas_entries: list[GroundTruthEntry],
    seed_entries: list[GroundTruthEntry] | None = None,
    synthetic_entries: list[GroundTruthEntry] | None = None,
    seed_path: Path | None = None,
    synthetic_path: Path | None = None,
    atlas_path: Path | None = None,
) -> bool:
    """Run atlas-specific verification checks. Returns True if all pass."""
    passed = True

    print_header("MCP-Atlas Ground Truth Verification")

    # --- [A] Atlas Data Integrity ---
    print_section(1, "Atlas Data Integrity")
    issues: list[str] = []

    non_atlas_source = [e for e in atlas_entries if e.source != "external_mcp_atlas"]
    if non_atlas_source:
        issues.append(
            f"{len(non_atlas_source)} entries with wrong source (expected 'external_mcp_atlas')"
        )

    not_verified = [e for e in atlas_entries if not e.manually_verified]
    if not_verified:
        issues.append(f"{len(not_verified)} entries not manually_verified")

    no_origin_task = [e for e in atlas_entries if e.origin_task_id is None]
    if no_origin_task:
        issues.append(f"{len(no_origin_task)} entries missing origin_task_id")

    bad_step_index = [e for e in atlas_entries if e.step_index is None or e.step_index < 0]
    if bad_step_index:
        issues.append(f"{len(bad_step_index)} entries with invalid step_index (None or < 0)")

    non_single_step = [e for e in atlas_entries if e.task_type != "single_step"]
    if non_single_step:
        issues.append(f"{len(non_single_step)} entries with task_type != 'single_step'")

    if issues:
        for issue in issues:
            print(f"  FAIL: {issue}")
        passed = False
    else:
        print("  All entries: source='external_mcp_atlas'  PASS")
        print("  All entries: manually_verified=True        PASS")
        print("  All entries: origin_task_id present        PASS")
        print("  All entries: step_index >= 0               PASS")
        print("  All entries: task_type='single_step'       PASS")

    # --- [B] Atlas Basic Stats ---
    print_section(2, "Atlas Basic Stats")
    unique_tasks = {e.origin_task_id for e in atlas_entries if e.origin_task_id is not None}
    unique_servers = {e.correct_server_id for e in atlas_entries}

    print(f"  Entry count:        {len(atlas_entries)}")
    print(f"  Unique tasks:       {len(unique_tasks)}")
    print(f"  Unique servers:     {len(unique_servers)}")

    # Server distribution
    server_counter = Counter(e.correct_server_id for e in atlas_entries)
    print("\n  Server distribution:")
    for server_id, count in server_counter.most_common():
        pct = count / len(atlas_entries) * 100
        print(f"    {server_id:<40} {count:>4} ({pct:>5.1f}%)")

    # Entries per task
    task_counter = Counter(e.origin_task_id for e in atlas_entries)
    task_counts = list(task_counter.values())
    if task_counts:
        mean_per_task = sum(task_counts) / len(task_counts)
        min_t, max_t = min(task_counts), max(task_counts)
        print(f"\n  Entries per task: min={min_t}, max={max_t}, mean={mean_per_task:.1f}")

    # Difficulty distribution
    diff_counter = Counter(e.difficulty.value for e in atlas_entries)
    print("\n  Difficulty distribution:")
    for diff in Difficulty:
        count = diff_counter.get(diff.value, 0)
        pct = count / len(atlas_entries) * 100 if atlas_entries else 0
        print(f"    {diff.value:<10} {count:>4} ({pct:>5.1f}%)")

    # Category distribution
    cat_counter = Counter(e.category.value for e in atlas_entries)
    print("\n  Category distribution:")
    for cat, count in cat_counter.most_common():
        pct = count / len(atlas_entries) * 100
        print(f"    {cat:<20} {count:>4} ({pct:>5.1f}%)")

    # --- [C] Tool Name Leakage ---
    print_section(3, "Tool Name Leakage (Atlas)")
    if not check_tool_name_leakage(atlas_entries, "atlas"):
        passed = False

    # --- [D] Merge Check ---
    print_section(4, "Merge Check")
    merge_paths: list[Path] = []
    merge_labels: list[str] = []
    if atlas_path:
        merge_paths.append(atlas_path)
        merge_labels.append(f"atlas ({len(atlas_entries)})")
    if seed_path and seed_entries is not None:
        merge_paths.append(seed_path)
        merge_labels.append(f"seed ({len(seed_entries)})")
    if synthetic_path and synthetic_entries is not None:
        merge_paths.append(synthetic_path)
        merge_labels.append(f"synthetic ({len(synthetic_entries)})")

    if len(merge_paths) >= 2:
        try:
            merged = merge_ground_truth(*merge_paths)
            print(f"  {' + '.join(merge_labels)} = {len(merged)} total")
            print("  Duplicate query_ids: 0")
            print("  Merge: PASS")
        except ValueError as e:
            print(f"  Merge: FAIL — {e}")
            passed = False
    else:
        print("  Skipped (need at least 2 sources for merge check)")

    # --- Verdict ---
    print_header("ATLAS VERDICT")
    if passed:
        print("  PASS — All atlas checks passed")
    else:
        print("  FAIL — See issues above")
    print()

    return passed


def verify(args: argparse.Namespace) -> bool:
    """Run all verification checks. Returns True if all pass."""
    passed = True
    synthetic_path = Path(args.synthetic)
    seed_path = Path(args.seed)

    print_header("Ground Truth Verification Report")

    # --- Check file existence ---
    if not synthetic_path.exists():
        print(f"\nERROR: Synthetic file not found: {synthetic_path}")
        return False
    if not seed_path.exists():
        print(f"\nERROR: Seed file not found: {seed_path}")
        return False

    synthetic = load_ground_truth(synthetic_path)
    seed = load_ground_truth(seed_path, only_verified=True)

    # --- [1] Basic Stats ---
    print_section(1, "Basic Stats")
    print(f"  Synthetic entries: {len(synthetic)}")
    print(f"  Seed entries:      {len(seed)}")

    # Difficulty distribution
    synth_by_diff = split_by_difficulty(synthetic)
    seed_by_diff = split_by_difficulty(seed)

    print(f"\n  {'Difficulty':<10} {'Synthetic':>10} {'%':>8} {'Seed':>8} {'%':>8}")
    print(f"  {'-' * 10} {'-' * 10} {'-' * 8} {'-' * 8} {'-' * 8}")
    for diff in Difficulty:
        s_count = len(synth_by_diff[diff])
        s_pct = s_count / len(synthetic) * 100 if synthetic else 0
        sd_count = len(seed_by_diff[diff])
        sd_pct = sd_count / len(seed) * 100 if seed else 0
        print(f"  {diff.value:<10} {s_count:>10} {s_pct:>7.1f}% {sd_count:>8} {sd_pct:>7.1f}%")

    # Server distribution
    server_counter = Counter(e.correct_server_id for e in synthetic)
    print("\n  Server distribution:")
    for server_id, count in server_counter.most_common():
        print(f"    {server_id:<40} {count:>4} entries")

    # Category distribution
    cat_counter = Counter(e.category.value for e in synthetic)
    print("\n  Category distribution:")
    for cat, count in cat_counter.most_common():
        print(f"    {cat:<20} {count:>4} entries")

    # --- [2] Quality Gate ---
    print_section(2, "Quality Gate")
    gate = QualityGate()

    # Difficulty distribution check
    try:
        gate.check_difficulty_distribution(synthetic, seed)
        print("  Difficulty distribution: PASS")
    except QualityGateError as e:
        print(f"  Difficulty distribution: FAIL — {e}")
        passed = False

    # Tool name leakage check (with false-positive filtering)
    if not check_tool_name_leakage(synthetic, "synthetic"):
        passed = False

    # --- [3] Samples ---
    print_section(3, "Samples by Difficulty")
    for diff in Difficulty:
        entries = synth_by_diff[diff]
        print(f"\n  [{diff.value.upper()}]")
        for entry in entries[:3]:
            print(f'    Q: "{entry.query}"')
            print(f"    A: {entry.correct_tool_id}")
            print()

    # --- [4] Merge Check ---
    print_section(4, "Merge Check (seed + synthetic)")
    try:
        merged = merge_ground_truth(seed_path, synthetic_path)
        print(f"  Seed ({len(seed)}) + Synthetic ({len(synthetic)}) = {len(merged)} total")
        print("  Duplicate query_ids: 0")
        print("  Merge: PASS")
    except ValueError as e:
        print(f"  Merge: FAIL — {e}")
        passed = False

    # --- [5] Source/Verified Check ---
    print_section(5, "Data Integrity")
    non_synthetic = [e for e in synthetic if e.source != "llm_synthetic"]
    unverified_seed = [e for e in seed if not e.manually_verified]
    synth_status = "PASS" if not non_synthetic else f"FAIL ({len(non_synthetic)} wrong)"
    seed_status = "PASS" if not unverified_seed else f"FAIL ({len(unverified_seed)} wrong)"
    print(f"  All synthetic entries have source='llm_synthetic': {synth_status}")
    print(f"  All seed entries are manually_verified:            {seed_status}")
    if non_synthetic or unverified_seed:
        passed = False

    # --- [6] Verdict ---
    print_header("VERDICT")
    if passed:
        print("  PASS — All checks passed")
    else:
        print("  FAIL — See issues above")
    print()

    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify ground truth quality")
    parser.add_argument("--synthetic", default="data/ground_truth/synthetic.jsonl")
    parser.add_argument("--seed", default="data/ground_truth/seed_set.jsonl")
    parser.add_argument("--atlas", default=None, help="MCP-Atlas per-step GT JSONL file")
    args = parser.parse_args()

    all_ok = True

    # Atlas verification (when --atlas provided)
    if args.atlas:
        atlas_path = Path(args.atlas)
        if not atlas_path.exists():
            print(f"\nERROR: Atlas file not found: {atlas_path}")
            sys.exit(1)

        atlas_entries = load_ground_truth(atlas_path)

        # Load seed if available (for merge check)
        seed_path = Path(args.seed)
        seed_entries = None
        if seed_path.exists():
            seed_entries = load_ground_truth(seed_path, only_verified=True)

        # Load synthetic if available and file exists (for merge check)
        synthetic_path = Path(args.synthetic)
        synthetic_entries = None
        if synthetic_path.exists():
            synthetic_entries = load_ground_truth(synthetic_path)

        atlas_ok = verify_atlas(
            atlas_entries=atlas_entries,
            seed_entries=seed_entries,
            synthetic_entries=synthetic_entries,
            seed_path=seed_path if seed_entries is not None else None,
            synthetic_path=synthetic_path if synthetic_entries is not None else None,
            atlas_path=atlas_path,
        )
        if not atlas_ok:
            all_ok = False

    # Synthetic+Seed verification (backwards compatible: runs when no --atlas, or when both exist)
    synthetic_path = Path(args.synthetic)
    seed_path = Path(args.seed)
    if synthetic_path.exists() and seed_path.exists() and not args.atlas:
        synth_ok = verify(args)
        if not synth_ok:
            all_ok = False

    sys.exit(0 if all_ok else 1)
