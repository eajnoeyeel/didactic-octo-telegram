---
name: change-verification
description: Run the repository's pre-handoff verification after non-trivial code changes. Use before reporting completion on code changes. Do not use for pure brainstorming or small docs-only edits.
---

# Change Verification

## Main Project

1. Run `uv run ruff check src tests`.
2. Run the smallest relevant `pytest` slice for the changed files.
3. If shared pipeline/model/config behavior changed, prefer the affected unit suites over a single smoke test.
4. Inspect the diff for debug leftovers, accidental file churn, and stale docs.
5. Report skipped checks explicitly when credentials, Qdrant, or other external services are unavailable.

## Proxy Prototype

If the change touched `proxy_verification/`:

1. Run `uv run pytest -v` from that directory.
2. Run `uv run python scripts/verify.py` when routing, discovery, or backend integration changed.
3. Call out skipped Node-backed coverage if `npx` is unavailable.
