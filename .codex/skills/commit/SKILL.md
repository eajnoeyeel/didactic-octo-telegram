---
name: commit
description: Create surgical git commits in this repository after verification has passed and the user asked to commit. Use when the user explicitly requests commits. Do not use automatically after every change or before checks complete.
---

# Commit

1. Review `git status` and the diff before staging anything.
2. Stage only the files that belong to one logical change. Never default to `git add .`.
3. Keep commit messages concise and conventional, for example `feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, or `refactor: ...`.
4. Prefer one logical issue per commit.
5. Verify the staged diff matches the intended scope before creating the commit.
