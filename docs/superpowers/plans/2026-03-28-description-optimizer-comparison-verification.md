# Description Optimizer 비교 검증 (Comparison Verification) Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Description Optimizer가 실제로 MCP tool description을 개선하는지, 어떤 차원에서 얼마나 개선되는지를 정량적/정성적으로 면밀하게 검증하는 스크립트와 리포트를 생성한다.

**Architecture:** 3단계 검증 — (1) 자동화된 비교 스크립트가 representative sample에 대해 before/after GEO 점수를 측정하고 통계 리포트를 생성, (2) 사람이 리뷰할 수 있는 side-by-side 비교 리포트 생성, (3) Quality Gate 효과성과 Heuristic Analyzer 캘리브레이션을 실증적으로 검증.

**Tech Stack:** Python 3.12, pytest, pytest-asyncio, OpenAI API (GPT-4o-mini + text-embedding-3-small), HeuristicAnalyzer, tabulate

**Branch:** `feat/description-optimizer` (현재 브랜치에서 계속)

---

## 사전 지식 (Background)

### 현재 상태
- **소스 코드:** `src/description_optimizer/` — analyzer, optimizer, pipeline, quality_gate, models
- **기존 테스트:** 117개 PASS (unit 52 + verification 65), 99% coverage
- **실제 데이터:** `data/raw/servers.jsonl` — 50 servers, 861 tools
- **dry-run 결과:** 평균 GEO 0.102 (90%가 0.20 미만) — 이는 최적화 전 원본 상태

### 검증 목표
1. **실제 LLM 최적화 실행** → before/after GEO 점수 비교
2. **차원별 개선 분석** → 6개 GEO 차원 각각의 개선폭 측정
3. **Quality Gate 효과성** → 게이트가 나쁜 최적화를 실제로 걸러내는지
4. **의미 보존 검증** → 원본과 최적화본의 의미적 유사도 확인
5. **사람이 읽는 side-by-side 리포트** → 정성적 품질 확인

### 핵심 모듈 참조
| 모듈 | 파일 | 역할 |
|------|------|------|
| Models | `src/description_optimizer/models.py` | DimensionScore, AnalysisReport, OptimizedDescription, OptimizationStatus |
| HeuristicAnalyzer | `src/description_optimizer/analyzer/heuristic.py` | 6차원 regex 기반 GEO 점수 산출 |
| LLMDescriptionOptimizer | `src/description_optimizer/optimizer/llm_optimizer.py` | GPT-4o-mini 기반 description 최적화 |
| QualityGate | `src/description_optimizer/quality_gate.py` | GEO 비회귀 + 코사인 유사도 검증 |
| OptimizationPipeline | `src/description_optimizer/pipeline.py` | analyze → optimize → re-analyze → gate → result |
| CLI Script | `scripts/optimize_descriptions.py` | batch 실행 CLI |
| Embedder ABC | `src/embedding/base.py` | Embedder interface (embed_one, embed_batch) |
| OpenAIEmbedder | `src/embedding/openai_embedder.py` | text-embedding-3-small 구현 |

---

## File Structure

```
scripts/
├── optimize_descriptions.py        # (기존) 전체 batch CLI
└── run_comparison_verification.py   # (신규) 비교 검증 메인 스크립트

tests/verification/
├── conftest.py                     # (기존) HeuristicAnalyzer fixture
├── test_heuristic_edge_cases.py    # (기존) 19 edge case tests
├── test_quality_gate_edge_cases.py # (기존) 13 boundary tests
├── test_llm_optimizer_robustness.py # (기존) 11 robustness tests
├── test_pipeline_error_paths.py    # (기존) 11 error path tests
├── test_geo_calibration.py         # (기존) 11 calibration tests
└── test_comparison_verification.py  # (신규) 비교 검증 결과 assertion 테스트

data/
├── raw/servers.jsonl               # (기존) 원본 861 tools
└── verification/                   # (신규) 검증 결과 저장
    ├── sample_tools.json           # 검증 대상 30 tool 샘플
    ├── optimization_results.jsonl  # pipeline 실행 결과
    └── comparison_report.md        # side-by-side 비교 리포트
```

---

## Task 1: 대표 샘플 선정 스크립트

**목적:** 861개 tool 중 GEO 점수 분포를 대표하는 30개 tool을 자동 선정한다. 전체를 돌리면 비용이 크므로 stratified sampling으로 대표성 확보.

**Files:**
- Create: `scripts/run_comparison_verification.py`
- Create: `data/verification/` directory
- Read: `data/raw/servers.jsonl`

- [ ] **Step 1: 샘플 선정 함수 작성**

`scripts/run_comparison_verification.py` 파일을 생성하고, 데이터 로드 + stratified sampling 함수를 작성한다.

