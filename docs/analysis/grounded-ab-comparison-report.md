# Grounded vs Ungrounded A/B 비교 보고서 + 연구 방향

> **Date:** 2026-03-29
> **Branch:** `feat/description-optimizer`
> **데이터:** `data/verification/grounded_optimization_results.jsonl`, `data/verification/optimization_results.jsonl`
> **스크립트:** `scripts/run_grounded_ab_comparison.py`

---

## 1. 실험 설계

### 대상
- 동일한 30개 tool 샘플 (`data/verification/sample_tools.json`)
- 원본 데이터: `data/raw/servers.jsonl` (861 tools, Smithery 크롤링)

### 조건
| 조건 | 설명 |
|------|------|
| **Ungrounded** (기존) | 원본 description만으로 LLM 최적화. input_schema 미제공. |
| **Grounded** (신규) | input_schema + sibling tools + anti-hallucination 규칙 적용 |

### Grounded 최적화에 추가된 것
1. `OptimizationContext` — `input_schema`, `sibling_tools` 포함
2. `build_grounded_prompt()` — schema 기반 프롬프트 구성
3. Anti-hallucination SYSTEM_PROMPT — "AUGMENT, NEVER invent" 규칙
4. Hallucination Detection Gate — backtick 파라미터 vs schema 교차 검증
5. Information Preservation Gate — 숫자/통계 + 기술 용어 보존 검증

---

## 2. 결과 요약

### 2.1 전체 지표

| 지표 | Ungrounded | Grounded | 차이 | 비고 |
|------|-----------|----------|------|------|
| 성공률 | 22/30 (73%) | **26/30 (87%)** | +14%p | Grounded가 더 많은 tool 최적화 |
| 평균 GEO 향상 | **+0.1792** | +0.1420 | -0.0372 | Ungrounded가 수치상 높음 |
| Gate 거부 | 8건 | **4건** | -50% | Grounded가 더 적은 품질 위반 |
| Stats 퇴보 건수 | 3건 | **0건** | -100% | Grounded가 기존 정보 완전 보존 |
| Boundary 환각 의심 | **21/22 (95%)** | 2/26 (8%) | -87%p | 핵심 차이 |

### 2.2 차원별 Delta (성공 건 기준)

| Dimension | Ungrounded Before→After (Delta) | Grounded Before→After (Delta) | 승자 |
|-----------|------|------|------|
| clarity | 0.5159→0.5773 (+0.0614) | 0.5308→0.7442 (**+0.2135**) | **Grounded** |
| disambiguation | 0.0545→0.4727 (**+0.4182**) | 0.0462→0.3462 (+0.3000) | Ungrounded |
| parameter_coverage | 0.1614→0.4000 (+0.2386) | 0.1538→0.4077 (**+0.2538**) | **Grounded** |
| boundary | 0.0273→0.4136 (**+0.3864**) | 0.0231→0.0462 (+0.0231) | Ungrounded |
| stats | 0.0795→0.0273 (-0.0523) | 0.1019→0.1288 (**+0.0269**) | **Grounded** |
| precision | 0.1932→0.2159 (+0.0227) | 0.1808→0.2154 (**+0.0346**) | **Grounded** |

**Grounded 4승, Ungrounded 2승.** 단, Ungrounded의 2승(boundary, disambiguation)은 환각에 의한 것.

### 2.3 Per-Tool Head-to-Head (21개 공통 성공)

| 결과 | 건수 |
|------|------|
| Grounded 승 | 8 |
| Ungrounded 승 | 12 |
| Tie | 1 |

**Ungrounded가 per-tool에서도 12:8로 이김.** 그러나 이 차이의 대부분이 boundary 환각에서 비롯됨.

---

## 3. 핵심 발견: Goodhart's Law 확인

### 3.1 Boundary 차원이 GEO 차이의 원인

GEO 차이 -0.0372 중 boundary 차원 기여도:
- Ungrounded boundary delta: +0.3864
- Grounded boundary delta: +0.0231
- **차이: 0.3633** (GEO는 6차원 기하평균이므로 이 한 차원이 전체에 큰 영향)

**21/22 (95%)의 ungrounded 성공 건에서 boundary가 0.2 이상 급등** — 거의 전부 환각.

### 3.2 환각 사례 (Ungrounded)

