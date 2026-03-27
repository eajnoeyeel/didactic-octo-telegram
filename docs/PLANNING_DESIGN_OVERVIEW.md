# MCP Selection Optimizer — 기획/설계 통합 검토

> 최종 업데이트: 2026-03-22
> 목적: 14개 문서의 핵심 요약 + 검토 포인트 인덱스. 상세 분석은 각 원본 문서 참조.

---

## 문서 목록

| 파일 | 역할 | 상태 |
|------|------|------|
| `context/project-overview.md` | 프로젝트 요약, North Star, 타임라인 | 확정 |
| `design/architecture.md` | DP0-DP9 결정, 기술 스택, 통제 변인 | 확정 (DP4 실험 대기) |
| `design/architecture-diagrams.md` | Mermaid 다이어그램, 파이프라인 흐름도 | 확정 |
| `design/evaluation.md` | 평가 참조 허브 — 하위 3개 문서 포인터 | 확정 |
| `design/metrics-rubric.md` | 4-Tier 11개 지표 정의 | 확정 |
| `design/metrics-dashboard.md` | Metric Tree, 시각화 명세 | 확정 |
| `design/experiment-design.md` | E1-E7 실험 허브 | 확정 |
| `design/experiment-details.md` | 실험별 상세 프로토콜 | 확정 |
| `design/ground-truth-design.md` | GT 스키마, Seed/Synthetic 전략 | 확정 |
| `design/ground-truth-schema.md` | Pydantic 모델 정의, Quality Gate | 확정 |
| `design/code-structure.md` | 디렉토리/파일 구조 | 확정 |
| `plan/implementation.md` | 구현 허브 (Phase 요약 + 하위 문서 포인터) | 확정 |
| `plan/phase-0-2.md` | Phase 0-2 상세 코드 스니펫 | 진행 중 |
| `plan/phase-3-5.md` | Phase 3-5 상세 | 대기 |
| `plan/phase-6-8.md` | Phase 6-8 상세 | 대기 |
| `plan/phase-9-12.md` | Phase 9-12 상세 | 대기 |
| `plan/deferred.md` | 후순위 기능 + Phase 13 (Gated) | 확정 |
| `plan/checklist.md` | 진행 체크리스트 | 갱신 중 |
| `mentoring/open-questions.md` | OQ-1~5 미결 사항 | OQ-1 해결 |
| `research/description-quality-scoring.md` | OQ-1 DQS 조사 문서 | 완료 |
| `papers/` | 개별 논문 아카이브 (10편+) | 누적 |
| `CONVENTIONS.md` | 문서 관리 규약 | 확정 |

---

## 열린 질문 (OQ-1~5)

| OQ | 주제 | 상태 | 블로킹 대상 |
|----|------|------|------------|
| **OQ-1** | GEO Score: 6-dimension GEO Score 채택 | **RESOLVED** (2026-03-21, 2026-03-26 업데이트) | — |
| **OQ-2** | Smithery 크롤링 + Pool 구성 구체화 | 미결 (Critical) | E1-E6 전체 |
| **OQ-3** | 자체 MCP 서버 3개 구축 범위 | 미결 (High) | E4 A/B 실증 |
| **OQ-4** | Sequential 2-Layer 버그 수정 | 미결 (Medium) | E1 공정성 |
| **OQ-5** | 상세: `mentoring/open-questions.md` 참조 | — | — |

---

## 주요 결정 사항 (DP0-DP9)

