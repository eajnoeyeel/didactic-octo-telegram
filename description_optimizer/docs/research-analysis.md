# Description Optimizer — Research Analysis & Idea Validation

> 작성: 2026-03-28
> 목적: Provider가 MCP 서버/도구를 등록할 때 description을 자동 최적화하여 retrieval 품질을 높이는 기능의 학술적 근거 분석

---

## 핵심 아이디어

Provider가 MCP 서버/도구를 플랫폼에 등록할 때, 원본 description을 LLM 기반으로 자동 재작성(rewrite)하여:
1. **검색 임베딩과의 정렬도(retrieval alignment)** 향상
2. **RAG 후보 검색 품질(Recall@K / MRR)** 향상
3. **사실성(faithfulness)과 의미 보존** 유지

원본 description은 보존하고, 최적화된 `retrieval_description`을 별도 필드로 저장하여 임베딩/검색에 사용.

---

## 학술적 근거 (Evidence)

### Evidence 1: 설명 품질 → 선택률 인과관계

**Paper A — "MCP Tool Descriptions Are Smelly!" (Hasan et al., 2025)**
- 856개 도구/103개 서버 분석, **97.1%** 최소 1개 quality defect
- 설명 augmentation → **+5.85pp 작업 성공률** 향상
- **직접 인과 검증**: 단순 상관이 아닌 augmentation 실험으로 입증

**Paper B — "From Docs to Descriptions" (Wang et al., 2025)**
- 10,831개 MCP 서버 초대규모 분석
- 표준 준수 설명 선택률 **72%** vs 비준수 **20%** (**260% 증가**)
- Functionality 차원이 선택률에 가장 큰 영향 (**+11.6%**)

**Paper F — "Tool Preferences in Agentic LLMs are Unreliable" (EMNLP 2025)**
- 설명의 작은 편집 → 선택 도구의 큰 변화
- 설명은 **"설득 입력(persuasive input)"** — 최적화 가능한 레버

### Evidence 1b: 설명 조작의 극단적 효과

**ToolTweak — "Understanding the Effects of Adversarial Tool Descriptions on LLM Tool Selection" (2025, arxiv:2510.02554)**
- 설명의 반복적 조작으로 선택률 ~20% → **81%** (약 4배 증가)
- 적대적(adversarial) 연구이나, 설명이 선택을 **인과적으로** 결정함을 가장 강력하게 증명
- **적용**: 합법적 품질 개선도 동일한 메커니즘으로 효과를 낼 수 있음. 동시에 과도한 "마케팅"을 방지하는 Quality Gate 필요성의 근거

### Evidence 2: 어떤 차원이 중요한가?

**Paper G — CallNavi (2025)**
- GPT-4o 라우팅 정확도 **91.9%**
- **Purpose clarity + "언제 사용" 가이드**가 최우선
- Parameter 세부사항은 상대적으로 덜 중요

→ 최적화 시 우선순위: Purpose > When-to-use > Disambiguation > Parameters

### Evidence 3: GEO (Generative Engine Optimization)

**GEO 기법 (Aggarwal et al., 2023-2024)**
- 기존 SEO가 검색엔진 최적화였다면, GEO는 **AI/LLM 검색 최적화**
- 핵심 기법: Statistics Addition, Technical Terms, Fluency Optimization, Authoritative Tone
- **프로젝트 적용**: GEO 기법은 description 최적화의 아이디어 원천. 단, GEO Score 향상이 retrieval 성능(P@1) 향상과 직접 동치는 아님 — P@1 A/B에서 GEO↑ + P@1↓ 확인됨. GEO는 진단 보조 지표로 사용.

### Evidence 4: Document Rewriting for Retrieval

**doc2query / docTTTTTquery (Nogueira et al., 2019)**
- 문서에 대해 가능한 쿼리를 생성하여 문서에 추가 → 검색 정확도 향상
- **적용**: description에 "이 도구를 찾을 때 사용할 수 있는 쿼리" 정보를 내재화

**HyDE (Gao et al., 2023)**
- 가상 문서 생성 후 검색 — 쿼리-문서 간 의미 갭 해소
- **역방향 적용**: 도구 description에 "사용자가 이런 상황에서 찾을 것" 정보를 포함

**InPars / Promptagator (Bonifacio et al., 2022; Dai et al., 2023)**
- LLM으로 합성 쿼리 생성 → retriever 학습 데이터
- **적용**: description 최적화 시 예상 쿼리를 고려한 표현 사용

