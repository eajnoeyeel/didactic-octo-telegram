# Description Optimizer — GEO-P@1 근본원인 분석 기반 문서 정비 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GEO-P@1 불일치 근본원인 분석 결과를 반영하여, 현재 브랜치에서 수정된 10개 문서를 일관된 원칙으로 직접 수정한다.

**Architecture:** 분석 결론(root-cause-analysis)을 SOT로 고정한 뒤, 나머지 문서가 그 결론을 참조하도록 top-down 순서로 수정한다. 기존 내용 유지보다 문제를 바로 잡는 것을 우선한다.

**Tech Stack:** Markdown 문서 수정 (코드 변경 없음)

---

## Context

Description Optimizer에서 GEO Score와 P@1의 불일치가 확인되었다:
- GEO +0.19 향상 → P@1 -0.069 하락
- 근본원인: (1) 평가/검색 경로 불일치 — `search_description`이 생성되지만 실제 retrieval에 사용되지 않음, (2) GEO 휴리스틱이 retrieval에 불리한 패턴(길이 팽창, sibling 오염)을 보상, (3) disambiguation이 분리가 아닌 오염으로 작동, (4) gate가 safety용이지 retrieval regression용이 아님
- 상세: `docs/analysis/description-optimizer-root-cause-analysis.md`

**공통 변경 원칙 (모든 문서에 적용):**
1. `search_description`은 retrieval 전용 텍스트다
2. `optimized_description`은 사람용 설명이다
3. GEO는 hard gate가 아니라 diagnostic metric이다
4. P@1이 최종 판단 기준이다
5. sibling 이름 나열과 contrast phrasing은 retrieval 오염 가능성으로 취급한다
6. "boundary 제거만으로 Goodhart 해결" 같은 결론은 직접 수정한다

**범위 규칙:** `git diff --name-only $(git merge-base HEAD main)..HEAD` 결과에 포함되는 문서만 수정한다.

**수정 방침:** 기존 내용을 유지할 필요 없음. 문제점을 바로 잡을 수 있게 직접 수정한다.

---

## File Structure

모든 파일은 기존 파일 수정 (Create 없음):

| 파일 | 변경 유형 |
|------|-----------|
| `docs/analysis/description-optimizer-root-cause-analysis.md` | 확인 — 이미 최신 SOT |
| `description_optimizer/CLAUDE.md` | rewrite — 프로젝트 요약, gate, next steps 전면 수정 |
| `description_optimizer/docs/evaluation-design.md` | rewrite — 3-way A/B, search_description primary |
| `description_optimizer/docs/progress.md` | rewrite — 현재 상태 전면 반영 |
| `description_optimizer/docs/research-analysis.md` | 수정 — GEO 서술을 진단 보조로 조정 |
| `description_optimizer/docs/research-phase2-synthesis.md` | 수정 — 결론부 + 결정사항 직접 수정 |
| `description_optimizer/docs/verification-report.md` | rewrite — 최신 기준으로 수정 |
| `docs/analysis/grounded-ab-comparison-report.md` | 수정 — "Goodhart 해결" 결론 직접 수정 |
| `docs/progress/grounded-optimization-handoff.md` | 수정 — 결론 + 다음 단계 직접 수정 |
| `docs/progress/status-report.md` | 수정 — 현재 상태, 다음 단계 반영 |

---

### Task 1: Root Cause Analysis 확인

**Files:**
- Review: `docs/analysis/description-optimizer-root-cause-analysis.md`

- [ ] **Step 1: SOT 확인**

이 문서는 2026-03-30 작성으로 이미 최신. Section 8 "대응 방향"이 공통 변경 원칙과 일치하는지 확인 후 변경 없이 다음으로 이동.

---

### Task 2: description_optimizer/CLAUDE.md Rewrite

**Files:**
- Modify: `description_optimizer/CLAUDE.md`

핵심 수정: GEO 중심 서술 제거, Quality Gate에서 GEO 비회귀 제외, search_description retrieval 경로 명시, next steps 업데이트.

- [ ] **Step 1: 프로젝트 한줄 요약 수정 (line 19)**

