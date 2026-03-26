# 실험 설계 — Hub: E0-E7 요약 + 공유 방법론

> 최종 업데이트: 2026-03-22
> 상세 스펙 (입력/출력/코드): `./experiment-details.md`

---

## 실험이 답하는 4가지 질문

1. **2-Layer가 1-Layer 대비 실질적 향상을 가져오는가?** — E0
2. **어떤 검색 전략이 최적인가?** — E1
3. **어떤 임베딩/Reranker가 최적인가?** — E2, E3
4. **Description 품질이 선택률에 인과적 영향을 미치는가?** — E4 (핵심 테제)

---

## E0-E7 One-line Summary

| ID | 이름 | Primary Metric | 상태 |
|----|------|---------------|------|
| **E0** | 1-Layer vs 2-Layer 아키텍처 검증 | Precision@1 (2-Layer >= 1-Layer +5%p) | E1 전제조건 |
| **E1** | 검색 전략 비교 (Sequential / Parallel / Taxonomy) | Precision@1 | 핵심 실험 |
| **E2** | 임베딩 모델 비교 (BGE-M3 / OpenAI / Voyage) | Tool Recall@10 | E1 후 진행 |
| **E3** | Reranker 비교 (Cohere / Cohere+LLM / LLM-only) | Precision@1 향상폭 | E2 후 진행 |
| **E4** | Description 품질 → 선택률 인과 관계 | A/B Lift > 30% | **가장 중요** |
| **E5** | Pool 스케일 (5/20/50/100 서버) | Precision@1 저하 곡선 | E4와 병렬 |
| **E6** | Pool 유사도 (Low/Base/High similarity) | Confusion Rate 변화 | E4와 병렬 |
| **E7** | GEO 점수 방식 비교 (휴리스틱 vs LLM) | Spearman(geo_score, selection_rate) | OQ-1 해결 |

---

## 독립 변인 (Manipulated Variables)

| 변인 | 수준 | 설명 |
|------|------|------|
| 검색 전략 | Sequential (A), Parallel (B), Taxonomy-gated (C) | `PipelineStrategy` 구현체 교체 |
| 임베딩 모델 | BGE-M3, OpenAI text-embedding-3-small, Voyage voyage-3 | 인덱스 빌드 시 교체 |
| Reranker | Cohere Rerank 3, Cohere + LLM fallback, LLM-as-Judge | Reranker 구현체 교체 |
| Description 품질 | Version A (Poor), Version B (Good) | 자체 MCP 서버 A/B pair |
| Tool Pool 크기 | 5, 20, 50, 100 서버 | `build_index.py --pool-size` |
| Tool Pool 유사도 | Low, Base, High similarity | Pool 정의 파일 교체 |

## 종속 변인 (Measured Variables)

| 실험 유형 | Primary Metric | Secondary Metrics |
|-----------|---------------|-------------------|
| 전략 비교 | Precision@1 | Recall@K, Latency p95, Confusion Rate |
| 임베딩 비교 | Tool Recall@10 | Precision@1, Latency, cold start time |
| Reranker 비교 | Precision@1 향상폭 | Latency 증가폭, 비용 |
| Description A/B | Selection Rate Lift | Spearman r, Regression R-squared |
| Pool 스케일 | Precision@1 저하율 | Latency 증가율, Confusion Rate |

## 통제 변인 (한 실험에서 하나의 독립변인만 변경)

| 변인 | 고정값 (기본) |
|------|-------------|
| Ground Truth | seed_set.jsonl + synthetic.jsonl (동일 셋) |
| Query 순서 | 동일 (Position bias는 별도 실험) |
| Reranker Top-K | K=10 (Reranker 비교 실험 제외) |
| Confidence 임계값 | gap > 0.15 (Confidence 실험 제외) |
| 실행 환경 | 동일 머신, 동일 Python 3.12 환경 |

---

## 실험 실행 순서 (의존관계)

```
Phase 0: Ground Truth 구축 (seed set + Pool 정의)
    |
Phase 0.5: E0 (1-Layer vs 2-Layer) — 전제 조건 확인
    | [2-Layer 유효 판정 시]
Phase 1: E1 (전략 비교) — 최적 전략 결정
    |
Phase 2: E2 (임베딩 비교) — E1 최적 전략 고정
    |
Phase 3: E3 (Reranker 비교) — E1+E2 결과 고정
    |
Phase 4 (병렬):
    +-- E4 (Description A/B) — 테제 검증
    +-- E5 (Pool 스케일) — 스케일 테스트
    +-- E6 (Pool 유사도) — Confusion Rate 심화

Phase 5 (OQ-1 해결 후):
    +-- E7 (GEO 점수 비교) — E4와 함께 분석
```

