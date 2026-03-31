# Scope and Priority

Use this file to keep the skill body lean. It defines the default audit surfaces, authority tiers, and change-propagation shortcuts for this repository.

## Meta-Rules First

Read these before evaluating subject-matter documents:

| Surface | Meaning |
|---------|---------|
| `.codex/AGENTS.md` | Codex-side working order for the repository |
| `docs/AGENTS.md` | Documentation policy and document-specific source priority |
| `proxy_verification/AGENTS.md` | Local override for the proxy prototype subtree |

These are not just another low-priority doc set. They define how to interpret the other documents.

## Subject-Matter Priority

| Priority | Surface | Default meaning |
|----------|---------|-----------------|
| 1 | `docs/design/` | Target-state source of truth for the main project |
| 2 | `docs/adr/` | Decision source of truth; newer accepted ADRs win on their topic |
| 3 | `docs/plan/`, `docs/progress/`, `docs/handoff/` | Derived or propagation surfaces that should mirror current design decisions |
| 4 | `docs/context/`, `docs/mentoring/` | Context, open decisions, and question tracking |
| 5 | `docs/research/`, `docs/papers/` | Evidence archive; informative, not normative |
| 6 | `docs/superpowers/` | Historical working context, not implementation truth |
| 7 | `CLAUDE.md`, `.claude/`, `.codex/skills/`, `.claude/skills/` | Operational memory and workflow guidance unless a nearer AGENTS file says otherwise |

Apply one extra rule for the proxy prototype:

| Proxy priority | Surface | Default meaning |
|----------------|---------|-----------------|
| 1 | `proxy_verification/src/`, `tests/`, `config.json` | Local implementation truth for the prototype |
| 2 | `proxy_verification/AGENTS.md` | Local operating rules and source priority |
| 3 | `proxy_verification/docs/`, `proxy_verification/CLAUDE.md` | Reports and guidance, not implementation truth |

## Default Audit Surfaces

| Path pattern | Category | Expected role |
|--------------|----------|---------------|
| `.codex/AGENTS.md` | repo-rules | Codex-side working order |
| `docs/AGENTS.md` | docs-rules | Documentation policy and doc-level authority |
| `docs/CONVENTIONS.md` | docs-rules | Documentation conventions and cross-link policy |
| `CLAUDE.md` | root-guidance | Project memory and quick pointers |
| `docs/PLANNING_DESIGN_OVERVIEW.md` | overview | High-level bridge document between design and plans |
| `docs/context/*.md` | context | Project overview and north-star framing |
| `docs/design/*.md` | design | Architecture, metrics, experiments, GT, code structure |
| `docs/adr/*.md` | adr | Architectural and process decisions |
| `docs/plan/*.md` | plan | Implementation roadmap and checklist |
| `docs/progress/*.md` | progress | Shipped status and current state summary |
| `docs/handoff/*.md` | handoff | Change-bridge documents after pivots |
| `docs/research/*.md` | research | Problem-focused evidence synthesis |
| `docs/papers/*.md` | papers | Individual paper archive |
| `docs/mentoring/*.md` | mentoring | Questions and mentor-driven pivots |
| `docs/superpowers/**/*.md` | superpowers | Historical specs and generated plans |
| `**/README*.md` | readme | Supporting operational or dataset documentation |
| `.claude/rules/*.md` | claude-rules | Claude-side operational memory |
| `.claude/agents/*.md` | claude-agents | Project-specific agent instructions |
| `.claude/evals/*` | eval-memory | Experiment result notes and local evidence |
| `.claude/skills/*/SKILL.md` | claude-skills | Workflow memory if the skill encodes project facts |
| `.codex/skills/*/SKILL.md` | codex-skills | Workflow memory if the skill encodes project facts |
| `proxy_verification/AGENTS.md` | proxy-rules | Local rules for the prototype |
| `proxy_verification/CLAUDE.md` | proxy-guidance | Prototype memory and pointers |
| `proxy_verification/docs/*.md` | proxy-reports | Verification reports and analysis |

## Memory Inclusion Rules

1. Probe tool-provided memory resources first.
2. If no external memory resource is connected, explicitly say so.
3. Treat repo-local memory-like guidance as fallback memory:
   - `CLAUDE.md`
   - `.claude/agents/`
   - `.claude/rules/`
   - `.claude/evals/`
   - project-specific skill files under `.claude/skills/` or `.codex/skills/` when they contain factual project guidance
   - drop generic vendor or system skills from the audit scope if they do not encode repository facts
4. Add user-provided external memory directories only when the user explicitly points to them or when the environment exposes them safely.
5. Exclude binary assets, cache directories, and raw logs unless a document relies on them as canonical evidence.

## Change-Propagation Shortcuts

Use these shortcuts before doing a full-text repository search.

| Change starts in | Re-check these surfaces next |
|------------------|------------------------------|
| `docs/design/architecture.md` or `docs/design/code-structure.md` | `CLAUDE.md`, `docs/context/project-overview.md`, `docs/design/architecture-diagrams.md`, `docs/plan/implementation.md`, `docs/progress/status-report.md`, `.claude/rules/architecture.md`, relevant skill files |
| `docs/design/evaluation.md`, `docs/design/metrics-rubric.md`, `docs/design/metrics-dashboard.md` | `docs/design/experiment-design.md`, `docs/design/experiment-details.md`, `docs/research/evaluation-metrics.md`, `docs/mentoring/open-questions.md`, `docs/plan/checklist.md`, `.claude/evals/*.md`, `CLAUDE.md` |
| `docs/design/ground-truth-design.md`, `docs/design/ground-truth-schema.md`, `docs/adr/0011-*`, `docs/adr/0012-*` | `docs/handoff/*.md`, `docs/progress/status-report.md`, `docs/plan/checklist.md`, `docs/research/evaluation-benchmark-design.md`, `docs/research/external-benchmarks-20260328.md`, `.claude/evals/*.md`, `CLAUDE.md` |
| `docs/design/experiment-design.md` or `docs/design/experiment-details.md` | `CLAUDE.md`, `.claude/evals/*.md`, `docs/progress/status-report.md`, `docs/plan/implementation.md`, `docs/mentoring/*.md` |
| `docs/adr/*.md` | Every document that references the ADR number or the renamed concept |
| `docs/handoff/*.md` | The design, plan, progress, and rules docs that should reflect the handoff decision |
| `proxy_verification/AGENTS.md`, `proxy_verification/CLAUDE.md`, `proxy_verification/docs/*.md` | `proxy_verification/src/`, `tests/`, `config.json`, and any root-level architecture doc that describes bridge or proxy behavior |

## Common False Positives

- Planned modules appearing in design docs are not automatically wrong if they are clearly marked as planned.
- Research or papers docs may preserve rejected alternatives. Flag them only when they read like current guidance.
- Historical specs under `docs/superpowers/` are not current truth unless a newer doc points back to them as active input.
- `CLAUDE.md` is intentionally condensed. Missing detail there is not a problem by itself unless it contradicts current design docs.
