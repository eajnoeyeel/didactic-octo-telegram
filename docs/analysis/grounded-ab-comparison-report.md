# Grounded vs Ungrounded A/B 비교 보고서 + 연구 방향

> **Date:** 2026-03-29 (fluency 기반 재실행)
> **Branch:** `feat/description-optimizer`
> **데이터:** `data/verification/grounded_optimization_results.jsonl`, `data/verification/optimization_results.jsonl`
> **스크립트:** `scripts/run_grounded_ab_comparison.py`
> **차원:** clarity, disambiguation, parameter_coverage, **fluency** (boundary 제거), stats, precision

---

## 1. 실험 설계

### 대상
- 동일한 30개 tool 샘플 (`data/verification/sample_tools.json`)
- 원본 데이터: `data/raw/servers.jsonl` (861 tools, Smithery 크롤링)

### 조건
| 조건 | 설명 |
|------|------|
| **Ungrounded** (baseline) | `pipeline.run()` — 원본 description만으로 LLM 최적화. context 미제공. |
| **Grounded** (new) | `pipeline.run_with_tool()` — input_schema + sibling tools + anti-hallucination 규칙 적용 |

### Phase 2 변경사항 (이전 실행 대비)
1. **boundary 차원 완전 제거 → fluency 차원으로 교체** (GEO 연구 미지지, 95% 환각 원인)
2. RAGAS faithfulness 게이트 추가 (주장별 이진 검증)
3. doc2query 쿼리 인식 최적화 프롬프트 추가
4. 양쪽 모두 동일 파이프라인에서 fresh re-run (기존 캐시 결과 사용 안 함)

### Grounded 최적화에 추가된 것
1. `OptimizationContext` — `input_schema`, `sibling_tools` 포함
2. `build_grounded_prompt()` — schema 기반 프롬프트 구성
3. Anti-hallucination SYSTEM_PROMPT — "AUGMENT, NEVER invent" 규칙
4. Hallucination Detection Gate — backtick 파라미터 vs schema 교차 검증
5. Information Preservation Gate — 숫자/통계 + 기술 용어 보존 검증

---

## 2. 결과 요약 (fluency 기반, 2026-03-29)

### 2.1 전체 지표

| 지표 | Ungrounded | Grounded | 차이 | 비고 |
|------|-----------|----------|------|------|
| 성공률 | 17/30 (57%) | **21/30 (70%)** | +13%p | Grounded가 더 많은 tool 최적화 |
| 평균 GEO 향상 | +0.1603 | **+0.1861** | **+0.0258** | **Grounded가 이제 수치에서도 승리** |
| Gate 거부 | **13건** | 9건 | -31% | Grounded가 더 적은 품질 위반 |
| Per-tool 승부 | 3승 | **11승** (1 tie) | — | Grounded 압도적 |

### 2.2 차원별 Delta (성공 건 기준)

| Dimension | Ungrounded Delta | Grounded Delta | 승자 |
|-----------|------:|------:|------|
| clarity | +0.1706 | **+0.2071** | **Grounded** |
| disambiguation | **+0.4059** | +0.3000 | Ungrounded |
| parameter_coverage | +0.1029 | **+0.2429** | **Grounded** |
| fluency | +0.2735 | **+0.2929** | **Grounded** |
| stats | +0.0000 | **+0.0238** | **Grounded** |
| precision | +0.0088 | **+0.0500** | **Grounded** |

**Grounded 5승, Ungrounded 1승.** Ungrounded는 disambiguation에서만 승리.

### 2.3 Per-Tool Head-to-Head (15개 공통 성공)

| 결과 | 건수 |
|------|------|
| Grounded 승 | **11** |
| Ungrounded 승 | 3 |
| Tie | 1 |

**Grounded가 per-tool에서 11:3으로 압도적 승리.** 이전 (boundary 포함 시) 8:12 역전에서 완전 뒤집힘.

---

## 3. 핵심 발견: boundary 제거로 GEO-level Goodhart 완화

### 3.1 이전 결과와 비교

| 지표 | 이전 (boundary 포함) | 현재 (fluency 기반) | 변화 |
|------|---------------------|--------------------| -----|
| GEO 향상 차이 | Ungrounded +0.0372 | **Grounded +0.0258** | **역전** |
| Per-tool 승부 | UG 12:8 GR | **GR 11:3 UG** | **역전** |
| 차원별 승부 | GR 4:2 UG | **GR 5:1 UG** | 개선 |

**boundary 차원 제거로 GEO-level Goodhart 문제가 완화됨.** 이전에 ungrounded가 이겼던 이유(boundary 환각 +0.3864)가 사라졌고, grounded의 GEO 우위가 드러남. 단, 후속 P@1 A/B에서 GEO 향상이 retrieval 성능 향상으로 이어지지 않음이 확인됨 (δP@1 = -0.069). Retrieval-level 해결에는 `search_description` 경로 연결과 disambiguation 재설계가 필요. 상세: `docs/analysis/description-optimizer-root-cause-analysis.md`

