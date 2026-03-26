# Metrics Dashboard — 레이아웃, Metric Tree, 모니터링 규칙

> 최종 업데이트: 2026-03-22
> 지표 정의/공식: `./metrics-rubric.md`

---

## Dashboard Layout

```text
+------------------------------------------------------------------+
|  NORTH STAR: Precision@1 — [current]%                            |
|  vs baseline: [up/down X%]  |  by strategy: [A: X% | B: Y% | C: Z%]|
+--------------------+--------------------+------------------------+
|  INPUT 1           |  INPUT 2           |  INPUT 3               |
|  Server Recall@K   |  Tool Recall@10    |  Confusion Rate        |
|  [sparkline]       |  [sparkline]       |  [pie: confuse vs miss]|
|  Target: >=90%     |  Target: >=85%     |  Target: <50% of errs  |
+--------------------+--------------------+------------------------+
|  INPUT 4                                |  HEALTH                |
|  Description Quality Score              |  ECE / Latency p95 /   |
|  [histogram: score distribution]        |  Server Error Rate     |
|  OQ-1 미결                               |  [sparklines]          |
+-----------------------------------------+------------------------+
|  EVIDENCE TRIANGULATION (프로젝트 테제 증명)                        |
|  8a. A/B Lift [paired bar]  |  8b. Spearman [scatter]  |  8c. R² |
|  Target: >30%               |  Target: r>0.6           |  >0.4   |
+------------------------------------------------------------------+
|  SECONDARY: NDCG@5 [box plot]  |  MRR [bar]  |  Pass Rate [bar] |
+------------------------------------------------------------------+
```

---

## Metric Tree — 지표 간 인과 관계

```text
                    Precision@1 (NSM)
                   /        |        \
         Server           Tool         Confusion
         Recall@K      Recall@10        Rate
            |              |              |
         MRR          NDCG@5        Description
            |              |         Quality Score
      Server Error      Latency          |
         Rate              |      Evidence Triangulation
                          ECE      /        |        \
                              A/B Lift   Spearman    R²
                              (8a)       (8b)       (8c)
                                           |
                                       Pass Rate
```

- 위로 갈수록 lagging, 아래로 갈수록 leading
- 왼쪽 브랜치 = 검색 품질 (파이프라인 엔지니어링)
- 가운데 = 시스템 건강
- 오른쪽 브랜치 = Provider 가치 증명 (프로젝트 테제, evidence triangulation)

---

## Leading vs Lagging 분류

| 지표 | 유형 | 근거 |
|------|------|------|
| Server Recall@K | Leading | Layer 1 악화 → Precision@1 악화 예측 |
| Tool Recall@10 | Leading | Reranker 입력 품질 → Precision@1 예측 |
| Confusion Rate | Leading | confusion 비율 상승 → description 품질 문제 예측 |
| Description Quality Score | Leading | 점수 낮음 → Selection Rate 저하 예측 |
| ECE | Leading | calibration 악화 → confidence 분기 오류 예측 |
| Precision@1 | Lagging | 파이프라인 전체 결과 사후 측정 |
| Pass Rate | Lagging | 실제 태스크 성공 사후 측정 |
| A/B Selection Rate Lift | Lagging | E4 실험 완료 후에만 측정 가능 |
| Spearman correlation | Lagging | 충분한 데이터 축적 후에만 계산 가능 |
| Regression R-squared | Lagging | A/B + Spearman 이후 심화 분석 |

---

## Alert Thresholds Summary

| 지표 | 정상 | 주의 | 위험 | 대응 |
|------|------|------|------|------|
| Precision@1 | >= 50% | 30-50% | < 30% | 검색 전략 또는 임베딩 모델 재검토 |
| Server Recall@K | >= 90% | 80-90% | < 80% | 서버 임베딩 품질 점검 |
| Tool Recall@10 | >= 85% | 70-85% | < 70% | 임베딩 모델 또는 서버 필터링 점검 |
| Confusion Rate | < 50% | 50-70% | > 70% | Description disambiguation 필요 |
| ECE | < 0.15 | 0.15-0.25 | > 0.25 | Confidence 분기 로직 재검토 |
| Latency p95 | < 2s | 2-5s | > 5s | Reranker 병목 또는 Qdrant 연결 점검 |
| A/B Lift | > 30% | 10-30% | < 10% | Description 차이 불충분 또는 다른 요인 지배 |
| Spearman r_s | > 0.6 | 0.3-0.6 | < 0.3 | GEO 점수 산정 방식 교체 (OQ-1) |
| Regression R-squared | > 0.4 | 0.2-0.4 | < 0.2 | Quality 하위 요소가 selection 설명 불가 |

---

## Review Cadence

| 주기 | 대상 | 행동 |
|------|------|------|
| **매 실험 (즉시)** | Precision@1, Recall@K, Latency, Confusion Rate | W&B에 자동 기록. 전략 비교 즉시 가능 |
| **주 1회** | NDCG@5, MRR, ECE, Server Error Rate | 실험 배치 종합 비교. 추세 확인 |
| **2주 1회** | Evidence Triangulation (8a/8b/8c), Pass Rate | 데이터 충분히 쌓인 후 측정. Provider 기능 방향 점검 |
| **CTO 멘토링 (매주 화)** | 전체 대시보드 스냅샷 | 진행 상황 보고. 지표 해석 피드백 수집 |
| **4/26 제출 전** | 전체 지표 최종 스냅샷 | 최종 보고서용 |

---

## Tooling

| 용도 | 도구 | 이유 |
|------|------|------|
| 실험 결과 추적 | **Weights & Biases** | 실험별 지표 비교, hyperparameter sweep, 시각화 자동 |
| LLM call 추적 | **Langfuse** | Reranker LLM fallback 비용, 응답 시간 모니터링 |
| 대시보드 | **W&B Dashboard** (개발 중), **FastAPI + 간단 HTML** (데모용) | CTO 데모 시 실시간 지표 표시 |
| 실험 코드 | Custom Python harness (`src/evaluation/`) | 2-Layer + Provider 특수 지표는 직접 구현 |