```python
"""Comparison verification script for Description Optimizer.

Runs the full optimization pipeline on a representative sample of MCP tools,
generates before/after GEO score comparisons, and produces a human-readable report.

Usage:
    # Phase 1: Sample selection + dry-run analysis only (no API key needed)
    PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase sample

    # Phase 2: Full optimization (requires OPENAI_API_KEY in .env)
    PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase optimize

    # Phase 3: Generate comparison report from saved results
    PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase report

    # All phases at once
    PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase all
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from loguru import logger

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import AnalysisReport

SAMPLE_SIZE = 30
VERIFICATION_DIR = Path("data/verification")
RAW_DATA = Path("data/raw/servers.jsonl")
SAMPLE_FILE = VERIFICATION_DIR / "sample_tools.json"


def load_all_tools() -> list[dict]:
    """Load all tools from servers.jsonl with server context."""
    tools = []
    with open(RAW_DATA) as f:
        for line in f:
            server = json.loads(line.strip())
            for tool in server.get("tools", []):
                tool_id = f"{server['server_id']}::{tool['tool_name']}"
                tools.append({
                    "tool_id": tool_id,
                    "server_id": server["server_id"],
                    "tool_name": tool["tool_name"],
                    "description": tool.get("description") or "",
                })
    return tools


async def select_representative_sample(tools: list[dict]) -> list[dict]:
    """Select SAMPLE_SIZE tools via stratified sampling by GEO score tier.

    Tiers:
        - low:    GEO < 0.10  (majority of tools — select 10)
        - medium: 0.10 <= GEO < 0.30  (select 10)
        - high:   GEO >= 0.30  (select 10, or fewer if not enough)
    """
    import random

    random.seed(42)  # Reproducible

    analyzer = HeuristicAnalyzer()
    scored: list[tuple[dict, float]] = []

    for tool in tools:
        report = await analyzer.analyze(tool["tool_id"], tool["description"])
        tool["geo_score_original"] = round(report.geo_score, 4)
        tool["dimension_scores_original"] = {
            s.dimension: round(s.score, 4) for s in report.dimension_scores
        }
        scored.append((tool, report.geo_score))

    # Stratify
    low = [t for t, g in scored if g < 0.10]
    medium = [t for t, g in scored if 0.10 <= g < 0.30]
    high = [t for t, g in scored if g >= 0.30]

    logger.info(f"Distribution: low={len(low)}, medium={len(medium)}, high={len(high)}")

    # Sample 10 from each tier (or all if fewer)
    sample = []
    sample.extend(random.sample(low, min(10, len(low))))
    sample.extend(random.sample(medium, min(10, len(medium))))
    sample.extend(random.sample(high, min(10, len(high))))

    logger.info(f"Selected {len(sample)} tools for verification")
    return sample


async def phase_sample():
    """Phase 1: Select sample and save to file."""
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    tools = load_all_tools()
    logger.info(f"Loaded {len(tools)} tools from {RAW_DATA}")

    sample = await select_representative_sample(tools)

    with open(SAMPLE_FILE, "w") as f:
        json.dump(sample, f, indent=2, ensure_ascii=False)

    logger.info(f"Sample saved to {SAMPLE_FILE}")

    # Print summary
    print("\n=== SAMPLE SELECTION SUMMARY ===")
    print(f"Total tools: {len(tools)}")
    print(f"Sample size: {len(sample)}")
    print(f"\nGEO Score Distribution in Sample:")
    for tool in sorted(sample, key=lambda t: t["geo_score_original"]):
        print(f"  {tool['geo_score_original']:.4f}  {tool['tool_id'][:60]}")
```

- [ ] **Step 2: 실행하여 샘플 선정 확인**

Run: `PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase sample`
Expected: `data/verification/sample_tools.json`에 30개 tool이 GEO 분포별로 선정됨

- [ ] **Step 3: 커밋**

```bash
git add scripts/run_comparison_verification.py data/verification/
git commit -m "feat(verification): add comparison verification script — Phase 1 sample selection"
```

---

## Task 2: 전체 파이프라인 실행 + 결과 저장

**목적:** 선정된 30개 tool에 대해 실제 LLM 최적화 파이프라인을 돌리고, before/after 결과를 JSONL로 저장한다.

**Files:**
- Modify: `scripts/run_comparison_verification.py`
- Read: `src/description_optimizer/pipeline.py`
- Read: `src/description_optimizer/optimizer/llm_optimizer.py`

**선행 조건:** `.env`에 `OPENAI_API_KEY` 설정 필요

- [ ] **Step 1: phase_optimize 함수 추가**

`scripts/run_comparison_verification.py`에 다음 함수를 추가한다:

