---
name: experiment-orchestration
description: Plan or run multi-step experiment workflows such as E0-E7, compare experiment outputs, or map experiment dependencies. Use only when the user asks for experiment execution or analysis. Do not use for normal unit tests or when the requested experiment harness does not exist in the repository.
---

# Experiment Orchestration

1. Verify the runnable surface first. Currently available: `scripts/run_e0.py` (Flat + Sequential), `src/evaluation/` (harness + metrics). `scripts/run_experiments.py` (full E0-E7 CLI)는 아직 미구현.
2. E0 이외의 실험 요청은 design/planning task로 취급. 존재하지 않는 command/결과를 만들지 말 것.
3. If/when experiment code exists, keep dependency order explicit:
   - E0 -> E1 -> E2 -> E3
   - E4 / E5 / E6 can run in parallel only after the shared prerequisites exist
   - E7 depends on the relevant evaluation outputs
4. Compare like with like: same GT slice, same pool, same fixed variables, and explicit notes about missing or skipped conditions.
