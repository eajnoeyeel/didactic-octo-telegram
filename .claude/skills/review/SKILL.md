---
name: review
description: Review a pull request or local diff for bugs, security issues, and project convention violations. Use when the user says "review", "review PR", "review this PR", or "review changes".
argument-hint: "[PR number, branch name, or omit for current diff]"
---

# PR Review Skill

Perform a thorough code review against this project's architecture, conventions, and best practices.

## Resolve Target

Determine what to review based on `$ARGUMENTS`:

| Input                    | Action                                                      |
| ------------------------ | ----------------------------------------------------------- |
| PR number (e.g. `123`)   | `gh pr diff 123`, `gh pr view 123 --json title,body,files`  |
| Branch name              | `git diff master...<branch>`                                |
| Empty / omitted          | `git diff HEAD` (unstaged + staged changes)                 |

## Review Checklist

### 1. Correctness & Logic

- [ ] No off-by-one errors, null/empty edge cases, or silent failures
- [ ] Async code uses `await` correctly — no fire-and-forget coroutines
- [ ] SQLAlchemy queries use proper session handling (no leaked sessions)
- [ ] State mutations are intentional — no accidental shared mutable defaults
- [ ] Error handling doesn't swallow exceptions silently (`except: pass`)

### 2. Project Conventions (from CLAUDE.md)

- [ ] Changes are surgical — no unrelated formatting, refactoring, or "improvements"
- [ ] No speculative features, premature abstractions, or over-engineering
- [ ] Matches existing code style (naming, patterns, indentation)
- [ ] Imports follow existing conventions (stdlib → third-party → local)
- [ ] Commit messages follow `<type>(<scope>): <summary>` if commits are included

### 3. Architecture Alignment

- [ ] **Routes** live in `api/endpoints/`, composed via `api/routes.py`
- [ ] **Business logic** in `services/`, not in route handlers
- [ ] **DB access** via repositories in `db/repositories/`, not raw queries in services
- [ ] **LLM calls** go through `providers/` strategy pattern (MockProvider / OpenAIProvider)
- [ ] **Pydantic models** in `models/schemas.py` for request/response shapes
- [ ] **RAG** uses `rag/` module — no ad-hoc embedding or retrieval code
- [ ] **Config** via `pydantic-settings` in `core/config.py`, not hardcoded values

### 4. Security

- [ ] No hardcoded secrets, API keys, or credentials
- [ ] No SQL injection risk (parameterized queries or ORM only)
- [ ] User input validated at API boundary before reaching services
- [ ] No sensitive data (PII, keys) in log statements
- [ ] PII masking boundary respected — raw text doesn't leak past masking step

### 5. LangChain / LCEL

- [ ] LCEL chains use `RunnableLambda`, `RunnableParallel` — no deprecated `LLMChain` or `SequentialChain`
- [ ] `PromptTemplate` used for formatting, not string concatenation
- [ ] `ainvoke()` preferred over `invoke()` in async contexts, with sync fallback (`if hasattr(chain, "ainvoke")`)
- [ ] Graceful ImportError handling — chains fall back to direct provider calls when langchain is unavailable
- [ ] Callback handlers follow `BaseCallbackHandler` pattern for Langfuse integration
- [ ] RAG uses `FAISS` + `OpenAIEmbeddings` from langchain — no ad-hoc vector code
- [ ] No deprecated LangChain APIs (check `langchain_core` vs old `langchain.` imports)

### 6. Performance & Reliability

- [ ] No N+1 query patterns (use JOINs or eager loading)
- [ ] Bulk operations preferred over per-item DB calls in loops
- [ ] Concurrency-safe — no shared mutable state across async tasks
- [ ] Langfuse tracing calls use graceful fallback (offline-safe)

### 7. Testing

- [ ] New/modified logic has corresponding test coverage
- [ ] Tests use file-based SQLite (via `conftest.py`), not PostgreSQL
- [ ] MockProvider used in tests — no real LLM calls
- [ ] Edge cases covered (empty input, duplicates, missing fields)
- [ ] If no tests added for non-trivial changes, flag it

### 8. Frontend (if applicable)

- [ ] TypeScript types match backend response schemas
- [ ] API calls use `lib/api.ts` client — no raw `fetch` scattered in components
- [ ] No `any` types where a proper interface exists
- [ ] Shared UI extracted to `src/components/` when reused across pages

## Output Format

Write the review as follows:

```markdown
## Summary
(1-2 sentence overview: what the changes do and overall assessment)

## What's Good
(Positive observations — well-structured code, good test coverage, etc.)

## Issues

### Critical (must fix before merge)
- `file_path:line` — Description of the issue and why it matters

### Warnings (should fix)
- `file_path:line` — Description and suggested fix

### Suggestions (nice to have)
- `file_path:line` — Improvement idea

## Checklist
- Correctness: PASS/FAIL
- Conventions: PASS/FAIL
- Architecture: PASS/FAIL
- Security: PASS/FAIL
- LangChain/LCEL: PASS/FAIL
- Performance: PASS/FAIL
- Tests: PASS/FAIL

## Verdict
APPROVE / REQUEST_CHANGES — (one-line rationale)
```

## Rules

1. **Read before judging.** Read every changed file in full context — not just the diff lines. Understand surrounding code before flagging issues.
2. **No false positives.** Only flag real issues. If you're unsure, say so rather than presenting it as definitive.
3. **Be specific.** Always include `file_path:line` references. Vague feedback is useless.
4. **Respect existing code.** Don't flag pre-existing issues unless the PR makes them worse. Review the diff, not the whole codebase.
5. **Severity matters.** Distinguish critical bugs from style nitpicks. Don't block a PR over a naming preference.
6. **Suggest fixes.** For each issue, include a concrete fix or direction — don't just say "this is wrong."
7. **Skip the obvious.** Don't praise trivial things or pad the review. If everything looks good, say so briefly and approve.
