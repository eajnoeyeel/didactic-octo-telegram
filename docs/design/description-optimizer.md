# Description Optimizer — 설계 문서

> **Version**: 0.1 (2026-04-04)
> **Status**: Draft
> **Branch**: `feat/description-optimizer` (main에서 revert됨, 재설계 후 재구현 예정)

---

## 1. 위치와 목적

### 시스템 내 위치: Description 제어 2단계 모델

MCP Discovery Platform에서 description을 제어해야 하는 단계는 2곳이다:

| 단계 | 시점 | 목적 | 성공 지표 | 담당 컴포넌트 |
|------|------|------|----------|--------------|
| **① Embedding 전** | 도구 등록/인덱싱 시 | 벡터 검색에서 도구를 잘 찾게 | **P@1, Recall@K, MRR** | **Description Optimizer** (이 문서) |
| **② LLM Client 전달 전** | 검색 결과 반환 시 | LLM이 올바른 도구를 선택하게 | **GEO Score, Selection Rate** | GEO Presenter (별도, Phase 2) |

**Description Optimizer는 ①에 해당한다.**

- GEO Score와 **무관**. GEO는 ② 단계의 관심사.
- 목표는 오직 **벡터 검색 정확도 극대화** (P@1).
- 원본 description은 보존. 최적화된 `search_description`을 별도 필드로 생성하여 embedding에 사용.

### 한줄 요약

> Provider의 원본 description을 **retrieval-optimized text**로 변환하여, 임베딩 검색에서 정확한 도구가 상위에 노출되도록 한다.

---

## 2. 핵심 가설과 근거

### 가설

> "원본 description보다 retrieval에 최적화된 description을 embedding하면 P@1이 향상된다."

### 학술적 근거

| 근거 | 출처 | 핵심 발견 |
|------|------|----------|
| Description 품질 → 선택률 인과관계 | Description Smells (Hasan 2025) | augmentation → +5.85pp 성공률 |
| Functionality 차원이 가장 큰 영향 | From Docs to Descriptions (Wang 2025) | +11.6% selection uplift |
| 설명이 선택을 인과적으로 결정 | ToolTweak (2025) | 선택률 20% → 81% |
| 문서 → 예상 쿼리 추가로 검색 향상 | doc2query (Nogueira 2019) | 검색 정확도 직접 개선 |
| Purpose clarity가 최우선 | CallNavi (2025) | GPT-4o 라우팅 정확도 91.9% |

### 이전 실험 교훈 (2026-03-28 ~ 03-31)

| 교훈 | 상세 |
|------|------|
| **GEO 점수 최적화 ≠ 검색 품질** | GEO Score를 높이도록 최적화하면 Goodhart's Law 발동. P@1과 GEO는 독립적 |
| **Sibling context 완전 제거는 과도** | sibling 이름 나열 제거는 유효하나, context 완전 제거 시 P@1 악화 (0.5417 → 0.375) |
| **input_schema grounding 필수** | schema 없이 최적화하면 파라미터 환각 발생 |
| **Full rewrite보다 augmentation** | 원본의 통계/고유 용어를 파괴하면 검색 품질 하락 |
| **Quality Gate 필수** | 최적화가 오히려 검색 품질을 떨어뜨리는 케이스가 존재. 원본보다 나빠지면 원본 유지 |

---

## 3. 파이프라인 설계

### 흐름

```
Provider 등록 → 원본 description 저장
    ↓
Description Optimizer Pipeline
    ↓
    [1] Context 수집
        - input_schema (실제 파라미터)
        - sibling tools (같은 서버 내 다른 도구 — 이름 + 한줄 설명만)
        - tool_name
    ↓
    [2] LLM Optimization (retrieval-aligned rewrite)
        - Purpose clarity 강화 (이 도구가 무엇을 하는가)
        - 예상 쿼리 내재화 (doc2query 스타일)
        - input_schema 기반 파라미터 정보 보강
        - sibling 대비 차별점 명확화 (이름 나열 없이)
        - 원본의 고유 정보 보존 (augmentation 모드)
    ↓
    [3] Quality Gate
        - Similarity check: 원본과의 의미 유사도 하한
        - Hallucination check: input_schema에 없는 파라미터 언급 탐지
        - Retrieval regression check: 최적화 후 검색 순위가 하락하면 reject
    ↓
    [4] 결과
        - PASS → search_description = 최적화 텍스트
        - REJECT → search_description = 원본 description (안전 폴백)
```

### 데이터 모델

