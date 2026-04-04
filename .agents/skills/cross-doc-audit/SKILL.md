---
name: cross-doc-audit
description: Cross-document consistency audit for the entire repository. Compare all docs, rules, evals, memory, and AGENTS.md against each other to find conflicts, staleness, and gaps. Use when (1) the user says "정합성 검토", "cross-doc audit", "document consistency check", or "alignment check", (2) after significant design changes that touch multiple documents, (3) after ADR decisions or experiment pivots that should propagate across docs.
---

# Cross-Document Audit

Compare documents **against each other**, not individually. Find conflicts that could send the project in the wrong direction.

## Scope

Scan all of:

| Category | Paths |
|----------|-------|
| Design (SOT) | `docs/design/*.md` |
| Plans | `docs/plan/*.md` |
| Experiments | `docs/design/experiment-*.md`, `.Codex/evals/E*.md` |
| ADRs | `docs/adr/*.md` |
| Research | `docs/research/*.md` |
| Handoffs | `docs/handoff/*.md` |
| Progress | `docs/progress/*.md` |
| Rules | `.Codex/rules/*.md` |
| Agents | `.Codex/agents/*.md`, `docs/AGENTS.md` |
| Project root | `AGENTS.md` |
| Memory | `~/.Codex/projects/.../memory/*.md` |
| Conventions | `docs/CONVENTIONS.md` |

## Execution

### Phase 1 — Discovery & Classification

Use parallel Explore agents to read all documents above. For each document, record:
- **Role**: what it explains (design / plan / eval / research / ops / meta)
- **SOT status**: is this a source of truth, or derived from another doc?
- **Last updated**: from file content or git blame

Apply the SOT hierarchy from AGENTS.md: `docs/design/` > `docs/plan/` > code > everything else.

### Phase 2 — Cross-Document Consistency

Compare documents pairwise along these axes. Use parallel agents for independent comparisons.

**Structural alignment:**
- Architecture descriptions match across design docs, AGENTS.md, rules, and implementation plans
- Component names, layer boundaries, and responsibility scopes are consistent
- Module paths in code-structure.md match what's planned in implementation.md

**Experiment coherence:**
- Experiment goals in experiment-design.md match eval definitions in `.Codex/evals/`
- Metrics, thresholds, and success criteria are consistent between design and eval files
- GT strategy in ground-truth-design.md aligns with eval workflow rules and experiment details
- ADR decisions (especially ADR-0011, ADR-0012) are reflected in all downstream docs

**Terminology consistency:**
- tool_id format, query_id format, separator conventions
- Strategy names (Sequential/Parallel/Taxonomy-gated vs A/B/C)
- GT source labels (seed/external/synthetic), task_type values
- Metric names and threshold values

**Temporal coherence:**
- No stale pre-pivot content (e.g., old enriched description pipeline, old multi-label GT)
- Recent ADR decisions propagated to all affected documents
- Memory entries consistent with current document state

### Phase 3 — Change Propagation Check

For each recent design change (identify via git log and ADR dates):
1. List all documents that should reflect the change
2. Mark which ones do and which ones don't
3. Flag documents stuck in a pre-change state

### Phase 4 — Prioritized Findings

Classify every finding:

| Priority | Criteria | Example |
|----------|----------|---------|
| **P0** | Directly causes wrong implementation, experiment, or interpretation | SOT says single-step GT but eval file still uses multi-label Hit@K |
| **P1** | Causes significant confusion for collaborators or future sessions | Architecture doc lists module that doesn't exist and isn't planned |
| **P2** | Minor terminology, formatting, or cosmetic inconsistency | Korean/English mixed naming in one doc but not another |

### Phase 5 — Report

Output in this exact structure:

```markdown
# Cross-Document Audit Report — {date}

## Overall Status
{1-3 sentence summary: how aligned is the repo?}

## P0 — Critical Conflicts
| # | Documents | Conflict | SOT | Fix |
|---|-----------|----------|-----|-----|
| 1 | A.md vs B.md | ... | A.md | Update B.md section X |

## P1 — Significant Inconsistencies
| # | Documents | Issue | Fix |
|---|-----------|-------|-----|

## P2 — Minor Issues
| # | Documents | Issue | Fix |
|---|-----------|-------|-----|

## Deprecated / Deletion Candidates
- {file or section}: reason

## SOT Gaps
- {area where SOT is unclear or needs redefinition}

## Memory Sync Issues
- {memory entry}: {conflict with current docs}

## Recommended Actions
### Immediate (do now)
1. ...

### Deferred (next session)
1. ...
```

## Anti-Patterns

- Do NOT evaluate documents in isolation — always compare pairs/groups
- Do NOT report "this doc exists and looks fine" — only report cross-doc conflicts
- Do NOT restate document contents — cite the specific conflicting lines/sections
- Do NOT flag style preferences as P0 — reserve P0 for direction-altering conflicts
