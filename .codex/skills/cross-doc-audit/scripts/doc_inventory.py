#!/usr/bin/env python3
"""Inventory document and memory surfaces for repository-wide consistency audits."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from pathlib import Path

DEFAULT_SUFFIXES = {".md", ".mdx", ".markdown"}
SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".uv-cache",
    ".venv",
    ".worktrees",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}
UPDATE_PATTERNS = (
    re.compile(r"^> 최종 업데이트:\s*(\d{4}-\d{2}-\d{2})\s*$"),
    re.compile(r"^> 작성:\s*.*?\|\s*최종 업데이트:\s*(\d{4}-\d{2}-\d{2})\s*$"),
)
TITLE_PATTERN = re.compile(r"^#\s+(.+?)\s*$")


@dataclass(frozen=True)
class PatternSpec:
    glob: str
    category: str
    authority: str
    memory_surface: bool
    note: str


@dataclass
class Entry:
    path: str
    category: str
    authority: str
    memory_surface: bool
    update_marker: str | None
    last_commit_date: str | None
    title: str | None
    note: str


PS = PatternSpec

PATTERN_SPECS = (
    PS(".codex/AGENTS.md", "repo-rules", "working-order", True, "Codex working order"),
    PS("docs/AGENTS.md", "docs-rules", "docs-policy", True, "Documentation policy"),
    PS(
        "docs/CONVENTIONS.md",
        "docs-rules",
        "docs-policy",
        False,
        "Documentation conventions",
    ),
    PS("CLAUDE.md", "root-guidance", "secondary-guidance", True, "Project quick guidance"),
    PS(
        "docs/PLANNING_DESIGN_OVERVIEW.md",
        "overview",
        "supporting-context",
        False,
        "High-level planning overview",
    ),
    PS(
        "docs/context/*.md",
        "context",
        "supporting-context",
        False,
        "Project overview and framing",
    ),
    PS("docs/design/*.md", "design", "design-sot", False, "Target-state design"),
    PS("docs/adr/*.md", "adr", "decision-sot", False, "Accepted or pending decisions"),
    PS("docs/plan/*.md", "plan", "derived-plan", False, "Implementation planning"),
    PS(
        "docs/progress/*.md",
        "progress",
        "derived-status",
        False,
        "Current progress summary",
    ),
    PS(
        "docs/handoff/*.md",
        "handoff",
        "change-bridge",
        False,
        "Change propagation handoff",
    ),
    PS("docs/research/*.md", "research", "evidence", False, "Problem-focused research"),
    PS("docs/papers/*.md", "papers", "evidence", False, "Paper archive"),
    PS(
        "docs/mentoring/*.md",
        "mentoring",
        "decision-backlog",
        False,
        "Mentoring notes and open questions",
    ),
    PS(
        "docs/superpowers/**/*.md",
        "superpowers",
        "historical-context",
        False,
        "Historical generated plans",
    ),
    PS(
        "**/README*.md",
        "readme",
        "supporting-doc",
        False,
        "Supporting operational or dataset documentation",
    ),
    PS(".claude/rules/*.md", "claude-rules", "operational-memory", True, "Claude-side rules"),
    PS(
        ".claude/agents/*.md",
        "claude-agents",
        "operational-memory",
        True,
        "Claude-side agent memory",
    ),
    PS(".claude/evals/*", "eval-memory", "local-evidence", True, "Local experiment memory"),
    PS(
        ".claude/skills/*/SKILL.md",
        "claude-skills",
        "workflow-memory",
        True,
        "Inspect for project facts before keeping in scope",
    ),
    PS(
        ".codex/skills/*/SKILL.md",
        "codex-skills",
        "workflow-memory",
        True,
        "Inspect for project facts before keeping in scope",
    ),
    PS(
        "proxy_verification/AGENTS.md",
        "proxy-rules",
        "proxy-policy",
        True,
        "Proxy local rules",
    ),
    PS(
        "proxy_verification/CLAUDE.md",
        "proxy-guidance",
        "proxy-guidance",
        True,
        "Proxy quick guidance",
    ),
    PS(
        "proxy_verification/docs/*.md",
        "proxy-reports",
        "report-not-sot",
        True,
        "Proxy reports and analysis",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root to scan")
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format",
    )
    parser.add_argument(
        "--recent-first",
        action="store_true",
        help="Sort by last git commit date descending",
    )
    parser.add_argument(
        "--extra-glob",
        action="append",
        default=[],
        help="Additional glob pattern to include relative to --root",
    )
    return parser.parse_args()


def should_skip(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return any(part in SKIP_DIRS for part in relative_parts)


def read_head(path: Path, limit: int = 40) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    return text.splitlines()[:limit]


def extract_update_marker(lines: list[str]) -> str | None:
    for line in lines:
        stripped = line.strip()
        for pattern in UPDATE_PATTERNS:
            match = pattern.match(stripped)
            if match:
                return match.group(1)
    return None


def extract_title(lines: list[str]) -> str | None:
    for line in lines:
        match = TITLE_PATTERN.match(line.strip())
        if match:
            return match.group(1)
    return None


def classify(rel_path: str) -> PatternSpec | None:
    for spec in PATTERN_SPECS:
        if fnmatch(rel_path, spec.glob):
            return spec
    return None


def git_last_commit_date(root: Path, rel_path: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "log", "-1", "--format=%cs", "--", rel_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def gather_default_paths(root: Path) -> set[Path]:
    matches: set[Path] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path, root):
            continue
        if path.suffix.lower() not in DEFAULT_SUFFIXES:
            continue
        rel_path = path.relative_to(root).as_posix()
        if classify(rel_path):
            matches.add(path)
    return matches


def gather_extra_paths(root: Path, extra_globs: list[str]) -> set[Path]:
    matches: set[Path] = set()
    for pattern in extra_globs:
        for path in root.glob(pattern):
            if path.is_file() and not should_skip(path, root):
                matches.add(path)
    return matches


def build_entries(root: Path, paths: set[Path]) -> list[Entry]:
    entries: list[Entry] = []
    for path in sorted(paths):
        rel_path = path.relative_to(root).as_posix()
        spec = classify(rel_path)
        if spec is None:
            spec = PatternSpec(
                glob=rel_path,
                category="extra",
                authority="user-added",
                memory_surface=False,
                note="Included by --extra-glob",
            )
        lines = read_head(path)
        entries.append(
            Entry(
                path=rel_path,
                category=spec.category,
                authority=spec.authority,
                memory_surface=spec.memory_surface,
                update_marker=extract_update_marker(lines),
                last_commit_date=git_last_commit_date(root, rel_path),
                title=extract_title(lines),
                note=spec.note,
            )
        )
    return entries


def sort_entries(entries: list[Entry], recent_first: bool) -> list[Entry]:
    if recent_first:
        dated = sorted(
            (entry for entry in entries if entry.last_commit_date),
            key=lambda item: (item.last_commit_date or "", item.path),
            reverse=True,
        )
        undated = sorted(
            (entry for entry in entries if not entry.last_commit_date),
            key=lambda item: item.path,
        )
        return dated + undated
    return sorted(entries, key=lambda item: (item.category, item.path))


def render_table(entries: list[Entry]) -> str:
    headers = ("category", "authority", "mem", "updated", "git", "path")
    rows = []
    for entry in entries:
        rows.append(
            (
                entry.category,
                entry.authority,
                "Y" if entry.memory_surface else "N",
                entry.update_marker or "-",
                entry.last_commit_date or "-",
                entry.path,
            )
        )
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))
    lines = [
        "  ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers)),
        "  ".join("-" * widths[idx] for idx in range(len(headers))),
    ]
    for row in rows:
        lines.append("  ".join(value.ljust(widths[idx]) for idx, value in enumerate(row)))
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root directory not found: {root}")

    paths = gather_default_paths(root)
    paths.update(gather_extra_paths(root, args.extra_glob))
    entries = sort_entries(build_entries(root, paths), args.recent_first)

    if args.format == "json":
        print(json.dumps([asdict(entry) for entry in entries], ensure_ascii=False, indent=2))
    else:
        print(render_table(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
