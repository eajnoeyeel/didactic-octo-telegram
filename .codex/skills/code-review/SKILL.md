---
name: code-review
description: Review code changes in this repository for bugs, regressions, and missing tests. Use after making changes or when the user asks for a review. Do not use for implementing features or for docs-only proofreading.
---

# Code Review

1. Inspect the current diff and limit attention to changed files plus directly impacted callers and tests.
2. Prioritize correctness, regression risk, broken assumptions, and missing coverage over style comments.
3. In the main project, check for async I/O mistakes, `Settings` bypasses, `::` tool ID drift, weak Qdrant/OpenAI error handling, and stale-doc assumptions.
4. In `proxy_verification/`, check for stdout contamination, wrong `__` namespace handling, missing `npx` guards, and async test lifecycle mistakes around `stdio_client`.
5. Report findings first, ordered by severity, with file references. If no findings remain, say that explicitly and mention residual risk or missing verification.
