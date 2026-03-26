---
name: experiment-orchestration
description: Plan or run multi-step experiment workflows such as E0-E7, compare experiment outputs, or map experiment dependencies. Use only when the user asks for experiment execution or analysis. Do not use for normal unit tests or when the requested experiment harness does not exist in the repository.
---

# Experiment Orchestration

1. Verify the runnable surface first. In the current repo, `scripts/run_experiments.py` and `src/evaluation/` are not present, so many experiment requests are design/planning tasks rather than executable workflows.
2. If the harness is absent, do not fabricate commands or results. Reframe the task as design, gap analysis, or implementation planning.
3. If/when experiment code exists, keep dependency order explicit:
   - E0 -> E1 -> E2 -> E3
   - E4 / E5 / E6 can run in parallel only after the shared prerequisites exist
   - E7 depends on the relevant evaluation outputs
4. Compare like with like: same GT slice, same pool, same fixed variables, and explicit notes about missing or skipped conditions.