```markdown
# AS-IS:
Description Optimizer — Provider가 MCP 서버/도구를 등록할 때 description을 GEO Score 기반으로 진단하고, LLM으로 자동 최적화하여 검색 선택률을 높이는 기능.

# TO-BE:
Description Optimizer — Provider가 MCP 서버/도구를 등록할 때 description을 진단하고, LLM으로 자동 최적화하여 retrieval 정확도(P@1)를 높이는 기능. GEO Score는 진단 보조 지표로 사용.
```

- [ ] **Step 2: 현재 상태 섹션 전체 교체 (lines 27-38)**

```markdown
## 현재 상태 (2026-03-30)

**Branch:** `feat/description-optimizer` — Phase 2 구현 완료, GEO-P@1 불일치 근본원인 분석 완료

**핵심 발견 (2026-03-30):**
- P@1 A/B 결과: Original 0.5417 → Optimized 0.4722 (δP@1 = -0.069)
- 근본원인: (1) 평가/검색 경로가 `search_description`이 아닌 `optimized_description`을 사용, (2) GEO 휴리스틱이 retrieval에 불리한 패턴 보상, (3) disambiguation이 sibling 오염으로 작동
- 상세: `docs/analysis/description-optimizer-root-cause-analysis.md`

**다음 단계:** retrieval 경로를 `search_description` 기준으로 재정렬 → 3-way A/B 평가 (original vs optimized vs search) → GEO를 diagnostic metric으로 격하
```

- [ ] **Step 3: 상세 컨텍스트 참조에서 root-cause-analysis 설명 업데이트 (line 48)**

```markdown
# AS-IS:
| `docs/analysis/description-optimizer-root-cause-analysis.md` | 근본원인 분석 (Goodhart's Law, 환각 사례) |

# TO-BE:
| `docs/analysis/description-optimizer-root-cause-analysis.md` | **근본원인 분석 SOT** (2026-03-30) — 평가/검색 경로 불일치, GEO 보상 왜곡, disambiguation 오염 |
```

- [ ] **Step 4: Architecture에서 Quality Gate 수정 (line 71)**

```markdown
# AS-IS:
    Quality Gate (5-gate: GEO + Similarity + Hallucination + Info Preservation + Faithfulness)

# TO-BE:
    Quality Gate (4-gate: Similarity + Hallucination + Info Preservation + Faithfulness)
    GEO Score → diagnostic metric only (gate에서 제외)
```

- [ ] **Step 5: ABC Pattern에서 QualityGate 설명 수정 (line 80)**

```markdown
# AS-IS:
- `QualityGate` — 5-gate 시스템 (GEO 비회귀, 의미 유사도, 환각 탐지, 정보 보존, RAGAS faithfulness)

# TO-BE:
- `QualityGate` — 4-gate 시스템 (의미 유사도, 환각 탐지, 정보 보존, RAGAS faithfulness). GEO Score는 diagnostic metric으로만 사용.
```

- [ ] **Step 6: P@1 A/B 평가 결과 섹션 결론 수정 (line 105)**

```markdown
# AS-IS:
- **결론**: GEO 점수 개선이 실제 검색 성능과 불일치 — GEO 프록시 메트릭 신뢰도 재검토 필요

# TO-BE:
- **근본원인**: (1) 평가가 search_description이 아닌 optimized_description을 임베딩, (2) GEO 휴리스틱이 길이 팽창/sibling 오염을 보상, (3) disambiguation이 분리가 아닌 오염으로 작동. 상세: `docs/analysis/description-optimizer-root-cause-analysis.md`
```

- [ ] **Step 7: 미해결 과제 전면 교체 (lines 108-125)**

```markdown
## 미해결 과제 (우선순위순)

1. ~~**P@1 end-to-end 검증**~~ — 완료. δP@1 = -0.069
2. ~~**GEO-P@1 불일치 근본원인 분석**~~ — 완료 (2026-03-30). `docs/analysis/description-optimizer-root-cause-analysis.md`
3. **[최우선] Retrieval 경로 재정렬** — `search_description`을 실제 임베딩/평가 경로에 연결
   - 평가: original vs optimized_description vs search_description 3-way A/B
   - retrieval 전용 텍스트(`search_description`)가 실제 P@1을 개선하는지 검증
4. **GEO를 diagnostic metric으로 전환** — hard gate에서 제외, 진단 보조로만 사용
5. **disambiguation 재설계** — sibling 이름 나열 → target-only qualifier 중심
6. **RAGAS faithfulness 파이프라인 통합**: 현재 gate만 구현됨, 최적화 루프에 통합 필요
```

