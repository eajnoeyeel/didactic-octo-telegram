# Description Optimizer — Evaluation Design

> 최종 업데이트: 2026-03-28

---

## 평가 목표

Description Optimizer가 실제로 검색 선택률(Precision@1)을 향상시키는지 검증.

## 평가 5단계

### Stage 1: Unit-level Quality (Task 1-5에서 완료)
- 모든 컴포넌트 단위 테스트 통과
- GEO Score 계산 정확성
- Quality Gate 작동 검증

### Stage 2: Description Quality Delta
- 최적화 전후 GEO Score 비교
- 목표: 평균 GEO Score +0.2 이상 향상
- 최소 80% 도구에서 GEO Score 비하락

### Stage 3: Semantic Preservation
- Cosine similarity(original, optimized) >= 0.85
- LLM-as-Judge 의미 보존 검증 (future)

### Stage 4: Offline A/B Test (Primary)
- Control: 원본 description으로 Qdrant 인덱싱 → 검색
- Treatment: 최적화 description으로 인덱싱 → 검색
- 동일 Ground Truth 사용
- Primary: Precision@1 delta
- Secondary: Recall@10, MRR delta

### Stage 5: Statistical Significance
- McNemar's test (paired, binary outcome)
- 유의수준: p < 0.05
- 최소 효과 크기: +5%p Precision@1

## 성공 기준

| 지표 | 목표 | 방법 |
|------|------|------|
| GEO Score delta | +0.2 avg | Before/after comparison |
| Semantic preservation | >= 0.85 cosine | Embedding similarity |
| Precision@1 delta | +10%p | A/B test |
| No regression | 0 tools worse | Gate verification |