- **E0은 E1의 전제 조건**: 2-Layer 유효성 미확인 시 E1 전략 비교 의미 변경
- **Phase 1-3은 순차적**: 각 실험 최적 결과 → 다음 실험 고정값
- **Phase 4는 병렬 가능**: E4, E5, E6 서로 독립

---

## 타임라인

| 주차 | 기간 | 실험 | 산출물 |
|------|------|------|--------|
| Week 1 | 3/20 - 3/26 | Ground Truth 구축 (seed set) | seed_set.jsonl (80개) |
| Week 2 | 3/27 - 4/2 | E1 (전략 비교) | 최적 전략 결정 |
| Week 3 | 4/3 - 4/9 | E2 (임베딩) + E3 (Reranker) | 최적 파이프라인 확정 |
| Week 4 | 4/10 - 4/16 | E4 (테제 검증) + E5 + E6 | evidence triangulation 결과 |
| Week 5 | 4/17 - 4/25 | 보고서 작성 + Provider Analytics 데모 | 최종 제출물 |

---

## 통계적 검증 적용 계획

### X̄-R 관리도 (Control Chart) — E0 직전 1회

실험 전체의 측정 안정성을 먼저 확인한다. 관리도가 불안정하면 이후 모든 실험 결과를 신뢰할 수 없으므로 선행 조건으로 취급.

```
목적: Precision@1 측정이 반복 실행에서도 일관되는가?
방법: 동일 조건으로 N회 반복 → 서브그룹(5회 단위) X̄, R 계산 → UCL/LCL ±3σ 이내 확인
판정: 관리 한계 이탈 시 원인 조사 (랜덤 시드, 파이프라인 비결정성 등) → 수정 후 재확인
구현: src/evaluation/metrics/control_chart.py
```

### 가설 검정 (p-value) — 실험별 적용 우선순위

| 실험 | 필요도 | 검정 방법 | 이유 |
|------|--------|-----------|------|
| E0 | 권장 | Mann-Whitney U | 1-Layer vs 2-Layer 차이 확인 |
| E1 | 권장 | Cochran's Q + post-hoc McNemar | 3-way 전략 비교 |
| E2, E3 | 선택적 | Mann-Whitney U | 탐색 실험, 수치 자체로 판단 가능 |
| **E4** | **필수** | **McNemar's test** | **핵심 테제 증명, p < 0.05 요구** |
| E5, E6 | 선택적 | — | 추세 분석이 주목적 |

> **실용적 원칙**: E1-E3는 수치 차이가 명확하면(>10%p) 검정 생략 가능. E4는 논문 수준 증명이 목적이므로 검정 필수.

---

## 위협 요인 (Threats to Validity)

### Internal Validity
- **Ground Truth 편향**: seed set 작성자 = 실험 설계자 → 특정 전략에 유리한 쿼리 가능
  - 완화: LLM synthetic 쿼리 병행, seed 작성 시 전략 구현 비참조
- **A/B Description 차이 크기**: Version A를 너무 나쁘게 만들면 lift 과대 측정
  - 완화: Version A도 실제 Smithery 수준 description으로 설정

### External Validity
- **Pool 규모**: 실제 MCP 생태계(수천 서버) vs 실험 Pool(50-100서버)
  - 완화: E5 스케일 실험으로 추세 분석
- **쿼리 분포**: 실제 사용자 쿼리와 실험 쿼리의 분포 차이
  - 완화: 난이도/모호도 분포를 의도적으로 다양화

### Construct Validity
- **GEO 점수 validity (OQ-1)**: 점수 자체가 "품질"을 잘 반영하는지 미검증
  - 완화: E7에서 human agreement 측정
- **Precision@1 한계**: multi-correct 케이스에서 하나만 정답 인정
  - 완화: NDCG@5 병행, alternative_tools 활용

---

## 최종 보고서 구조 (4/26 제출)

1. **Abstract**: 핵심 결과 한 문단
2. **실험 설정**: Pool 구성, Ground Truth 통계, 하드웨어 스펙
3. **E1-E3 결과**: 최적 파이프라인 결정 과정 + 수치
4. **E4 결과**: 테제 검증 (evidence triangulation 3개 지표)
5. **E5-E6 결과**: 스케일 및 robustness 분석
6. **Discussion**: 한계, 위협 요인, 향후 연구
7. **Provider Analytics 데모**: E4 결과 기반 대시보드 스크린샷