- [ ] **Step 8: Key Constraints에서 Quality Gate 수정 (line 134)**

```markdown
# AS-IS:
- **Quality Gate**: 5-gate (GEO 비회귀 + 의미 유사도 + 환각 탐지 + 정보 보존 + RAGAS faithfulness)

# TO-BE:
- **Quality Gate**: 4-gate (의미 유사도 + 환각 탐지 + 정보 보존 + RAGAS faithfulness). GEO는 diagnostic metric (gate 아님).
```

- [ ] **Step 9: Commit**

```bash
git add description_optimizer/CLAUDE.md
git commit -m "docs(desc-optimizer): align CLAUDE.md with root cause analysis — GEO diagnostic only, search_description retrieval path"
```

---

### Task 3: evaluation-design.md Rewrite

**Files:**
- Modify: `description_optimizer/docs/evaluation-design.md`

전면 재작성. 핵심: 3-way A/B, search_description primary, GEO diagnostic only.

- [ ] **Step 1: 전체 문서 교체**

```markdown
# Description Optimizer — Evaluation Design

> 최종 업데이트: 2026-03-30
> 근본원인 분석 반영: `docs/analysis/description-optimizer-root-cause-analysis.md`

---

## 평가 목표

Description Optimizer가 실제로 검색 선택률(Precision@1)을 향상시키는지 검증.

**핵심 원칙:**
- P@1이 최종 판단 기준이다
- `search_description`이 retrieval 전용 텍스트이며, 평가의 primary treatment이다
- GEO Score는 진단 보조 지표이며, 성공 기준에 포함하지 않는다

## 평가 5단계

### Stage 1: Unit-level Quality
- 모든 컴포넌트 단위 테스트 통과
- Quality Gate 작동 검증 (4-gate: Similarity + Hallucination + Info Preservation + Faithfulness)

### Stage 2: Description Quality Diagnosis (diagnostic only)
- 최적화 전후 GEO Score 비교 — **진단 목적으로만 기록**
- GEO Score 변화는 hard gate가 아님 (GEO 하락이 반드시 나쁜 것은 아님)
- 참고: GEO +0.19 향상이 P@1 -0.069 하락과 동시에 발생한 사례 확인됨

### Stage 3: Semantic Preservation
- Cosine similarity(original, optimized) >= 0.85
- Cosine similarity(original, search) >= 0.75

### Stage 4: Offline A/B Test (Primary) — 3-way 비교

| 조건 | 설명 | 인덱싱 텍스트 |
|------|------|--------------|
| Control | 원본 description | `tool.description` |
| Treatment A | search description | `search_description` |
| Treatment B | optimized description | `optimized_description` |

- 동일 Ground Truth 사용
- **Primary: Control vs Treatment A** (search_description)의 P@1 delta
- Secondary: Control vs Treatment B (optimized_description의 retrieval 영향 확인)
- Per-query breakdown: degraded cases 집중 분석

### Stage 5: Statistical Significance
- McNemar's test (paired, binary outcome)
- 유의수준: p < 0.05
- 최소 효과 크기: +5%p Precision@1

## 성공 기준

| 지표 | 목표 | 방법 |
|------|------|------|
| P@1 delta (search_desc) | +5%p 이상 | 3-way A/B: Control vs Treatment A |
| Semantic preservation | >= 0.85 cosine (optimized), >= 0.75 (search) | Embedding similarity |
| No new degradation | 기존 degraded 3건 개선 또는 유지 | Per-query breakdown |
| GEO Score delta | 기록만 (gate 아님) | Before/after comparison |

## 이전 평가 결과 참조

`optimized_description` 기반 2-way A/B (2026-03-29):
- Original P@1: 0.5417, Optimized P@1: 0.4722 (δP@1 = -0.069)
- 이 결과가 evaluation design 재설계의 동기
- 상세: `data/verification/retrieval_ab_report.json`
```

- [ ] **Step 2: Commit**

