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