```python
async def phase_optimize():
    """Phase 2: Run full optimization pipeline on sample tools."""
    from openai import AsyncOpenAI

    from config import Settings
    from description_optimizer.optimizer.llm_optimizer import LLMDescriptionOptimizer
    from description_optimizer.pipeline import OptimizationPipeline
    from description_optimizer.quality_gate import QualityGate
    from embedding.openai_embedder import OpenAIEmbedder

    if not SAMPLE_FILE.exists():
        logger.error(f"Sample file not found: {SAMPLE_FILE}. Run --phase sample first.")
        return

    with open(SAMPLE_FILE) as f:
        sample = json.load(f)

    settings = Settings()
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    analyzer = HeuristicAnalyzer()
    optimizer = LLMDescriptionOptimizer(client=openai_client)
    embedder = OpenAIEmbedder(client=openai_client)
    gate = QualityGate(min_similarity=0.85)
    pipeline = OptimizationPipeline(
        analyzer=analyzer,
        optimizer=optimizer,
        embedder=embedder,
        gate=gate,
        skip_threshold=0.75,
    )

    results_file = VERIFICATION_DIR / "optimization_results.jsonl"
    with open(results_file, "w") as f:
        for i, tool in enumerate(sample):
            logger.info(f"[{i + 1}/{len(sample)}] Optimizing {tool['tool_id']}")
            result = await pipeline.run(tool["tool_id"], tool["description"])
            # Enrich with original dimension scores
            record = json.loads(result.model_dump_json())
            record["dimension_scores_original"] = tool["dimension_scores_original"]
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()  # Write after each tool for crash safety

    logger.info(f"Results saved to {results_file}")

    # Quick summary
    results = []
    with open(results_file) as f:
        for line in f:
            results.append(json.loads(line.strip()))

    success = sum(1 for r in results if r["status"] == "success")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] == "failed")
    rejected = sum(1 for r in results if r["status"] == "gate_rejected")

    print(f"\n=== OPTIMIZATION SUMMARY ===")
    print(f"Success: {success}, Skipped: {skipped}, Failed: {failed}, Gate Rejected: {rejected}")

    if success > 0:
        improvements = [
            r["geo_score_after"] - r["geo_score_before"]
            for r in results
            if r["status"] == "success"
        ]
        avg = sum(improvements) / len(improvements)
        print(f"Average GEO improvement: +{avg:.4f}")
        print(f"Min improvement: +{min(improvements):.4f}")
        print(f"Max improvement: +{max(improvements):.4f}")
```

- [ ] **Step 2: main + argparse 연결**

```python
async def main(args: argparse.Namespace) -> None:
    if args.phase in ("sample", "all"):
        await phase_sample()
    if args.phase in ("optimize", "all"):
        await phase_optimize()
    if args.phase in ("report", "all"):
        await phase_report()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Description Optimizer Comparison Verification")
    parser.add_argument(
        "--phase",
        choices=["sample", "optimize", "report", "all"],
        default="all",
        help="Which phase to run",
    )
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
```

- [ ] **Step 3: 실행하여 최적화 결과 확인**

Run: `PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase optimize`
Expected: `data/verification/optimization_results.jsonl`에 30개 결과 저장, 콘솔에 요약 출력

- [ ] **Step 4: 커밋**

```bash
git add scripts/run_comparison_verification.py
git commit -m "feat(verification): add Phase 2 — full pipeline execution on sample"
```

---

## Task 3: 차원별 비교 분석 + Side-by-Side 리포트 생성

**목적:** optimization_results.jsonl을 읽어서 (1) 차원별 before/after 통계, (2) 각 tool의 side-by-side 텍스트 비교, (3) Quality Gate 결과 분석을 markdown 리포트로 생성한다.

**Files:**
- Modify: `scripts/run_comparison_verification.py`
- Create: `data/verification/comparison_report.md` (스크립트가 자동 생성)

- [ ] **Step 1: phase_report 함수 작성**