| DP | 결정 (한줄) | 상태 |
|----|-------------|------|
| **DP0** | 극한 완성도 우선순위: 추천+Analytics > Distribution > Spec > OAuth | 확정 |
| **DP1** | MCP Tool + REST API 이중 노출 | 확정 |
| **DP2** | 2-Layer (서버→Tool) 추천 단위 | 확정 |
| **DP3** | Strategy Pattern — A(Sequential)/B(Parallel)/C(Taxonomy) 모두 구현 후 실험 | 확정 |
| **DP4** | 임베딩: BGE-M3 vs OpenAI vs Voyage voyage-3 → E2 실험 결정 | 실험 대기 |
| **DP5** | Reranker: Cohere Rerank 3 + low-confidence LLM fallback | 방향 확정 |
| **DP6** | Confidence 분기: gap 기반 (threshold 0.15, E3에서 sweep) | 확정 |
| **DP7** | 데이터: Smithery 크롤링 + 직접 MCP 연결 하이브리드 | 확정 |
| **DP8** | 배포: 로컬 FastAPI → Lambda + API Gateway | 확정 |
| **DP9** | 평가: 커스텀 하네스 + 4-Tier 11개 지표 | 확정 |

---

## 검토 포인트 (핵심만)

### 프로젝트 전체
- North Star Precision@1 >= 50% (Pool 50)과 실제 환경(수천 개) 간 괴리
- Week 1에 Phase 0-4 완료 현실성 (GT 80개 수동 포함)
- 5주 타임라인에 buffer 없음 — 블로커 발생 시 cut 대상 미정

### 파이프라인
- Sequential 전략의 hard-gate 문제: Server Recall@3 미달 시 Precision@1 상한 제약
- RRF Fusion 파라미터(k값, 가중치) 미정
- Confidence threshold 0.15 초기값 근거 부족 (E3 sweep으로 보완 예정)

### 데이터
- Smithery API 접근성/rate limit 미검증 (OQ-2)
- 80개 쿼리 표본의 통계적 power (McNemar's test)
- 자체 MCP 서버 3개 구축 부담 (OQ-3)

### 평가/실험
- 11개 지표 + 하네스를 Phase 5 (2일)에 구현하는 밀도
- E3 threshold sweep: Cohere 무료 1000 req/month로 예상 4000 call 부족
- E4 자체 서버 관련 쿼리 수 극소 → 통계적 유의성 우려

### Provider Analytics
- 5주 스코프 내 실제 구현은 Phase 9 (Analytics 백엔드)뿐, 나머지 Deferred
- 실사용 로그 없이 실험 데이터만으로 데모 설득력

### 기술 스택
- Qdrant 1GB 한도: E2에서 임베딩 3종 × 서버+Tool 인덱스 재빌드 시 용량
- BGE-M3 CPU-only inference 속도 미검증
- 전체 실험 API 비용 예측 부재

### 코드 구조
- GroundTruth 모델 불일치 → `ground-truth-design.md`가 정본
- Seed Set 크기 불일치 → 80개가 최신 결정

---

## 문서 간 불일치 (해결 필요)

1. **GroundTruth 모델**: `implementation.md` vs `ground-truth-design.md` → 후자가 정본
2. **Seed Set 크기**: 50개 vs 80개 혼재 → **80개** 확정
3. **E2 후보**: 2개 vs 3개 → **3개** (BGE-M3/OpenAI/Voyage voyage-3)
4. **Phase 일정**: `implementation.md` vs `checklist.md` 1일 단위 차이 → 동기화 필요
5. **OQ-4 범위**: 넓은 범위에서 Sequential 버그 수정으로 좁혀짐

---

## 논문 참고 (요약)

| 논문 | 핵심 적용 |
|------|-----------|
| RAG-MCP | Primary baseline (43%) |
| ToolTweak | 핵심 테제 근거 (20%→81%) |
| JSPLIT | Strategy C (Taxonomy-gated) |
| ToolScan | Confusion Rate 7 error patterns |
| ToolLLM / StableToolBench / API-Bank | Scale, 평가, GT 설계 참고 |

> 상세: `papers/` 폴더 내 개별 파일 참조

---

> **다음 단계**: 검토 포인트를 기반으로 설계 결정 확정 또는 수정.
> 상세 분석이 필요하면 각 원본 문서를 Read tool로 직접 읽을 것.