```
# EthanHenrickson/math-mcp::arccos
"does not handle complex numbers or inputs outside the range of -1 to 1"
→ arccos의 수학적 정의역을 추측으로 서술. input_schema에는 이 정보 없음.

# Sallvainian/ngss-mcp::search_standards
"does not handle non-NGSS content"
→ 실제 API 동작 모른 채 제한사항 날조.

# aryankeluskar/polymarket-mcp::get_trades
"does not handle trades from other markets or platforms"
→ 근거 없는 제한사항 추가.

# slack::SLACK_LEAVE_A_CONVERSATION
boundary: 0.00 → 0.70 (+0.70)
→ 가장 극단적인 환각 케이스. 0점에서 0.7점으로.

# slack::SLACK_DELETE_A_COMMENT_ON_A_FILE
"It does not handle comments on channels or direct messages."
→ 원본에 없는 제한사항. 사실 여부 불명.
```

### 3.3 Grounded가 환각을 방지하는 메커니즘

1. **Anti-hallucination SYSTEM_PROMPT**: "NEVER invent parameters, limitations, or capabilities not in the provided schema"
2. **Hallucination Detection Gate**: optimized text에서 backtick 파라미터 추출 → input_schema의 properties와 교차 검증 → 불일치 시 reject
3. **Augmentation mode**: "keep original + add grounded info" — 전체 재작성 대신 보존+추가
4. **실제 gate 동작**: `FaresYoussef94/aws-knowledge-mcp::aws___search_doc`이 hallucination gate에 의해 거부됨 (날조된 파라미터 탐지)

---

## 4. 미해결 문제: GEO Scorer의 구조적 한계

### 4.1 문제 정의

현재 GEO scorer(HeuristicAnalyzer)는 **regex 기반 패턴 매칭**으로 각 차원을 측정합니다:

```
boundary: "does not", "cannot", "limit", "only" 등의 패턴 → 점수 부여
disambiguation: "unlike", "in contrast", "as opposed to" 패턴 → 점수 부여
```

이로 인해:
- 날조된 제한사항도 boundary 점수를 받음 (사실 여부 미검증)
- 의미 없는 "Unlike other tools..." 문구도 disambiguation 점수를 받음
- **GEO 점수가 실제 설명 품질의 신뢰할 수 있는 지표가 아님**

### 4.2 순환 검증 구조 (변하지 않은 문제)

```
HeuristicAnalyzer → "이 차원이 약함" → LLM Optimizer → "패턴 문구 삽입" → HeuristicAnalyzer → "점수 올랐음!"
```

Grounded 최적화로 **환각은 제거**했지만, **평가 체계 자체의 순환 검증 구조**는 여전히 존재합니다.

### 4.3 앞으로 풀어야 할 질문들

1. **Heuristic scoring을 어떻게 개선할 것인가?**
   - boundary/disambiguation에 사실 검증(factual grounding) 로직 추가?
   - LLM-as-Judge 방식으로 전환?
   - Heuristic + LLM 하이브리드?

2. **Description quality → Tool selection accuracy 인과 관계 검증은 어떻게?**
   - 현재 GEO는 프록시 메트릭. North Star는 Precision@1.
   - 최적화된 설명으로 실제 Qdrant 인덱스를 구축하고 검색 정확도를 비교해야 함.
   - `scripts/run_selection_eval.py`가 scaffold만 존재.

3. **어떤 차원이 실제로 tool selection에 기여하는가?**
   - clarity가 높으면 embedding similarity가 올라가는가?
   - parameter_coverage가 tool 구분에 도움이 되는가?
   - 이 인과관계를 실험적으로 밝혀야 함.

---

## 5. 연구 방향 제안

### 5.1 Description Quality Evaluation (GEO scorer 개선)

**현재 문제:** Regex 패턴 매칭은 사실 여부를 검증하지 못함.

**연구 키워드:**
- Factual grounding in text evaluation
- LLM-as-Judge for text quality (G-Eval, FActScore)
- Hallucination detection metrics (SelfCheckGPT, FaithfulnessScore)
- Rubric-based LLM evaluation

**기대 결과:** 환각에 취약하지 않은 새로운 description quality 평가 방법

### 5.2 Description Optimization → Retrieval Performance 연결

**현재 문제:** GEO 점수 향상 ≠ 검색 성능 향상이 검증되지 않음.

**연구 키워드:**
- Query-document relevance optimization
- Document expansion for dense retrieval (doc2query, ANCE)
- Tool retrieval / API retrieval papers
- Description augmentation for semantic search

**기대 결과:** 어떤 설명 특성이 실제 검색 정확도에 기여하는지 이해