```python
async def phase_report():
    """Phase 3: Generate comparison report from optimization results."""
    results_file = VERIFICATION_DIR / "optimization_results.jsonl"
    if not results_file.exists():
        logger.error(f"Results file not found: {results_file}. Run --phase optimize first.")
        return

    results = []
    with open(results_file) as f:
        for line in f:
            results.append(json.loads(line.strip()))

    analyzer = HeuristicAnalyzer()

    # Re-analyze optimized descriptions to get per-dimension after scores
    for r in results:
        if r["status"] == "success":
            report_after = await analyzer.analyze(r["tool_id"], r["optimized_description"])
            r["dimension_scores_after"] = {
                s.dimension: round(s.score, 4) for s in report_after.dimension_scores
            }
        else:
            r["dimension_scores_after"] = r.get("dimension_scores_original", {})

    report_path = VERIFICATION_DIR / "comparison_report.md"
    with open(report_path, "w") as f:
        _write_report(f, results)

    logger.info(f"Report saved to {report_path}")
    print(f"\n=== Report generated: {report_path} ===")


def _write_report(f, results: list[dict]) -> None:
    """Write the full comparison report to a file handle."""
    dims = ["clarity", "disambiguation", "parameter_coverage", "boundary", "stats", "precision"]

    f.write("# Description Optimizer 비교 검증 리포트\n\n")
    f.write(f"> 생성 시각: 스크립트 실행 시점\n")
    f.write(f"> 샘플 크기: {len(results)} tools\n\n")

    # --- Section 1: Overall Summary ---
    f.write("## 1. 전체 요약\n\n")
    status_counts = {}
    for r in results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    f.write("| Status | Count |\n|--------|-------|\n")
    for status, count in sorted(status_counts.items()):
        f.write(f"| {status} | {count} |\n")

    success = [r for r in results if r["status"] == "success"]
    if success:
        improvements = [r["geo_score_after"] - r["geo_score_before"] for r in success]
        f.write(f"\n**성공 건수:** {len(success)}\n")
        f.write(f"**평균 GEO 개선:** +{sum(improvements) / len(improvements):.4f}\n")
        f.write(f"**최소 개선:** +{min(improvements):.4f}\n")
        f.write(f"**최대 개선:** +{max(improvements):.4f}\n\n")

    # --- Section 2: Dimension-Level Analysis ---
    f.write("## 2. 차원별 Before/After 분석\n\n")
    f.write("| Dimension | Avg Before | Avg After | Avg Δ | Improved% |\n")
    f.write("|-----------|-----------|----------|-------|----------|\n")

    for dim in dims:
        befores = []
        afters = []
        for r in success:
            b = r.get("dimension_scores_original", {}).get(dim, 0)
            a = r.get("dimension_scores_after", {}).get(dim, 0)
            befores.append(b)
            afters.append(a)

        if befores:
            avg_b = sum(befores) / len(befores)
            avg_a = sum(afters) / len(afters)
            delta = avg_a - avg_b
            improved_pct = sum(1 for b, a in zip(befores, afters) if a > b) / len(befores) * 100
            f.write(f"| {dim} | {avg_b:.4f} | {avg_a:.4f} | {delta:+.4f} | {improved_pct:.0f}% |\n")

    # --- Section 3: Per-Tool Side-by-Side ---
    f.write("\n## 3. Tool별 Side-by-Side 비교\n\n")

    for i, r in enumerate(results):
        f.write(f"### Tool {i + 1}: `{r['tool_id']}`\n\n")
        f.write(f"**Status:** {r['status']}\n")
        f.write(f"**GEO:** {r['geo_score_before']:.4f} → {r['geo_score_after']:.4f}")
        if r["status"] == "success":
            delta = r["geo_score_after"] - r["geo_score_before"]
            f.write(f" ({delta:+.4f})")
        f.write("\n\n")

        if r.get("skip_reason"):
            f.write(f"**Skip/Reject Reason:** {r['skip_reason']}\n\n")

        # Dimension comparison table
        f.write("| Dimension | Before | After | Δ |\n")
        f.write("|-----------|--------|-------|---|\n")
        for dim in dims:
            b = r.get("dimension_scores_original", {}).get(dim, 0)
            a = r.get("dimension_scores_after", {}).get(dim, 0)
            delta = a - b
            f.write(f"| {dim} | {b:.4f} | {a:.4f} | {delta:+.4f} |\n")

        f.write("\n**Original:**\n")
        f.write(f"```\n{r['original_description'][:500]}\n```\n\n")

        if r["status"] == "success":
            f.write("**Optimized:**\n")
            f.write(f"```\n{r['optimized_description'][:500]}\n```\n\n")
            f.write("**Search Description:**\n")
            f.write(f"```\n{r.get('search_description', 'N/A')[:300]}\n```\n\n")

        f.write("---\n\n")

    # --- Section 4: Quality Gate Analysis ---
    f.write("## 4. Quality Gate 분석\n\n")
    rejected = [r for r in results if r["status"] == "gate_rejected"]
    failed = [r for r in results if r["status"] == "failed"]

    f.write(f"- **Gate Rejected:** {len(rejected)} tools\n")
    f.write(f"- **Failed (optimizer error):** {len(failed)} tools\n\n")

    if rejected:
        f.write("### Rejection Details\n\n")
        for r in rejected:
            f.write(f"- `{r['tool_id']}`: {r.get('skip_reason', 'N/A')}\n")

    if failed:
        f.write("\n### Failure Details\n\n")
        for r in failed:
            f.write(f"- `{r['tool_id']}`: {r.get('skip_reason', 'N/A')}\n")

    # --- Section 5: Verdict ---
    f.write("\n## 5. 검증 결론\n\n")
    f.write("아래 체크리스트를 사람이 직접 확인:\n\n")
    f.write("- [ ] 성공한 최적화의 GEO 개선이 양수인가?\n")
    f.write("- [ ] 6개 차원 중 최소 4개가 개선되었는가?\n")
    f.write("- [ ] 최적화된 설명이 원본의 의미를 보존하는가? (Section 3 side-by-side 확인)\n")
    f.write("- [ ] 최적화된 설명에 환각(hallucination)이 없는가?\n")
    f.write("- [ ] Quality Gate가 나쁜 최적화를 적절히 걸러냈는가?\n")
    f.write("- [ ] search_description이 벡터 검색에 적합한 키워드를 포함하는가?\n")
    f.write("- [ ] 최적화된 설명의 길이가 적절한가? (50-200 words)\n")
```