### Evidence 5: 기존 프로젝트 실험 (Enriched Description Pipeline)

**커밋 5ef4c0c (reverted e62a8bf)**
- 외부 소스(GitHub, Glama, MCP Market 등)에서 더 나은 설명을 **수집**
- 3-tier priority: GitHub > External Registry > Smithery
- **차이점**: 수집(collection)이었지 재작성(rewriting)이 아니었음
- **교훈**: 다양한 소스에서 설명을 모으는 것만으로는 한계. **능동적 최적화** 필요

---

## 접근 방식 비교

| 접근법 | 설명 | 장점 | 단점 |
|--------|------|------|------|
| **A: Rule-based Rewriting** | 정규식/템플릿 기반 설명 보강 | 빠름, 결정론적, 무료 | 의미 이해 제한, 유연성 낮음 |
| **B: LLM-based Rewriting** | GPT-4o-mini로 설명 재작성 | 높은 품질, 맥락 이해 | 비용, 비결정론적 |
| **C: Hybrid (Rule + LLM)** | Rule로 분석 → LLM으로 재작성 | 비용 효율적, 높은 품질 | 복잡도 증가 |
| **D: doc2query Augmentation** | 예상 쿼리를 설명에 추가 | 검색 정확도 직접 개선 | 설명이 길어짐 |
| **E: Multi-view Description** | 인간용 + 기계용 설명 분리 생성 | 각 목적에 최적화 | 저장/관리 복잡 |

### 채택: Retrieval-Aligned Rewrite

1. GEO는 진단 신호로만 유지
2. LLM은 query alignment, tool 핵심 기능, schema grounding 중심으로 재작성
3. canonical 출력은 `retrieval_description`

---

## 검증 설계 (Evaluation Strategy)

### 1. Offline A/B Test (Primary Validation)

**방법**: 동일 쿼리셋으로 원본 vs `retrieval_description`의 retrieval quality 비교

```
Setup:
  - Control: 원본 description으로 인덱싱 → 검색
  - Treatment: retrieval_description으로 인덱싱 → 검색
  - 동일 Ground Truth 사용
  - raw pool에 라벨이 없으면 GT에서 pool 교집합만 필터링

Metrics:
  - Recall@K (primary)
  - MRR (secondary)
  - Precision@1 (diagnostic)
  - GEO Score delta (diagnostic only)
```

### 2. Retrieval Safety Gate

**방법**: retrieval text가 검색에 불리한 오염 없이 원문 의미를 유지하는지 검증

```
Gate:
  - cosine similarity(original, retrieval_description) >= 0.85
  - hallucinated params 없음
  - sibling contamination 없음
  - 핵심 숫자/기술 용어 손실 없음
```

**목표 (4-gate)**: GEO 비회귀 gate 제거. GEO Score 향상이 P@1 향상과 상관하지 않으므로 hard gate로 부적절 — diagnostic metric으로 전환 예정.

### 3. Semantic Preservation Test

**방법**: 원본 의미 보존 검증

```
Tests:
  - Cosine similarity(원본 embedding, 최적화 embedding) >= 0.85
  - LLM-as-Judge: "의미가 보존되었는가?" (3-judge ensemble, 1-5점)
  - 원본에 있는 핵심 기능 목록이 최적화 후에도 모두 포함되어야 함
```

### 4. Regression Test

**방법**: 최적화가 기존 파이프라인 성능을 저하시키지 않는지 확인

```
Tests:
  - 기존 E0/E1 baseline 수치 재현 가능
  - 최적화된 description을 사용해도 기존 테스트 모두 PASS
```

### 5. Human Evaluation (Gold Standard)

**방법**: 10개 샘플에 대해 원본 vs 최적화 blind comparison

```
Criteria:
  - 어느 것이 더 명확한가? (clarity)
  - 어느 것이 더 구체적인가? (specificity)
  - 어느 것이 기능을 더 잘 설명하는가? (functionality)
  - 원본의 핵심 의미가 보존되었는가? (preservation)
```

---

## 현재 Empirical Validation (2026-03-30, MCP-Zero)

retrieval-aligned refactor 이후, `data/raw/mcp_zero_servers.jsonl` 기준 오프라인 검증을 수행했다.

### Evaluation Set

