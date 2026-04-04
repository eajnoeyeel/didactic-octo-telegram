# Description Control Architecture — 2단계 모델

> **Version**: 0.1 (2026-04-04)
> **Status**: Draft

---

## 1. 개요

MCP Discovery Platform에서 tool description은 2곳에서 제어된다. 각 단계는 **목적, 성공 지표, 최적화 대상이 완전히 다르다.**

```
Provider 등록 (원본 description)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Stage ①  Description Optimizer                     │
│  시점: Embedding 전 (인덱싱 파이프라인)               │
│  입력: description (원본)                             │
│  출력: search_description (검색 최적화 텍스트)         │
│  목표: 벡터 검색 정확도 극대화                         │
│  지표: P@1, Recall@K, MRR                            │
│  GEO: 무관                                           │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
              search_description → embed → Qdrant
                       │
                       ▼
              사용자 쿼리 → Qdrant 검색 → Rerank → top-K 결과
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Stage ②  GEO Presenter (Phase 2)                   │
│  시점: LLM Client에 결과 전달 전                      │
│  입력: top-K 검색 결과 (tool + description)            │
│  출력: display_description (LLM이 판단하기 좋은 텍스트) │
│  목표: LLM이 올바른 도구를 선택하도록                   │
│  지표: GEO Score, Selection Rate                      │
│  P@1: 이미 확정 (Stage ①에서 결정)                     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
              LLM Client가 도구 선택/실행
```

---

## 2. 왜 2단계인가

### 검색과 선택은 다른 문제

| | Stage ① 검색 | Stage ② 선택 |
|---|---|---|
| **질문** | "이 쿼리에 맞는 도구를 풀에서 찾아라" | "찾은 도구 중 어떤 것을 쓸지 판단하라" |
| **주체** | 임베딩 모델 + Reranker (기계적) | LLM Client (언어적 판단) |
| **좋은 description** | 쿼리와 벡터 공간에서 가까운 텍스트 | 기능/용도/제약이 명확하여 LLM이 판단하기 쉬운 텍스트 |
| **위험** | 검색 누락 (원하는 도구가 top-K에 없음) | 선택 오류 (top-K 안에 있지만 잘못된 도구 선택) |

하나의 description으로 두 목적을 동시에 최적화하면 충돌이 발생한다:
- 검색 최적화를 위해 예상 쿼리를 내재화하면, LLM이 읽기에 부자연스러워짐
- LLM 판단을 위해 제약/경계를 상세히 쓰면, 벡터 공간에서 쿼리와 멀어짐

**따라서 분리한다.**

---

## 3. Stage ① Description Optimizer (상세)

### 목적

원본 description을 **retrieval-optimized text**로 변환하여, 임베딩 검색에서 정확한 도구가 top-K에 포함되도록 한다.

### 핵심 원칙

1. **P@1이 유일한 성공 지표** — GEO Score 변화는 측정하지도 않는다
2. **실제 RAG 파이프라인으로 평가** — Qdrant 검색 → Rerank → P@1 측정
3. **원본보다 나빠지면 원본 유지** — Quality Gate의 최종 방어선
4. **Augmentation only** — 원본 정보를 삭제하지 않고 보강만 한다

### 파이프라인 내 위치

```
Register Lambda → Supabase INSERT (description 원본, index_status='pending')
    ↓ EventBridge
Index Lambda
    ├── [신규] Description Optimizer (description → search_description)
    ├── OpenAI embed (search_description ?? description)
    ├── Qdrant upsert
    └── Supabase UPDATE (index_status='indexed', search_description)
```

### 데이터 필드

| 필드 | 용도 | 단계 |
|------|------|------|
| `description` | 원본 (불변). Provider가 등록한 그대로 | - |
| `search_description` | Stage ① 출력. Embedding 대상 | Stage ① |
| `display_description` | Stage ② 출력. LLM Client에 전달 | Stage ② (Phase 2) |

### 상세 설계

`docs/design/description-optimizer.md` 참조.

---

## 4. Stage ② GEO Presenter (Phase 2)

### 목적

검색으로 찾은 top-K 도구의 description을 **LLM이 올바른 판단을 내리기 좋은 형태**로 변환하여 전달한다.

### 핵심 원칙

1. **GEO Score가 핵심 지표** — Clarity, Disambiguation, Parameter Coverage 등
2. **Selection Rate로 최종 검증** — LLM이 실제로 올바른 도구를 선택하는 비율
3. **검색 결과는 건드리지 않음** — Stage ①에서 결정된 top-K를 변경하지 않고, 표현만 최적화

### 비즈니스 확장

- Provider가 자신의 도구에 대해 GEO Score를 높이면 LLM의 선택 확률이 올라감
- 추후 특정 Provider의 GEO Score를 경쟁 도구보다 높여 선택률을 올리는 유료 서비스 가능
- `is_boosted` + `boost_score`와 연계 가능

### 현재 상태

MLP에서는 미구현. Provider Dashboard에서 GEO Score **진단**만 제공 (src/analytics/geo_score.py).
실제 `display_description` 생성 및 적용은 Phase 2.

---

## 5. 전체 흐름 요약

```
Provider 등록
    │
    ▼
description (원본, 불변)
    │
    ├──→ Stage ① Description Optimizer (백로그)
    │         search_description 생성
    │         목표: P@1 극대화
    │         GEO: 무관
    │
    ▼
search_description ?? description → embed → Qdrant
    │
    ▼
사용자 쿼리 → Qdrant search → Cohere Rerank → top-K
    │
    ├──→ Stage ② GEO Presenter (Phase 2)
    │         display_description 생성
    │         목표: LLM 선택 정확도
    │         GEO: 핵심 지표
    │
    ▼
LLM Client에 결과 전달
    tool_id + display_description + input_schema + score_breakdown
```

---

## 6. 문서 참조

| 문서 | 내용 |
|------|------|
| `docs/design/description-optimizer.md` | Stage ① 상세 설계 (파이프라인, 평가, 백로그) |
| `mlp/docs/service-design.md` | MLP 서비스 설계 (Stage ② GEO 진단은 FR7 Provider Dashboard) |
| `src/analytics/geo_score.py` | GEO Score 6D heuristic (Stage ② 진단용, MLP canonical) |
| `docs/design/experiment-design.md` | E4 실험 — description quality → selection rate 검증 |