- [ ] **Step 2: 실행하여 리포트 확인**

Run: `PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase report`
Expected: `data/verification/comparison_report.md`에 side-by-side 비교 리포트 생성

- [ ] **Step 3: 커밋**

```bash
git add scripts/run_comparison_verification.py
git commit -m "feat(verification): add Phase 3 — comparison report generator"
```

---

## Task 4: 비교 검증 결과에 대한 자동 Assertion 테스트

**목적:** 생성된 optimization_results.jsonl을 읽어서 자동으로 assertion 체크를 수행하는 pytest 테스트를 작성한다. 사람이 리포트를 보기 전에 기본적인 품질 기준을 자동 검증.

**Files:**
- Create: `tests/verification/test_comparison_verification.py`
- Read: `data/verification/optimization_results.jsonl` (Phase 2 실행 후 생성됨)

- [ ] **Step 1: 테스트 파일 작성**

```python
"""Automated assertions on comparison verification results.

These tests validate that the optimization pipeline produces measurable
improvements when run on real MCP tool descriptions.

Prerequisites:
    Run the comparison verification script first:
    PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase optimize
"""

import json
from pathlib import Path

import pytest

RESULTS_FILE = Path("data/verification/optimization_results.jsonl")

# Skip all tests if results file doesn't exist (Phase 2 not yet run)
pytestmark = pytest.mark.skipif(
    not RESULTS_FILE.exists(),
    reason="optimization_results.jsonl not found — run Phase 2 first",
)


def _load_results() -> list[dict]:
    results = []
    with open(RESULTS_FILE) as f:
        for line in f:
            results.append(json.loads(line.strip()))
    return results


class TestOverallQuality:
    """Validate overall optimization quality metrics."""

    def test_at_least_one_success(self) -> None:
        """Pipeline must successfully optimize at least 1 tool."""
        results = _load_results()
        success_count = sum(1 for r in results if r["status"] == "success")
        assert success_count > 0, "No successful optimizations"

    def test_success_rate_above_50_percent(self) -> None:
        """At least 50% of tools should be successfully optimized."""
        results = _load_results()
        success_count = sum(1 for r in results if r["status"] == "success")
        rate = success_count / len(results)
        assert rate >= 0.50, f"Success rate {rate:.0%} below 50%"

    def test_no_status_is_null(self) -> None:
        """Every result must have a valid status."""
        results = _load_results()
        for r in results:
            assert r["status"] in {"success", "skipped", "failed", "gate_rejected"}


class TestGEOImprovement:
    """Validate GEO score improvements on successful optimizations."""

    def test_average_geo_improvement_positive(self) -> None:
        """Average GEO improvement across successes must be > 0."""
        results = _load_results()
        success = [r for r in results if r["status"] == "success"]
        if not success:
            pytest.skip("No successful optimizations")
        avg_improvement = sum(
            r["geo_score_after"] - r["geo_score_before"] for r in success
        ) / len(success)
        assert avg_improvement > 0, f"Average improvement {avg_improvement:.4f} is not positive"

    def test_no_success_has_negative_improvement(self) -> None:
        """No successful optimization should have a negative GEO delta.

        Quality Gate should prevent this — if it passed, GEO must not decrease.
        """
        results = _load_results()
        for r in results:
            if r["status"] == "success":
                delta = r["geo_score_after"] - r["geo_score_before"]
                assert delta >= 0, (
                    f"{r['tool_id']}: GEO decreased {delta:+.4f} despite SUCCESS status"
                )

    def test_geo_scores_in_valid_range(self) -> None:
        """All GEO scores must be in [0.0, 1.0]."""
        results = _load_results()
        for r in results:
            assert 0.0 <= r["geo_score_before"] <= 1.0, (
                f"{r['tool_id']}: geo_score_before={r['geo_score_before']} out of range"
            )
            assert 0.0 <= r["geo_score_after"] <= 1.0, (
                f"{r['tool_id']}: geo_score_after={r['geo_score_after']} out of range"
            )


class TestDimensionImprovement:
    """Validate per-dimension improvements."""

    def test_at_least_3_dimensions_improve_on_average(self) -> None:
        """On average, at least 3 of 6 dimensions should improve."""
        results = _load_results()
        success = [r for r in results if r["status"] == "success"]
        if not success:
            pytest.skip("No successful optimizations")

        dims = ["clarity", "disambiguation", "parameter_coverage", "boundary", "stats", "precision"]
        dims_improved = 0
        for dim in dims:
            before_avg = sum(
                r.get("dimension_scores_original", {}).get(dim, 0) for r in success
            ) / len(success)
            after_avg = sum(
                r.get("dimension_scores_after", {}).get(dim, 0) for r in success
            ) / len(success)
            if after_avg > before_avg:
                dims_improved += 1

        assert dims_improved >= 3, (
            f"Only {dims_improved}/6 dimensions improved on average (need >= 3)"
        )


class TestSemanticPreservation:
    """Validate that optimized descriptions preserve original meaning."""

    def test_optimized_not_empty(self) -> None:
        """Successful optimizations must have non-empty optimized_description."""
        results = _load_results()
        for r in results:
            if r["status"] == "success":
                assert len(r["optimized_description"].strip()) > 0, (
                    f"{r['tool_id']}: empty optimized_description"
                )

    def test_search_description_not_empty(self) -> None:
        """Successful optimizations must have non-empty search_description."""
        results = _load_results()
        for r in results:
            if r["status"] == "success":
                assert len(r.get("search_description", "").strip()) > 0, (
                    f"{r['tool_id']}: empty search_description"
                )

    def test_optimized_length_reasonable(self) -> None:
        """Optimized descriptions should be 20-2000 characters."""
        results = _load_results()
        for r in results:
            if r["status"] == "success":
                length = len(r["optimized_description"])
                assert 20 <= length <= 2000, (
                    f"{r['tool_id']}: optimized length {length} outside [20, 2000]"
                )


class TestQualityGateEffectiveness:
    """Validate that gate rejections are legitimate."""

    def test_gate_rejected_preserves_original(self) -> None:
        """Gate-rejected results must have optimized == original."""
        results = _load_results()
        for r in results:
            if r["status"] == "gate_rejected":
                assert r["optimized_description"] == r["original_description"], (
                    f"{r['tool_id']}: gate_rejected but description changed"
                )

    def test_failed_has_skip_reason(self) -> None:
        """Failed and gate_rejected results must have a skip_reason."""
        results = _load_results()
        for r in results:
            if r["status"] in ("failed", "gate_rejected"):
                assert r.get("skip_reason"), (
                    f"{r['tool_id']}: status={r['status']} but no skip_reason"
                )
```

