# Proxy Verification Instructions

This directory is a separate MCP proxy prototype. These rules apply in addition to the repository root [`AGENTS.md`](/Users/iyeonjae/Desktop/shockwave/mcp-discovery/AGENTS.md).

## Source Priority

1. Current files under `proxy_verification/src/`, `tests/`, and `config.json`
2. This file
3. `proxy_verification/docs/`
4. Root-level planning docs that mention future Bridge/Router work

Treat `proxy_verification/docs/` as reports and analysis, not as the implementation source of truth.

## Local Layout

- `src/proxy_server.py`: stdio MCP entry point that exposes namespaced tools.
- `src/proxy_client.py`: connect-per-call backend client.
- `src/registry.py`: backend discovery and tool mapping.
- `src/models.py`: Pydantic config and mapping models.
- `scripts/verify.py`: end-to-end verification script.
- `tests/`: async pytest coverage, including optional Node-backed tests.

## Coding Rules

- Python target is 3.12 with type hints on public functions.
- Tool namespaces use `__`, not `::`.
- Keep stdout clean inside MCP servers. Protocol traffic owns stdout, so diagnostics belong on stderr or in test output.
- `print()` is acceptable in CLI/reporting code such as `scripts/verify.py`, but avoid noisy stdout logging inside `src/proxy_server.py`.
- Prefer single-scope helper functions around `stdio_client(...)` in tests instead of async fixtures that span setup and teardown. This repo already hit anyio cancel-scope issues with the fixture approach.
- Keep `config.json` shape and [`src/models.py`](/Users/iyeonjae/Desktop/shockwave/mcp-discovery/proxy_verification/src/models.py) validators in sync.

## Current Boundaries

- The connect-per-call design is intentional for this prototype. Do not refactor it into persistent sessions unless the user asks for that change.
- Node.js-backed tests are optional and must stay guarded by `HAS_NPX` / `@pytest.mark.skipif`.
- The verification prototype is allowed to be simpler than the planned production bridge.

## Verification

Run local checks from this directory:

```bash
uv run pytest -v
uv run pytest tests/test_nodejs_backends.py -v
uv run python scripts/verify.py
```

If `npx` is unavailable, call out the skipped Node-backed coverage explicitly.
