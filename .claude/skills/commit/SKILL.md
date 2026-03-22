---
name: commit
description: Create git commits. Always make granular, per-issue commits — one logical change per commit. Use when the user says "commit", "make commits", "granular commits", or after completing a set of code changes.
disable-model-invocation: true
argument-hint: "[optional message override]"
---

# Commit Skill

Create granular git commits — one logical change per commit.

## Rules

1. **One issue per commit.** Never bundle unrelated changes into a single commit. If you fixed 5 bugs, that's 5 commits.
2. **Stage surgically.** Use `git add <specific files>` — never `git add .` or `git add -A`.
3. **Commit message format:**
   - First line: `<type>(<scope>): <summary>` (under 72 chars)
   - Types: `fix`, `feat`, `refactor`, `chore`, `docs`, `test`
   - Blank line, then a brief explanation of **why** (not what)
   - Never end with `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`
4. **Order commits logically.** Infrastructure/schema changes before the code that depends on them.
5. **Verify before committing.** Run `git diff --cached` mentally to confirm only relevant files are staged.

## Process

1. Run `git status` and `git diff` to see all changes
2. Group changes by logical issue/fix
3. For each group:
   - Stage only the relevant files
   - Write a commit message following the format above
   - Commit
4. Run `git log --oneline -n <count>` to show the user the result

## Override

If `$ARGUMENTS` is provided, use it as the commit message body instead of generating one.