```python
class MCPTool(BaseModel):
    tool_id: str                      # "server_id::tool_name"
    description: str                  # 원본 (불변)
    search_description: str | None    # ① 최적화된 검색용 텍스트
    # display_description: str | None  # ② LLM Client용 (Phase 2, 별도 컴포넌트)
    input_schema: dict | None
```

### Embedding 흐름 변경

```
현재:  description → embed → Qdrant
변경후: search_description ?? description → embed → Qdrant
        (search_description이 있으면 사용, 없으면 원본 fallback)
```

---

## 4. 최적화 전략

### 우선순위 (CallNavi + Description Smells 근거)

1. **Purpose clarity** — "이 도구는 X를 한다" 명확화
2. **When-to-use** — "Y 상황에서 사용" (doc2query 내재화)
3. **Disambiguation** — 같은 서버 내 유사 도구와의 차별화 (이름 나열 없이, 기능 차이로)
4. **Parameter grounding** — input_schema 기반 핵심 파라미터 언급

### 하지 않는 것

- GEO Score 최적화 (② 단계의 관심사)
- Boundary/limitation 추가 (환각 위험 높음)
- 마케팅성 과장 (adversarial optimization 방지)
- 원본 정보 삭제 (augmentation only)

---

## 5. 평가 체계

### 평가 방법: 실제 RAG 파이프라인 기반 A/B

P@1 측정은 실제 검색 파이프라인을 그대로 사용한다. 두 조건의 차이는 **embedding 대상 텍스트만** 다르고, 나머지(Qdrant 검색 → Cohere Rerank → Confidence branching)는 동일하다.

```
[Condition A: Original]
description → embed → Qdrant index(A)
    GT query → embed → Qdrant search(A) → Rerank → top-1 → P@1 측정

[Condition B: Optimized]
search_description → embed → Qdrant index(B)
    GT query → embed → Qdrant search(B) → Rerank → top-1 → P@1 측정
```

- **독립 변수**: embedding 대상 텍스트 (description vs search_description)
- **통제**: 동일 GT, 동일 embedding 모델, 동일 reranker, 동일 파이프라인
- **Qdrant collection 분리**: 두 조건을 별도 collection에 인덱싱하여 오염 방지

### 성공 기준

| 지표 | 기준 | 측정 방법 |
|------|------|----------|
| **P@1** | Condition B > Condition A | GT 474 queries 전체 |
| **Recall@10** | 하락 없음 | 동일 |
| **MRR** | 향상 | 동일 |
| **Gate reject → 원본 유지** | reject된 케이스에서 원본이 더 나은지 확인 | reject 케이스별 P@1 비교 |

### Anti-pattern

- GEO Score로 최적화 품질을 판단하지 않는다
- 최적화 전후 GEO Score 변화를 성공 지표로 사용하지 않는다
- 실제 RAG 파이프라인을 거치지 않는 단순 유사도 비교로 P@1을 대체하지 않는다

---

## 6. 실험 연계 (E4)

E4 실험: "Higher description quality → higher tool selection rate" 검증

- Description Optimizer의 search_description을 사용한 검색 결과 vs 원본 description
- 독립 변수: description (original vs search_description)
- 종속 변수: P@1, Recall@K, MRR
- 통제: 동일 GT, 동일 embedding 모델, 동일 reranker
- 실제 RAG 파이프라인(Qdrant → Rerank → Confidence)을 통한 end-to-end 평가

---

## 7. 백로그 상태와 다음 단계

### 현재 상태

- `feat/description-optimizer` 브랜치에 이전 구현 존재 (main에서 revert됨)
- 이전 구현은 GEO Score 최적화 + retrieval 검증 혼합 — 재설계 필요
- 재사용 가능한 부분: LLM optimizer 구조, quality gate 프레임워크, 평가 스크립트

### 재구현 시 변경 사항

| 이전 | 재설계 |
|------|--------|
| GEO Score 기반 분석 → 최적화 → GEO 재평가 | P@1 기반 평가만 (실제 RAG 파이프라인 사용) |
| `optimized_description` + `retrieval_description` 이중 필드 | `search_description` 단일 필드 |
| Heuristic GEO analyzer 의존 | GEO analyzer 제거 (진단 목적으로도 불필요) |
| Quality Gate에 GEO 기반 체크 포함 | Similarity + Hallucination + Retrieval regression만 |
| 6D 차원별 최적화 프롬프트 | Retrieval-aligned 단일 프롬프트 |
| 단순 cosine similarity로 P@1 대체 | 실제 RAG 파이프라인 end-to-end 평가 |

### 우선순위

백로그. MLP 핵심 경로(Search API, Bridge MCP, Registry UI, Provider Dashboard) 완료 후 진행.
