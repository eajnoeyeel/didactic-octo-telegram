---
name: async-python-patterns
description: Apply async I/O patterns for this repository's Python code. Use when adding or refactoring async OpenAI, Qdrant, HTTP, or MCP stdio flows in `src/` or `proxy_verification/`. Do not use for pure data-model, docs-only, or static refactors.
---

# Async Python Patterns

- Share long-lived clients when the lifecycle is broader than one call. In the main project, prefer a single `AsyncQdrantClient`, `AsyncOpenAI`, or `httpx.AsyncClient` per workflow or app lifecycle.
- Do not introduce `requests` or sync SDK clients into async paths.
- Use `asyncio.gather(...)` only for independent work. Preserve deterministic sequencing when the second step depends on the first.
- Keep cleanup explicit for clients and subprocess-backed resources.
- In tests, prefer `AsyncMock` for external clients and small helper functions for end-to-end stdio flows.
- In `proxy_verification/`, avoid async fixtures that keep `stdio_client(...)` open across setup and teardown; the helper pattern in the existing tests is the safer default here.