```bash
git add description_optimizer/docs/evaluation-design.md
git commit -m "docs(desc-optimizer): rewrite evaluation design — 3-way A/B, search_description primary, GEO diagnostic only"
```

---

### Task 4: progress.md Rewrite

**Files:**
- Modify: `description_optimizer/docs/progress.md`

전면 재작성. Phase 1 + Phase 2 + 근본원인 분석 결과를 모두 반영.

- [ ] **Step 1: 상단 현재 상태 전면 교체**

```markdown
# Description Optimizer — 진행 현황

> 최종 업데이트: 2026-03-30
> 브랜치: `feat/description-optimizer`

---

## 현재 상태

| 항목 | 상태 |
|------|------|
| 브랜치 | `feat/description-optimizer` (main에서 분기) |
| 테스트 | **396 passed** (description optimizer + verification + evaluation) |
| Lint | PASS |
| Phase 1 (Core) | Task 1-10 완료 ✅ |
| Phase 2 (Grounded) | boundary→fluency, RAGAS, doc2query, P@1 A/B 완료 ✅ |
| P@1 A/B 평가 | **δP@1 = -0.069 (검색 성능 저하 확인)** |
| 근본원인 분석 | **완료** (2026-03-30) |
| **현재 단계** | **문서 정비 → retrieval 경로 재정렬 → 3-way A/B** |

### 핵심 발견

Grounded optimization은 환각 제거에 성공했으나, retrieval alignment 미해결:
- GEO +0.19 향상이 P@1 -0.069 하락으로 이어짐
- 근본원인: `search_description`이 retrieval 경로에 연결되지 않음 + GEO 보상 왜곡
- 상세: `docs/analysis/description-optimizer-root-cause-analysis.md`
```

- [ ] **Step 2: Phase 1 완료 작업 섹션 제목을 "Phase 1 완료 작업"으로 변경**

기존 "## 완료된 작업" → "## Phase 1 완료 작업 (2026-03-28)" 으로 제목만 수정. Task 1-10 내용은 유지.

- [ ] **Step 3: 핵심 문서 참조 테이블에 root-cause-analysis 추가**

```markdown
| `docs/analysis/description-optimizer-root-cause-analysis.md` | **근본원인 분석 SOT** (2026-03-30) |
```

- [ ] **Step 4: Commit**

```bash
git add description_optimizer/docs/progress.md
git commit -m "docs(desc-optimizer): rewrite progress with P@1 results and root cause analysis"
```

---

### Task 5: research-analysis.md 수정

**Files:**
- Modify: `description_optimizer/docs/research-analysis.md`

GEO를 "최적화 기법의 아이디어 원천"으로 위치 조정. selection metric과 동치인 것처럼 읽히는 표현 수정.

- [ ] **Step 1: Evidence 3 GEO 적용 설명 수정 (line 57-58)**

```markdown
# AS-IS:
- **프로젝트 적용**: description을 GEO 기법으로 최적화하면 임베딩 검색 + LLM reranking 모두에서 이점

# TO-BE:
- **프로젝트 적용**: GEO 기법은 description 최적화의 아이디어 원천. 단, GEO Score 향상이 retrieval 성능(P@1) 향상과 직접 동치는 아님 — P@1 A/B에서 GEO↑ + P@1↓ 확인됨. GEO는 진단 보조 지표로 사용.
```

- [ ] **Step 2: 결론 4번 항목 수정 (line 174)**

```markdown
# AS-IS:
4. GEO 기법 → AI 검색 최적화의 구체적 방법론 존재

# TO-BE:
4. GEO 기법 → description 최적화의 아이디어 원천 (단, GEO Score는 P@1과 직접 상관 없음 — 진단 보조 지표)
```

- [ ] **Step 3: 리스크에 GEO-P@1 불일치 추가 (line 180 뒤)**

```markdown
- **GEO-P@1 불일치**: GEO Score 향상이 검색 성능 향상을 보장하지 않음 — 길이 팽창과 sibling 오염이 dense retrieval에 노이즈로 작용. GEO는 최적화 방향의 아이디어 원천이지 selection metric이 아님. (2026-03-30 근본원인 분석에서 확인)
```

- [ ] **Step 4: Commit**