- [ ] **Step 2: 테스트가 skip 상태인지 확인 (Phase 2 미실행 시)**

Run: `uv run pytest tests/verification/test_comparison_verification.py -v`
Expected: 모든 테스트가 SKIPPED (results file이 아직 없으므로)

- [ ] **Step 3: 커밋**

```bash
git add tests/verification/test_comparison_verification.py
git commit -m "test(verification): add automated comparison verification assertions"
```

---

## Task 5: Heuristic Analyzer 캘리브레이션 심화 검증

**목적:** HeuristicAnalyzer가 "좋은 설명"과 "나쁜 설명"을 올바르게 구분하는지 더 세밀하게 검증한다. 특히 LLM이 최적화한 설명이 heuristic 점수에서도 실제로 높아지는지 확인.

**Files:**
- Create: `tests/verification/test_heuristic_sensitivity.py`
- Read: `src/description_optimizer/analyzer/heuristic.py`

- [ ] **Step 1: Sensitivity 테스트 작성**

```python
"""Heuristic Analyzer sensitivity tests — verify the analyzer rewards
known-good patterns and penalizes known-bad patterns consistently."""

from description_optimizer.analyzer.heuristic import HeuristicAnalyzer
from description_optimizer.models import AnalysisReport

import pytest


@pytest.fixture
def analyzer() -> HeuristicAnalyzer:
    return HeuristicAnalyzer()


def _dim(report: AnalysisReport, dimension: str) -> float:
    return next(s.score for s in report.dimension_scores if s.dimension == dimension)


class TestClarityDimension:
    """Verify clarity scoring responds to specific signal additions."""

    async def test_adding_action_verb_increases_clarity(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding an action verb to a vague description increases clarity."""
        vague = "A tool for files"
        with_verb = "Searches and retrieves files from the filesystem"
        r_vague = await analyzer.analyze("t::a", vague)
        r_verb = await analyzer.analyze("t::b", with_verb)
        assert _dim(r_verb, "clarity") > _dim(r_vague, "clarity")

    async def test_adding_when_to_use_increases_clarity(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding 'Use when...' phrase increases clarity."""
        base = "Searches files in a directory"
        with_when = "Searches files in a directory. Use when you need to find specific files by pattern."
        r_base = await analyzer.analyze("t::a", base)
        r_when = await analyzer.analyze("t::b", with_when)
        assert _dim(r_when, "clarity") > _dim(r_base, "clarity")

    async def test_adding_scope_increases_clarity(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding scope markers ('from the', 'in the') increases clarity."""
        base = "Searches files"
        with_scope = "Searches files from the local filesystem via the OS API"
        r_base = await analyzer.analyze("t::a", base)
        r_scope = await analyzer.analyze("t::b", with_scope)
        assert _dim(r_scope, "clarity") > _dim(r_base, "clarity")


class TestDisambiguationDimension:
    """Verify disambiguation scoring responds to contrast language."""

    async def test_adding_contrast_increases_disambiguation(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding 'unlike X' phrase increases disambiguation."""
        base = "Searches files"
        with_contrast = "Searches files. Unlike grep, this tool only searches filenames, not content."
        r_base = await analyzer.analyze("t::a", base)
        r_contrast = await analyzer.analyze("t::b", with_contrast)
        assert _dim(r_contrast, "disambiguation") > _dim(r_base, "disambiguation")

    async def test_adding_only_for_increases_disambiguation(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding 'only for' qualifier increases disambiguation."""
        base = "Manages database connections"
        with_qual = "Manages database connections. Only for PostgreSQL databases, not MySQL or SQLite."
        r_base = await analyzer.analyze("t::a", base)
        r_qual = await analyzer.analyze("t::b", with_qual)
        assert _dim(r_qual, "disambiguation") > _dim(r_base, "disambiguation")


class TestBoundaryDimension:
    """Verify boundary scoring responds to limitation language."""

    async def test_adding_cannot_increases_boundary(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding 'Cannot X' limitation increases boundary score."""
        base = "Reads files from disk"
        with_boundary = "Reads files from disk. Cannot read binary files. Does not support URLs."
        r_base = await analyzer.analyze("t::a", base)
        r_boundary = await analyzer.analyze("t::b", with_boundary)
        assert _dim(r_boundary, "boundary") > _dim(r_base, "boundary")

    async def test_adding_limitation_keyword_increases_boundary(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding 'limitation' keyword increases boundary score."""
        base = "Sends email messages"
        with_lim = "Sends email messages. Limitation: maximum 10 recipients per message."
        r_base = await analyzer.analyze("t::a", base)
        r_lim = await analyzer.analyze("t::b", with_lim)
        assert _dim(r_lim, "boundary") > _dim(r_base, "boundary")


class TestStatsDimension:
    """Verify stats scoring responds to quantitative information."""

    async def test_adding_numbers_with_units_increases_stats(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding '100 results per query' increases stats score."""
        base = "Returns search results"
        with_stats = "Returns up to 100 results per query in under 200ms"
        r_base = await analyzer.analyze("t::a", base)
        r_stats = await analyzer.analyze("t::b", with_stats)
        assert _dim(r_stats, "stats") > _dim(r_base, "stats")


class TestPrecisionDimension:
    """Verify precision scoring responds to technical terminology."""

    async def test_adding_tech_terms_increases_precision(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding technical terms (SQL, REST, JSON) increases precision."""
        base = "Queries the database"
        with_tech = "Queries the PostgreSQL database via REST API, returning JSON responses"
        r_base = await analyzer.analyze("t::a", base)
        r_tech = await analyzer.analyze("t::b", with_tech)
        assert _dim(r_tech, "precision") > _dim(r_base, "precision")


class TestParameterCoverageDimension:
    """Verify parameter_coverage responds to parameter documentation."""

    async def test_adding_param_refs_increases_coverage(
        self, analyzer: HeuristicAnalyzer
    ) -> None:
        """Adding parameter references increases parameter_coverage."""
        base = "Searches for items"
        with_params = "Searches for items. Accepts a required `query` string parameter and an optional `limit` integer."
        r_base = await analyzer.analyze("t::a", base)
        r_params = await analyzer.analyze("t::b", with_params)
        assert _dim(r_params, "parameter_coverage") > _dim(r_base, "parameter_coverage")


class TestOverallOrdering:
    """Verify that progressively richer descriptions get progressively higher GEO scores."""

    async def test_progressive_improvement(self, analyzer: HeuristicAnalyzer) -> None:
        """tier1 < tier2 < tier3 in GEO score."""
        tier1 = "Search"
        tier2 = "Searches files in a directory. Returns matching paths."
        tier3 = (
            "Searches files in the local filesystem via glob patterns. "
            "Use when you need to find files by name or extension. "
            "Accepts a required `pattern` string and optional `recursive` bool. "
            "Returns up to 1000 results. Cannot search file contents. "
            "Unlike grep, this only matches filenames. "
            "Supports POSIX glob syntax."
        )
        r1 = await analyzer.analyze("t::a", tier1)
        r2 = await analyzer.analyze("t::b", tier2)
        r3 = await analyzer.analyze("t::c", tier3)
        assert r1.geo_score < r2.geo_score < r3.geo_score
```