- raw pool: `data/raw/mcp_zero_servers.jsonl`
- filtered GT: `data/verification/mcp_zero_gt_filtered.jsonl`
- queries: `178`
- correct tools: `32`
- servers: `10`

### Optimization Coverage

- GT tools optimized: `32`
- `success`: `7`
- `gate_rejected`: `25`
- success tool들이 실제로 영향을 줄 수 있는 queries: `61`

### Query-Level Result

| Metric | Original | Optimized | Delta |
|--------|----------|-----------|-------|
| `P@1` | `0.2753` | `0.3427` | `+0.0674` |
| `Recall@10` | `0.6517` | `0.6629` | `+0.0112` |
| `MRR` | `0.4136` | `0.4439` | `+0.0304` |

### 해석

1. refactor 이후 top-1 retrieval과 상위권 정렬 품질은 실제로 개선됐다.
2. 다만 `Recall@10` 상승 폭은 작아서, 현재 단계는 "후보를 훨씬 더 넓게 찾는다"기보다 "맞는 후보를 더 위로 올린다"에 가깝다.
3. 가장 큰 병목은 optimizer 자체보다 `gate_rejected 25/32`로 드러난 gate throughput이다.
4. long-tail rank는 일부 쿼리에서 오히려 악화되어, 다음 단계는 gate 완화 실험과 regression control이 중심이 되어야 한다.

---

## 결론

**아이디어는 학술적으로 강력하게 뒷받침됩니다.**

1. 97.1% defect rate → 대부분의 설명에 개선 여지 있음 (Paper A)
2. 260% 선택률 차이 → 설명 품질이 실제 비즈니스 가치에 직결 (Paper B)
3. 설명은 persuasive input → 최적화가 실질적 효과를 낼 수 있음 (Paper F)
4. GEO 기법 → description 최적화의 아이디어 원천 (단, GEO Score는 P@1과 직접 상관 없음 — 진단 보조 지표)
5. doc2query/HyDE → retrieval-aware document rewriting의 학술적 기반 존재
6. **현재 실증 결과**: MCP-Zero filtered GT에서 `P@1`, `MRR`는 개선되었고, 다음 bottleneck은 GEO가 아니라 gate throughput으로 확인됨

**리스크**:
- 과도한 최적화로 모든 설명이 비슷해지면 오히려 disambiguation 저하 → Quality Gate로 방지
- LLM hallucination으로 잘못된 기능이 추가될 수 있음 → Semantic Preservation Test로 방지
- 비용: GPT-4o-mini 기준 tool당 ~$0.001 → Pool 50 기준 ~$0.05, 허용 범위
- **GEO-P@1 불일치**: GEO Score 향상이 검색 성능 향상을 보장하지 않음 — 길이 팽창과 sibling 오염이 dense retrieval에 노이즈로 작용. GEO는 최적화 방향의 아이디어 원천이지 selection metric이 아님. (2026-03-30 근본원인 분석에서 확인)

**현재 실무 결론**:
- retrieval-aligned 방향 전환은 타당하다
- GEO는 primary objective가 아니라 diagnostic으로 남겨야 한다
- 다음 성능 레버는 rewrite aggressiveness보다 `gate reject` 감소와 long-tail regression 제어다

---

## References

1. Hasan et al., "MCP Tool Descriptions Are Smelly!", 2025
2. Wang et al., "From Docs to Descriptions", 2025
3. "Tool Preferences in Agentic LLMs are Unreliable", EMNLP 2025
4. CallNavi, 2025
5. Aggarwal et al., "GEO: Generative Engine Optimization", 2023-2024
6. Nogueira et al., "doc2query / docTTTTTquery", 2019
7. Gao et al., "HyDE: Hypothetical Document Embeddings", 2023
8. Bonifacio et al., "InPars", 2022
9. Dai et al., "Promptagator", 2023
10. LLM-Rubric, Microsoft, ACL 2024
11. ToolTweak, "Understanding the Effects of Adversarial Tool Descriptions on LLM Tool Selection", 2025 (arxiv:2510.02554)
12. Patil et al., "Gorilla: Large Language Model Connected with Massive APIs", 2023 (arxiv:2305.15334)
13. MetaTool, ICLR 2024 (arxiv:2310.03128)
14. ToolFlood, "Semantic Covering Attack on Tool Selection", 2025 (arxiv:2603.13950)