```bash
git add description_optimizer/docs/research-analysis.md
git commit -m "docs(desc-optimizer): clarify GEO as idea source, not selection metric"
```

---

### Task 6: research-phase2-synthesis.md 수정

**Files:**
- Modify: `description_optimizer/docs/research-phase2-synthesis.md`

P@1 결과를 반영하여 결론부 직접 수정. "RAGAS가 Goodhart를 직접 해결"을 정정.

- [ ] **Step 1: 전체 종합 상단에 P@1 결과 반영 (line 204 아래)**

```markdown
> **2026-03-30 업데이트:** 아래 추천안으로 구현된 grounded optimization의 P@1 A/B 결과, δP@1 = -0.069 (검색 성능 저하). 근본원인: retrieval 경로 불일치 + GEO 보상 왜곡. 추가 필요 조치: (1) `search_description`을 retrieval 전용 경로에 연결, (2) GEO를 diagnostic metric으로 격하, (3) disambiguation 재설계. 상세: `docs/analysis/description-optimizer-root-cause-analysis.md`
```

- [ ] **Step 2: "왜 이 접근법인가" #1 수정 (line 241)**

```markdown
# AS-IS:
1. **RAGAS Faithfulness가 Goodhart 문제를 직접 해결** — regex 대신 주장별 이진 검증으로 환각을 탐지

# TO-BE:
1. **RAGAS Faithfulness가 환각 문제를 직접 해결** — regex 대신 주장별 이진 검증. 단, Goodhart 문제의 완전 해결에는 retrieval 경로 정렬(`search_description` 사용)이 추가로 필요.
```

- [ ] **Step 3: 결정 사항에 2026-03-30 항목 추가 (line 271 아래)**

```markdown
### 추가 결정 사항 (2026-03-30, 근본원인 분석 이후)

6. **`search_description`이 retrieval 전용 텍스트** — 평가와 실서비스 모두에서 임베딩 대상은 `search_description`
7. **GEO는 diagnostic metric으로만 사용** — hard gate에서 제외
8. **3-way A/B 평가 전환** — original vs optimized_description vs search_description 비교
9. **disambiguation 재설계** — sibling 이름 나열(contrast phrasing) → target-only qualifier 중심
```

- [ ] **Step 4: Commit**

```bash
git add description_optimizer/docs/research-phase2-synthesis.md
git commit -m "docs(desc-optimizer): update phase2 synthesis with P@1 results — retrieval alignment needed"
```

---

### Task 7: verification-report.md 수정

**Files:**
- Modify: `description_optimizer/docs/verification-report.md`

Phase 1 시점의 검증 결과를 최신 기준으로 수정. boundary 관련 확인 포인트 수정, GEO calibration 해석 수정.

- [ ] **Step 1: 날짜 업데이트 및 상단에 최신 컨텍스트 추가 (line 2 아래)**

```markdown
> **최신 업데이트 (2026-03-30):** Phase 2 이후 boundary→fluency 교체, GEO가 diagnostic metric으로 전환, Quality Gate가 4-gate(GEO 비회귀 제외)로 변경됨. 이 문서의 검증 결과는 Phase 1 기준이며, 아래 내용은 해당 시점에서 유효합니다.
```

- [ ] **Step 2: GEO 캘리브레이션 결과 해석 수정 (line 87)**

```markdown
# AS-IS:
**관찰**: poor < medium < good 순서 정확히 유지. medium tier의 GEO가 예상보다 낮음 (0.1 수준) — heuristic이 disambiguation, boundary, stats 없는 설명에 엄격함.

# TO-BE:
**관찰**: poor < medium < good 순서 유지. medium tier의 GEO가 예상보다 낮음 (0.1 수준). **주의:** GEO Score는 retrieval 성능(P@1)과 직접 상관하지 않으므로, 이 캘리브레이션은 description 품질 진단 참고용이지 검색 성능 예측 지표가 아님.
```

- [ ] **Step 3: 리뷰 1에서 boundary 확인 포인트 수정 (line 128)**

```markdown
# AS-IS:
- [ ] boundary 차원에서 "Cannot", "Does not" 등이 있는 설명이 높은 점수를 받는가?

# TO-BE:
- [x] ~~boundary 차원~~ — 제거됨 (2026-03-29). fluency 차원으로 교체.
```