- [ ] **Step 2: 테스트 실행**

Run: `uv run pytest tests/verification/test_heuristic_sensitivity.py -v`
Expected: 모든 테스트 PASS

- [ ] **Step 3: 커밋**

```bash
git add tests/verification/test_heuristic_sensitivity.py
git commit -m "test(verification): add heuristic analyzer sensitivity tests (12 tests)"
```

---

## Task 6: 전체 실행 + 검증 리포트 생성

**목적:** Task 1-5의 모든 코드를 통합 실행하여 최종 검증 리포트를 생성하고, 테스트 결과를 확인한다.

**Files:**
- Run: `scripts/run_comparison_verification.py`
- Run: `tests/verification/test_comparison_verification.py`
- Read: `data/verification/comparison_report.md`

**선행 조건:** `.env`에 `OPENAI_API_KEY` 설정 필요

- [ ] **Step 1: Phase 1 + 2 실행 (샘플 선정 + 최적화)**

Run: `PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase sample`
Run: `PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase optimize`

Expected:
- `data/verification/sample_tools.json` — 30개 tool 샘플
- `data/verification/optimization_results.jsonl` — 30개 결과

- [ ] **Step 2: Phase 3 실행 (리포트 생성)**

Run: `PYTHONPATH=src uv run python scripts/run_comparison_verification.py --phase report`
Expected: `data/verification/comparison_report.md` 생성

