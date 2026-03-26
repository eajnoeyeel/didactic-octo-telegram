# Documentation Instructions

This directory is secondary context, not the primary source of truth for implementation.

## Source Priority

1. Current code, tests, and config
2. This file and the repository root [`AGENTS.md`](/Users/iyeonjae/Desktop/shockwave/mcp-discovery/AGENTS.md)
3. Existing docs in this directory
4. Legacy Claude-specific material

If a design or plan doc no longer matches the code, update the doc or mark the gap explicitly. Do not silently treat the doc as authoritative.

## Editing Rules

- Use Korean prose unless the file already uses English for its main content.
- Add or update `> 최종 업데이트: YYYY-MM-DD` when making a meaningful doc edit.
- Keep planned work clearly labeled as planned.
- Do not claim that modules, commands, or experiments exist unless they are present in the repository now.
- Prefer concise hub documents that point to focused files instead of long duplicated summaries.
- Leave brainstorming history intact unless the user explicitly asks for a rewrite; targeted correction notes are usually safer.

## Directory Notes

- `design/` and `plan/` describe intended architecture and execution. They frequently drift behind or ahead of implementation.
- `research/` and `papers/` are evidence archives. Follow [`docs/CONVENTIONS.md`](/Users/iyeonjae/Desktop/shockwave/mcp-discovery/docs/CONVENTIONS.md) for structure, naming, and cross-linking.
- `superpowers/` captures previous agent-generated plans and specs. Treat it as historical working context, not implementation truth.

## Verification

When a doc edit references code paths, commands, or behavior, spot-check the referenced files or commands first. If you cannot verify a claim from the current repo state, say so in the doc rather than stating it as fact.