- [ ] **Step 4: 리뷰 3에서 Quality Gate 설명 수정 (line 153)**

```markdown
# AS-IS:
- [ ] `allow_geo_decrease=False` — 어떤 상황에서도 GEO 하락을 허용하지 않는 것이 합리적인가?
  - 고려: 의미 보존을 위해 약간의 GEO 하락이 나을 수 있음

# TO-BE:
- [x] `allow_geo_decrease` — GEO는 diagnostic metric으로 전환됨. GEO 비회귀 gate는 제거 대상.
```

- [ ] **Step 5: Commit**

```bash
git add description_optimizer/docs/verification-report.md
git commit -m "docs(desc-optimizer): update verification report — GEO diagnostic, boundary removed"
```

---

### Task 8: grounded-ab-comparison-report.md 수정

**Files:**
- Modify: `docs/analysis/grounded-ab-comparison-report.md`

"Goodhart 해결" 결론을 직접 수정. Section 3 제목과 본문을 P@1 결과 반영.

- [ ] **Step 1: Section 3 제목 수정 (line 74)**

```markdown
# AS-IS:
## 3. 핵심 발견: boundary 제거로 Goodhart's Law 해결

# TO-BE:
## 3. 핵심 발견: boundary 제거로 GEO-level Goodhart 완화
```

- [ ] **Step 2: Section 3.1 결론 수정 (line 84)**

```markdown
# AS-IS:
**boundary 차원 제거만으로 Goodhart 문제가 해결됨.** 이전에 ungrounded가 이겼던 이유(boundary 환각 +0.3864)가 사라졌고, grounded의 실질적 품질 우위가 드러남.

# TO-BE:
**boundary 차원 제거로 GEO-level Goodhart 문제가 완화됨.** 이전에 ungrounded가 이겼던 이유(boundary 환각 +0.3864)가 사라졌고, grounded의 GEO 우위가 드러남. 단, 후속 P@1 A/B에서 GEO 향상이 retrieval 성능 향상으로 이어지지 않음이 확인됨 (δP@1 = -0.069). Retrieval-level 해결에는 `search_description` 경로 연결과 disambiguation 재설계가 필요. 상세: `docs/analysis/description-optimizer-root-cause-analysis.md`
```

- [ ] **Step 3: Section 4.4 다음 단계 수정 (lines 124-127)**

```markdown
# AS-IS:
1. **P@1 end-to-end 검증**: `scripts/run_retrieval_ab_eval.py` 실행 — GEO 프록시가 아닌 실제 검색 성능 측정
2. **disambiguation 개선**: regex 대조 문구 → sibling tools 간 임베딩 거리로 측정
3. **RAGAS faithfulness 파이프라인 통합**: 현재 gate만 구현됨, 최적화 루프에 통합 필요

# TO-BE:
1. ~~**P@1 end-to-end 검증**~~ — 완료 (δP@1 = -0.069, 검색 성능 저하 확인)
2. **[최우선] Retrieval 경로 재정렬** — `search_description`을 임베딩/평가 경로에 연결, 3-way A/B 평가
3. **GEO를 diagnostic metric으로 전환** — hard gate에서 제외
4. **disambiguation 재설계** — sibling 이름 나열 → target-only qualifier 중심
5. **RAGAS faithfulness 파이프라인 통합**
```

- [ ] **Step 4: Section 5 연구 방향의 5.4 Scorer 개선 방향 수정 (lines 170-175)**

```markdown
# AS-IS:
| **D. 가중치 재조정** | boundary 가중치 축소, clarity 가중치 증가 | 하 |

# TO-BE (전체 테이블 교체):
| 방향 | 설명 | 난이도 |
|------|------|--------|
| **A. Retrieval 경로 재정렬** | `search_description`을 임베딩/평가에 연결 — 가장 근본적 | 중 |
| **B. GEO diagnostic 전환** | hard gate 제거, 진단 보조로만 사용 | 하 |
| **C. disambiguation 재설계** | sibling 이름 나열 → target-only qualifier, 임베딩 거리 측정 | 상 |
| **D. 3-way A/B 평가** | original vs optimized vs search — search_description이 P@1 개선하는지 검증 | 중 |
```

