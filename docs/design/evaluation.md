# 평가 체계 참조 허브

> 최종 업데이트: 2026-03-29
> 이 문서는 평가 체계의 경량 요약 + 상세 문서 포인터입니다. 최신 실험 의존관계와 GT 정의는 `experiment-design.md`, `ground-truth-design.md`를 따른다.

---

## 상세 문서

| 파일 | 내용 | 언제 읽는가 |
|------|------|-------------|
| [metrics-rubric.md](metrics-rubric.md) | 11개 지표 정의, 임계값, 시각화 방법 | 지표 설계/구현 시. **target metric rubric** (구현 현황: `src/evaluation/metrics.py`) |
| [ground-truth-design.md](ground-truth-design.md) | Pydantic 스키마, JSONL 형식, self seed 80 + MCP-Atlas per-step primary GT + synthetic 보조 | Ground Truth 작성/검증 시 |
| [experiment-design.md](experiment-design.md) | E0-E7 실험 매트릭스, 통제 변인, CLI 스펙, 외부 데이터 반영 타임라인 | 실험 설계/실행/결과 해석 시 |

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
4. **Description Quality Score** — GEO 점수 (Clarity, Disambiguation, Parameter Coverage, Boundary, Stats, Precision)

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
E0 (1-Layer vs 2-Layer)
  └─► E1 (전략 비교)
        └─► E2 (임베딩 모델)
              └─► E3 (Reranker)
                    ├─► E4 (Description A/B) ★ 테제 검증
                    ├─► E5 (Pool 스케일)
                    └─► E6 (Pool 유사도)

E7 (GEO 점수 방법 비교) ─ E4 selection data와 함께 해석
```

| 실험 | 독립 변인 | Primary Metric | 시기 |
|------|-----------|----------------|------|
| E0 | 아키텍처 (1-Layer / 2-Layer) | Precision@1 | 외부 데이터 통합 직후 |
| E1 | 검색 전략 (A/B/C) | Precision@1 | Week 3 |
| E2 | 임베딩 모델 | Tool Recall@10 | Week 3 |
| E3 | Reranker 타입 | Precision@1 lift | Week 4 |
| E4 | Description 품질 (A/B) | Selection Rate Lift | Week 4 |
| E5 | Pool 크기 (5/20/50/100/200/308) | Precision@1 degradation | Week 4 |
| E6 | Pool 유사도 (Low/Base/High) | Confusion Rate | Week 4 |
| E7 | GEO 점수 방법 (휴리스틱/LLM/Smells 4D) | Spearman + Human agreement | Week 5 |

---

## 실험 결과 해석 체크리스트 _(CTO 멘토링 2026-03-26 반영)_

> "단순 평균 비교로 결론 내리지 않는다." — 변동성·유의성·상관성까지 확인한 후에만 실험 결론을 확정한다.

### 모든 유의미한 실험 공통

- [ ] **X̄-R 관리도 사전 확인**: E1 진행 전, `statistical.compute_control_chart`로 Precision@1 반복 측정 안정성 확인. 불안정(UCL/LCL 이탈) 시 원인 조사 후 실험 진행. (_구현: `src/analytics/statistical.py`_)
- [ ] **단순 수치 차이로 결론 내리지 않기**: 차이가 10%p 미만이면 통계 검정으로 유의성 확인
- [ ] **W&B에 결과 기록**: 실험 설정 + 메트릭 전체 로깅 (재현성 확보)

### E4 전용 — 테제 검증 (3개 모두 필수)

- [ ] **McNemar's test** (`compute_mcnemar`): p < 0.05이면 귀무가설 기각 (Description A/B 차이 유의)
- [ ] **Spearman 상관** (`compute_spearman`): r_s > 0.6, p < 0.05 (GEO Score ↔ selection rate 상관)
- [ ] **OLS Regression R²**: > 0.4, 최소 1개 계수 p < 0.05 (quality 하위 요소 기여도 분해)
- [ ] **Evidence Triangulation 판정**: `metrics-rubric.md §Evidence Triangulation` 기준으로 최종 판정

### E1 전략 비교

- [ ] 차이 < 10%p: Cochran's Q + post-hoc McNemar으로 유의성 확인
- [ ] 차이 ≥ 10%p: 수치 자체로 판단 가능 (통계 검정 선택적)

### E4 결과 해석 기준 (Evidence Triangulation)

| 통과 수 | 판정 |
|---------|------|
| 3개 모두 | 강한 증거 — 인과 주장 가능 |
| Primary(McNemar) + 1개 | 보통 증거 — 방향은 확인 |
| Primary만 | 약한 증거 — 범위 제한 |
| Primary 미통과 | 테제 기각 — Provider 기능 가치 재검토 |
