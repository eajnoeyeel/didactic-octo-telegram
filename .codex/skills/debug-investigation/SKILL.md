---
name: debug-investigation
description: Investigate failing tests, runtime errors, and unexpected behavior in this repository. Use for reproduction, root-cause analysis, and regression fixes. Do not use for greenfield feature work or high-level architecture brainstorming.
---

# Debug Investigation

1. Reproduce the failure with the smallest command or test case first.
2. Localize the issue before editing: config/env, data shape, async lifecycle, vector-store behavior, model validation, or subprocess/MCP transport.
3. Main repo failure patterns worth checking first:
   - missing `OPENAI_API_KEY` / Qdrant settings
   - `tool_id` validation mismatches against `::`
   - embedding dimension drift
   - empty or malformed JSONL inputs
   - docs referencing modules that are not implemented
4. `proxy_verification/` failure patterns worth checking first:
   - `npx` missing
   - proxy logs leaking onto stdout
   - unknown or mis-namespaced tool IDs
   - pytest/anyio teardown issues from async fixtures around `stdio_client`
5. Add or tighten a regression test when feasible.
6. Report root cause, supporting evidence, the fix, and anything still unverified.