- [ ] **Step 5: Phase 2 완료 현황의 "다음 세션에서 할 일" 수정 (lines 224-228)**

```markdown
# AS-IS:
### 다음 세션에서 할 일
1. **새 fluency 차원으로 grounded A/B 비교 재실행**: ...
2. **P@1 A/B 평가 실행**: ...
3. **결과 분석 후 통합**: ...
4. **P@1 delta >= +5pp 확인** (성공 기준)

# TO-BE:
### 다음 세션에서 할 일
1. ~~**A/B 비교 재실행**~~ — 완료 (grounded GEO 승리)
2. ~~**P@1 A/B 평가**~~ — 완료 (δP@1 = -0.069)
3. ~~**근본원인 분석**~~ — 완료 (2026-03-30)
4. **Retrieval 경로 재정렬** — `search_description` 연결
5. **3-way A/B 평가** — original vs optimized vs search
6. **GEO diagnostic 전환 + disambiguation 재설계**
```

- [ ] **Step 6: Commit**

```bash
git add docs/analysis/grounded-ab-comparison-report.md
git commit -m "docs: fix grounded A/B report — Goodhart GEO-level only, retrieval-level unresolved"
```

---

### Task 9: grounded-optimization-handoff.md 수정

**Files:**
- Modify: `docs/progress/grounded-optimization-handoff.md`

결론과 다음 단계를 P@1 결과 반영하여 직접 수정.

- [ ] **Step 1: A/B 비교 결과 결론 수정 (line 116)**

```markdown
# AS-IS:
**결론:** boundary 차원 제거만으로 Goodhart 문제 해결. 이전 ungrounded의 GEO 우위(+0.0372)가 역전되어 grounded가 +0.0258로 승리. Per-tool도 8:12→11:3으로 완전 역전.

# TO-BE:
**결론:** boundary 차원 제거로 GEO-level Goodhart 완화. 이전 ungrounded의 GEO 우위(+0.0372)가 역전되어 grounded가 +0.0258로 승리. Per-tool도 8:12→11:3으로 완전 역전. 후속 P@1 A/B에서 GEO 향상이 retrieval 향상으로 이어지지 않음 확인 (δP@1 = -0.069). 근본원인: `docs/analysis/description-optimizer-root-cause-analysis.md`
```

- [ ] **Step 2: 다음 단계 수정 (lines 118-122)**

```markdown
# AS-IS:
### 다음 단계
1. **P@1 end-to-end 검증**: ...
2. **RAGAS faithfulness 파이프라인 통합**: ...
3. **disambiguation 개선**: ...

# TO-BE:
### 다음 단계
1. ~~**P@1 end-to-end 검증**~~ — 완료 (δP@1 = -0.069)
2. ~~**근본원인 분석**~~ — 완료 (2026-03-30)
3. **Retrieval 경로 재정렬** — `search_description`을 실제 임베딩/평가 경로에 연결
4. **3-way A/B 평가** — original vs optimized vs search
5. **GEO diagnostic 전환 + disambiguation 재설계**
6. **RAGAS faithfulness 파이프라인 통합**
```

- [ ] **Step 3: Commit**

```bash
git add docs/progress/grounded-optimization-handoff.md
git commit -m "docs: update grounded optimization handoff — P@1 result, next steps revised"
```

---

### Task 10: status-report.md 수정

**Files:**
- Modify: `docs/progress/status-report.md`

현재 상태, 다음 단계, 백로그를 근본원인 분석 완료 기준으로 업데이트.

- [ ] **Step 1: 날짜 업데이트 (line 2)**

`최종 업데이트: 2026-03-29` → `최종 업데이트: 2026-03-30`

- [ ] **Step 2: 요약 테이블 수정 (line 13)**

```markdown
# AS-IS:
| 진행중 | **GEO-P@1 불일치 근본원인 분석** (P@1 평가 완료, δP@1=-0.069) |

# TO-BE:
| 진행중 | **문서 정비 + Retrieval 경로 재정렬** (근본원인 분석 완료) |
```

- [ ] **Step 3: Description Optimizer 현황 테이블 수정 (lines 27-30)**

