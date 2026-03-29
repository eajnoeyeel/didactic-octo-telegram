---
name: cross-doc-audit
description: Repository-wide cross-document and memory consistency audit. Use when Codex needs to compare design docs, ADRs, plans, experiment specs or results, handoff docs, research notes, operating rules, architecture docs, work instructions, CLAUDE or AGENTS guidance, and available memory resources to find conflicts, stale decisions, source-of-truth gaps, deprecated content, or missing change propagation. Trigger on requests like "정합성 검토", "cross-doc audit", "alignment check", or after major design, ADR, experiment, or ground-truth changes.
---

# Cross-Doc Audit

Audit documents against each other from the project level. Optimize for conflicts that can misdirect implementation, experiments, or interpretation, not for isolated proofreading.

## Start Point

1. Read `.codex/AGENTS.md` first. Use its Working Order as the default authority spine.
2. Read `docs/AGENTS.md` before auditing repository documents.
3. If the audit touches `proxy_verification/`, read `proxy_verification/AGENTS.md` and apply its local source priority for that subtree.
4. Read [`references/scope-and-priority.md`](./references/scope-and-priority.md) for the default path map, authority tiers, and change-propagation heuristics.

## Workflow

### 1. Build the inventory first

1. Run the inventory script before making any judgment:

```bash
python .codex/skills/cross-doc-audit/scripts/doc_inventory.py --root .
```

2. Use JSON when you need to sort, filter, or compare recent changes programmatically:

```bash
python .codex/skills/cross-doc-audit/scripts/doc_inventory.py --root . --format json
python .codex/skills/cross-doc-audit/scripts/doc_inventory.py --root . --recent-first
```

3. Probe external memory surfaces when tools allow it:
   - Call `list_mcp_resources` and `list_mcp_resource_templates`.
   - Read memory-like resources if a memory server is available.
   - If no memory resource exists, say that explicitly and fall back to repo-local operational memory surfaces.
4. Treat repo-local memory surfaces as in-scope by default:
   - `CLAUDE.md`
   - `.claude/agents/`, `.claude/rules/`, `.claude/evals/`, and project-specific `.claude/skills/`
   - `.codex/AGENTS.md` and `.codex/skills/*/SKILL.md`
   - `proxy_verification/CLAUDE.md`, `proxy_verification/AGENTS.md`, `proxy_verification/docs/`
5. Add explicit non-Markdown artifacts only when they are canonical evidence for a design or experiment claim. Use `--extra-glob` for those cases.

### 2. Classify documents by role and boundary

For every in-scope item, classify these fields before looking for conflicts:

- document role
- responsibility boundary
- authority or source-of-truth status
- whether it is normative, derived, historical, or evidentiary
- which downstream documents should reflect its decisions

Do not skip this step. Many false positives come from comparing two documents that were never supposed to own the same decision.

### 3. Identify the source of truth per topic

Use the default authority rules in `references/scope-and-priority.md`, then refine topic by topic.

At minimum, identify the current answer for:

- project goal and north-star metrics
- architecture and planned module boundaries
- evaluation metrics and thresholds
- experiment design, hypotheses, and result interpretation
- ground-truth design and dataset strategy
- operating rules and documentation policy
- proxy prototype boundaries

If no clear source of truth exists, report that as a finding. Unclear authority is itself a consistency problem.

### 4. Run cross-document consistency checks

Compare documents in groups, not one file at a time. Check these axes in order:

1. Project goals and document direction
   - Verify that plans, experiments, handoffs, status reports, and operating guidance still aim at the same current project goal.
2. Architecture versus implementation, plan, and experiment direction
   - Verify that architecture docs, code-structure docs, plans, rules, and current repo state do not describe incompatible systems.
3. Experiment coherence
   - Verify that hypotheses, metrics, thresholds, condition labels, ground-truth assumptions, and result interpretation are mutually consistent.
4. Terminology consistency
   - Verify that component names, tool or server identifiers, strategy names, layer names, dataset labels, and responsibility boundaries are stable across docs.
5. Temporal consistency
   - Verify that recent ADRs, handoffs, and design pivots displaced older content everywhere they should have.
   - Flag unlabeled historical content that still reads like current guidance.
6. Deprecated or stale content
   - Flag documents or sections that are no longer valid, were superseded, or should be merged or deleted.
7. Memory versus docs
   - Verify that stored memory, rule files, agent guidance, and local workflow instructions do not contradict current design or decision docs.
8. Decision propagation
   - Verify that decisions made in one document are reflected in the downstream documents that depend on them.

When a doc references code paths, commands, or existing behavior, spot-check the current repo state instead of trusting the prose.

### 5. Trace recent changes and propagation gaps

1. Start from the newest accepted ADRs, newest design docs, newest handoff docs, and the most recently changed items from the inventory script.
2. For each recent change, list which documents should reflect that change.
3. Mark each downstream document as:
   - reflected
   - partially reflected
   - stale
4. Separate truly current documents from pre-change documents that were kept for history.
5. If an older document is intentionally historical, require that it be clearly labeled as such. If it is not labeled, treat it as an ambiguity risk.

Use `git log`, `git diff`, and `rg` on decision names, ADR numbers, experiment IDs, metric names, and component names to trace propagation.

### 6. Prioritize only substantive problems

Use these levels exactly:

- `P0`: A consistency problem that can directly cause wrong implementation, wrong experiment execution, or wrong interpretation of results.
- `P1`: A mismatch that can cause major collaboration confusion, wrong handoff assumptions, or persistent misunderstanding of current state.
- `P2`: A minor terminology, phrasing, structure, or duplication issue that does not materially change direction.

Do not inflate stylistic issues into `P0` or `P1`.

### 7. Include an actionable fix for every finding

For each finding, always state:

- which documents or memory surfaces are involved
- what exactly conflicts or diverges
- what should be treated as the current source of truth
- how the affected documents should change
- whether the fix is a simple edit, a merge, a split, a deprecation label, or a deletion

## Output Format

Return the audit in Korean unless the user asked otherwise. Use this exact structure:

```markdown
# Cross-Document Consistency Audit — YYYY-MM-DD

## 전체 정합성 상태 요약
{프로젝트 전체 관점의 요약 1-3문장}

## 주요 충돌/불일치 목록
### P0
| # | 관련 문서/메모리 | 문제 | 현재 정답(SOT) | 수정 방안 |
|---|------------------|------|----------------|-----------|

### P1
| # | 관련 문서/메모리 | 문제 | 현재 정답(SOT) | 수정 방안 |
|---|------------------|------|----------------|-----------|

### P2
| # | 관련 문서/메모리 | 문제 | 현재 정답(SOT) | 수정 방안 |
|---|------------------|------|----------------|-----------|

## deprecated 또는 삭제 후보 문서/내용
- {파일 또는 섹션}: {이유}

## source of truth 재정의가 필요한 영역
- {주제}: {왜 SOT가 불분명한지}

## 즉시 수정이 필요한 항목
1. {P0 또는 즉시 정리해야 하는 P1}

## 추후 정리해도 되는 항목
1. {P2 또는 비긴급 정리 과제}
```

## Guardrails

- Do not review documents independently and then stack summaries. Always compare relationships.
- Do not report mere existence or absence unless that absence creates a real cross-document contradiction.
- Do not restate whole documents. Cite the conflicting sections, concepts, or claims.
- Do not trust timestamps alone. Use authority, explicit update markers, and git history together.
- Do not treat historical working notes as errors by default. Flag them only when they are unlabeled, still look current, or override newer sources in practice.
- Do not silently ignore missing memory access. State whether external memory resources were available.