### 5.3 Tool Description Optimization 직접 관련 연구

**연구 키워드:**
- ToolBench, ToolLLM, Gorilla — LLM tool selection
- API-Bank — API retrieval and selection
- ToolkenGPT, AnyTool — tool description representation
- ReAct, Toolformer — tool use in LLM agents

**기대 결과:** 선행 연구에서 tool description quality가 selection에 미치는 영향에 대한 인사이트

### 5.4 Scorer 개선 구체 방향

| 방향 | 설명 | 난이도 |
|------|------|--------|
| **A. Heuristic 보강** | boundary/disambiguation에 schema 기반 검증 추가 | 중 |
| **B. LLM-as-Judge 추가** | 별도 LLM이 description quality 판정 (G-Eval 방식) | 상 |
| **C. Retrieval-based 평가** | description으로 실제 검색해서 Precision@1 직접 측정 | 상 |
| **D. 가중치 재조정** | boundary 가중치 축소, clarity 가중치 증가 | 하 |

---

## 6. 현재 코드베이스 상태

### 브랜치: `feat/description-optimizer`

**구현 완료 (10 tasks):**
- `src/description_optimizer/models.py` — `OptimizationContext` 모델
- `src/description_optimizer/optimizer/prompts.py` — `build_grounded_prompt()`, anti-hallucination SYSTEM_PROMPT
- `src/description_optimizer/optimizer/base.py` — `optimize(report, context=None)` ABC
- `src/description_optimizer/optimizer/llm_optimizer.py` — context 분기 (grounded/ungrounded)
- `src/description_optimizer/pipeline.py` — `run_with_tool()`, `run_batch_with_tools()`
- `src/description_optimizer/quality_gate.py` — hallucination gate, info preservation gate
- `scripts/optimize_descriptions.py` — MCPTool 기반으로 업데이트
- `scripts/run_comparison_verification.py` — input_schema 포함 로딩
- `scripts/run_selection_eval.py` — Precision@1 A/B scaffold

**테스트:** 389 tests pass, 92% coverage, lint clean

**미커밋 파일:**
- `data/verification/` — sample_tools.json, optimization_results.jsonl, grounded_optimization_results.jsonl
- `scripts/run_comparison_verification.py`
- `scripts/run_grounded_ab_comparison.py` (A/B 비교 스크립트)
- `tests/verification/` — 검증 테스트들

### 핵심 파일 경로

| 파일 | 용도 |
|------|------|
| `src/description_optimizer/analyzer/heuristic.py` | GEO scorer (regex 패턴 매칭) — **개선 대상** |
| `src/description_optimizer/analyzer/dimensions.py` | 6개 차원 정의 |
| `src/description_optimizer/optimizer/prompts.py` | LLM 프롬프트 — grounded/ungrounded 분기 |
| `src/description_optimizer/quality_gate.py` | 4-gate 시스템 (GEO, similarity, hallucination, info preservation) |
| `src/analytics/geo_score.py` | GEO 점수 계산 (기하평균) |
| `docs/analysis/description-optimizer-root-cause-analysis.md` | 기존 근본원인 분석 (grounded 이전) |

---

## 7. Phase 2 완료 현황 (2026-03-29)

### 완료 (이 세션)
1. **논문 리서치**: 4개 클러스터 종합 → `description_optimizer/docs/research-phase2-synthesis.md`
2. **Scorer 개선**: boundary 차원 제거, fluency 차원 추가 (GEO 연구 기반)
3. **RAGAS Faithfulness 게이트 추가**: 주장별 이진 검증
4. **doc2query 쿼리 인식 프롬프트**: `build_query_aware_prompt()`
5. **P@1 A/B 스크립트**: `scripts/run_retrieval_ab_eval.py`

### 다음 세션에서 할 일
1. **새 fluency 차원으로 grounded A/B 비교 재실행**: `scripts/run_grounded_ab_comparison.py`
2. **P@1 A/B 평가 실행**: `PYTHONPATH=src uv run python scripts/run_retrieval_ab_eval.py`
3. **결과 분석 후 통합**: check_faithfulness를 pipeline에 통합, build_query_aware_prompt를 optimizer에서 사용
4. **P@1 delta >= +5pp 확인** (성공 기준)

**핵심 질문 (해결 방향 수립 완료):** RAGAS faithfulness로 환각 검증 + P@1로 end-to-end 검증. 프록시 메트릭(GEO) 최적화 대신 실제 목표(도구 선택 정확도) 직접 측정.