```markdown
# AS-IS:
| **핵심 발견** | GEO↑ but P@1↓: 프록시 메트릭이 실제 검색 성능과 불일치 |
| **다음 단계** | GEO-P@1 불일치 근본원인 분석 → 최적화 전략 재설계 (새 세션) |

# TO-BE:
| **핵심 발견** | 근본원인 확인: retrieval 경로 불일치 + GEO 보상 왜곡 (분석 완료 2026-03-30) |
| 근본원인 분석 | **완료** — `docs/analysis/description-optimizer-root-cause-analysis.md` |
| **다음 단계** | retrieval 경로 재정렬 (`search_description` 연결) → 3-way A/B → GEO diagnostic 전환 |
```

- [ ] **Step 4: P@1 A/B 상세의 결론 수정 (line 36)**

```markdown
# AS-IS:
- **결론**: GEO 프록시 메트릭이 검색 성능과 반대 방향 — 근본원인 분석 필요

# TO-BE:
- **근본원인**: (1) search_description 미사용 (2) GEO 보상 왜곡 (3) disambiguation 오염 — 분석 완료, `docs/analysis/description-optimizer-root-cause-analysis.md`
```

- [ ] **Step 5: 다음 단계 섹션 수정 (lines 300-304)**

```markdown
# AS-IS:
### 우선순위 1: Description Optimizer GEO Scorer 개선
1. **논문 리서치** — G-Eval, FActScore, SelfCheckGPT, doc2query, ToolBench, Gorilla 등
2. **Scorer 개선 방향 결정** — LLM-as-Judge / Retrieval-based eval / Heuristic 보강 중 선택
3. **구현 및 A/B 재검증** — 개선된 scorer로 grounded A/B 비교 재실행
4. **상세:** `docs/analysis/grounded-ab-comparison-report.md` Section 5 참조

# TO-BE:
### 우선순위 1: Description Optimizer Retrieval 경로 재정렬
1. ~~**논문 리서치**~~ — 완료 (`description_optimizer/docs/research-phase2-synthesis.md`)
2. ~~**GEO-P@1 근본원인 분석**~~ — 완료 (`docs/analysis/description-optimizer-root-cause-analysis.md`)
3. **Retrieval 경로 재정렬** — `search_description`을 실제 임베딩/평가 경로에 연결
4. **3-way A/B 평가** — original vs optimized_description vs search_description
5. **GEO diagnostic 전환** — hard gate에서 제외
6. **disambiguation 재설계** — sibling 이름 나열 → target-only qualifier 중심
```

- [ ] **Step 6: 백로그 테이블 수정 (lines 310-321)**

```markdown
# AS-IS:
| **높음** | GEO Scorer 개선 리서치 (Goodhart's Law 해결) | **진행중** |
| 높음 | 임베딩 인덱스 빌드 | 대기 |
| 중간 | E0 실험 | Phase 5 완료 후 |
| 중간 | Precision@1 end-to-end 평가 | Scorer 개선 후 |

# TO-BE:
| ~~높음~~ | ~~GEO Scorer 개선 리서치~~ | **완료** (근본원인 분석으로 대체) |
| **높음** | Retrieval 경로 재정렬 (search_description 연결) | **대기** |
| **높음** | 3-way A/B 평가 (original vs optimized vs search) | 경로 재정렬 후 |
| **높음** | GEO diagnostic 전환 + disambiguation 재설계 | 대기 |
| 높음 | 임베딩 인덱스 빌드 (`scripts/build_index.py`) | 대기 |
| 중간 | E0 실험: 1-Layer vs 2-Layer 검증 | Phase 5 완료 후 |
| ~~중간~~ | ~~Precision@1 end-to-end 평가~~ | **완료** (δP@1=-0.069) |
```

- [ ] **Step 7: Commit**

```bash
git add docs/progress/status-report.md
git commit -m "docs: update status report — root cause complete, next: retrieval path realignment"
```

---

## Verification

모든 Task 완료 후:

1. **일관성 검증**: 모든 문서가 동일한 6가지 공통 원칙을 따르는지 확인
2. **git diff 검토**: `git diff --stat` — 10개 문서만 변경되었는지 확인
3. **범위 규칙 준수**: 수정된 파일이 모두 브랜치 diff에 포함되는지 확인