### 3.2 Grounded가 환각을 방지하는 메커니즘

1. **Anti-hallucination SYSTEM_PROMPT**: "NEVER invent parameters, limitations, or capabilities not in the provided schema"
2. **Hallucination Detection Gate**: optimized text에서 backtick 파라미터 추출 → input_schema의 properties와 교차 검증 → 불일치 시 reject
3. **Augmentation mode**: "keep original + add grounded info" — 전체 재작성 대신 보존+추가
4. **실제 gate 동작**: `FaresYoussef94/aws-knowledge-mcp::aws___search_doc`이 hallucination gate에 의해 거부됨 (날조된 파라미터 탐지)

---

## 4. Gate 거부 분석

### 4.1 Grounded 거부 (9건)
| Tool | 거부 사유 |
|------|----------|
| `math-mcp::max` | Similarity 0.744 < 0.75 |
| `GOOGLESUPER_EVENTS_INSTANCES` | Similarity 0.710 < 0.75 |
| `download_paper` | InfoPreservation (숫자 손실) |
| `github::create_or_update_file` | **Hallucination gate**: 날조된 파라미터 탐지 |
| `market_screen` | GEO 감소 + InfoPreservation |
| `brave_news_search` | GEO 감소 + InfoPreservation |
| `get_vulnerable_practice_labs` | GEO 감소 + InfoPreservation |
| `aws___search_doc` | **Hallucination gate**: 날조된 파라미터 탐지 |
| `indicators_run_custom` | GEO 감소 + InfoPreservation |

### 4.2 Ungrounded 거부 (13건)
Similarity(4), InfoPreservation(4), GEO 감소(3), 복합(2).
**Ungrounded가 4건 더 많이 거부됨** — context 없이 최적화하면 원본과의 의미 유사도 및 정보 보존이 더 어려움.

### 4.3 남은 구조적 문제

순환 검증 구조는 여전히 존재:
```
HeuristicAnalyzer → "이 차원이 약함" → LLM Optimizer → "패턴 문구 삽입" → HeuristicAnalyzer → "점수 올랐음!"
```

boundary 제거로 가장 큰 환각 원인은 해결했지만, disambiguation의 regex 패턴("unlike", "in contrast")도 여전히 게이밍 가능. 향후 임베딩 거리 기반 측정으로 전환 필요.

### 4.4 다음 단계

1. ~~**P@1 end-to-end 검증**~~ — 완료 (δP@1 = -0.069, 검색 성능 저하 확인)
2. **[최우선] Retrieval 경로 재정렬** — `search_description`을 임베딩/평가 경로에 연결, 3-way A/B 평가
3. **GEO를 diagnostic metric으로 전환** — hard gate에서 제외
4. **disambiguation 재설계** — sibling 이름 나열 → target-only qualifier 중심
5. **RAGAS faithfulness 파이프라인 통합**

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
| **A. Retrieval 경로 재정렬** | `search_description`을 임베딩/평가에 연결 — 가장 근본적 | 중 |
| **B. GEO diagnostic 전환** | hard gate 제거, 진단 보조로만 사용 | 하 |
| **C. disambiguation 재설계** | sibling 이름 나열 → target-only qualifier, 임베딩 거리 측정 | 상 |
| **D. 3-way A/B 평가** | original vs optimized vs search — search_description이 P@1 개선하는지 검증 | 중 |

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
| `src/description_optimizer/quality_gate.py` | 5-gate 시스템 (GEO 비회귀 + similarity + hallucination + info preservation + faithfulness) — GEO gate 제거 예정 |
| `src/analytics/geo_score.py` | GEO 점수 계산 (기하평균) |
| `docs/analysis/description-optimizer-root-cause-analysis.md` | **근본원인 분석 SOT** (2026-03-30) — GEO-P@1 불일치, 평가/검색 경로 불일치, disambiguation 오염 |

---

## 7. Phase 2 완료 현황 (2026-03-29)

### 완료 (이 세션)
1. **논문 리서치**: 4개 클러스터 종합 → `description_optimizer/docs/research-phase2-synthesis.md`
2. **Scorer 개선**: boundary 차원 제거, fluency 차원 추가 (GEO 연구 기반)
3. **RAGAS Faithfulness 게이트 추가**: 주장별 이진 검증
4. **doc2query 쿼리 인식 프롬프트**: `build_query_aware_prompt()`
5. **P@1 A/B 스크립트**: `scripts/run_retrieval_ab_eval.py`

### 다음 세션에서 할 일
1. ~~**A/B 비교 재실행**~~ — 완료 (grounded GEO 승리)
2. ~~**P@1 A/B 평가**~~ — 완료 (δP@1 = -0.069)
3. ~~**근본원인 분석**~~ — 완료 (2026-03-30)
4. **Retrieval 경로 재정렬** — `search_description` 연결
5. **3-way A/B 평가** — original vs optimized vs search
6. **GEO diagnostic 전환 + disambiguation 재설계**