- [ ] **Step 3: 자동 Assertion 테스트 실행**

Run: `uv run pytest tests/verification/test_comparison_verification.py -v`
Expected: results 파일이 존재하므로 skip이 아닌 실제 테스트 실행, 모두 PASS

- [ ] **Step 4: 전체 테스트 스위트 실행**

Run: `uv run pytest tests/verification/ -v`
Expected: 기존 65 + sensitivity 12 + comparison ~12 = ~89 테스트 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add data/verification/
git commit -m "feat(verification): add comparison verification results and report"
```

---

## Task 7: 사람이 리뷰할 체크리스트 작성

**목적:** `data/verification/comparison_report.md`를 보면서 사람이 확인해야 할 항목을 정리한다. 이 태스크는 코드가 아니라 문서 작업.

**Files:**
- Modify: `data/verification/comparison_report.md` (Section 5에 이미 기본 체크리스트 포함)

이 태스크는 Phase 3 리포트가 생성된 후 자동으로 포함됨. 별도 작업 불필요.

사람이 확인할 핵심 항목:

1. **Section 3 (Side-by-Side 비교)를 읽으며:**
   - 원본 의미가 보존되었는가?
   - 환각(hallucination)이 없는가? (원본에 없는 기능을 추가하지 않았는가?)
   - 최적화된 설명이 자연스럽고 읽기 쉬운가?
   - search_description이 벡터 검색에 유용한 키워드를 담고 있는가?

2. **Section 2 (차원별 분석)를 보며:**
   - 6개 차원 중 최소 4개가 평균적으로 개선되었는가?
   - 특정 차원이 오히려 악화되지 않았는가?
   - 개선폭이 의미 있는 수준인가? (최소 +0.05 이상)

3. **Section 4 (Quality Gate 분석)를 보며:**
   - Gate Rejected 건이 있다면, 거부 사유가 합리적인가?
   - Failed 건의 원인이 무엇인가?

---

## Self-Review Checklist

- [x] Spec coverage: 6개 검증 영역 (GEO 개선, 차원별 분석, Quality Gate, 의미 보존, Heuristic 감도, side-by-side) 모두 태스크에 반영
- [x] Placeholder scan: 모든 코드 블록에 실제 코드 포함, "TBD" 없음
- [x] Type consistency: `AnalysisReport`, `OptimizedDescription`, `HeuristicAnalyzer` 등 실제 코드의 타입과 일치
- [x] 파일 경로: 모든 경로가 실제 프로젝트 구조와 일치
- [x] 실행 커맨드: PYTHONPATH=src prefix 포함, uv run 사용
