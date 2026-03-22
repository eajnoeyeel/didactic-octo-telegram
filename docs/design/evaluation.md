# 평가 체계 참조 허브

> 최종 업데이트: 2026-03-21
> 이 문서는 평가 체계의 경량 요약 + 상세 문서 포인터입니다.

---

## 상세 문서

| 파일 | 내용 | 언제 읽는가 |
|------|------|-------------|
| [metrics-rubric.md](metrics-rubric.md) | 11개 지표 정의, 임계값, 시각화 방법 | 지표 계산/구현 시. **평가 코드의 source of truth** |
| [ground-truth-design.md](ground-truth-design.md) | Pydantic 스키마, JSONL 형식, 80개 seed set, synthetic 생성 + Quality Gate | Ground Truth 작성/검증 시 |
| [experiment-design.md](experiment-design.md) | E1-E7 실험 매트릭스, 통제 변인, CLI 스펙, W&B 연동, Threats to Validity | 실험 설계/실행/결과 해석 시 |

---

## 평가 체계 요약 (4-Tier)

### Tier 1: North Star (1개)
- **Precision@1** >= 50% (Pool 50, mixed domain)
  - Stretch: >= 65% (Pool 100, high similarity)
  - Alert: < 30% → 전략/임베딩 재검토

### Tier 2: Input Metrics (4개) — North Star를 끌어올리는 레버
1. **Server Recall@K** (K=3 or 5) — Layer 1에서 정답 서버 포함 여부
2. **Tool Recall@10** — Reranking 전 후보 품질
3. **Confusion Rate** — 유사 Tool 혼동으로 인한 오류 비율
4. **Description Quality Score** — SEO 점수 (Specificity, Disambiguation, Coverage)

### Tier 3: Health Metrics (3개) — 시스템 정상 동작 확인
5. **ECE** (Expected Calibration Error) — Confidence 신뢰도
6. **Latency** (p50/p95/p99) — 컴포넌트별 응답 시간
7. **Server Classification Error Rate** — Layer 1 hard-gate 실패율

### Tier 4: Evidence Triangulation (3개) — 테제 검증
8a. **A/B Selection Rate Lift** > 30%, McNemar's test p < 0.05
8b. **Spearman r** (quality ↔ selection) > 0.6, p < 0.05
8c. **OLS Regression R²** > 0.4

**판정**: 3개 중 2개 이상 통과 → 테제 지지

---

## 실험 의존관계 그래프

```
E1 (전략 비교)
  └─► E2 (임베딩 모델) ─ E1 최적 전략 고정
        └─► E3 (Reranker) ─ E1+E2 고정
              ├─► E4 (Description A/B) ★ 테제 검증
              ├─► E5 (Pool 스케일)
              └─► E6 (Pool 유사도)

E7 (SEO 점수 방법) ─ OQ-1 해결 후 독립 실행
```

| 실험 | 독립 변인 | Primary Metric | 시기 |
|------|-----------|----------------|------|
| E1 | 검색 전략 (A/B/C) | Precision@1 | Week 2 |
| E2 | 임베딩 모델 | Tool Recall@10 | Week 3 |
| E3 | Reranker 타입 | Precision@1 lift | Week 3 |
| E4 | Description 품질 (A/B) | Selection Rate Lift | Week 4 |
| E5 | Pool 크기 (5/20/50/100) | Precision@1 degradation | Week 4 |
| E6 | Pool 유사도 (Low/Base/High) | Confusion Rate | Week 4 |
| E7 | SEO 점수 방법 (regex/LLM) | Human agreement | TBD |
