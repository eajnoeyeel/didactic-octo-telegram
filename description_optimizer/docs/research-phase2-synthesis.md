# Description Optimizer — Phase 2 리서치 종합

> **작성:** 2026-03-29
> **목적:** GEO Scorer의 Goodhart's Law 문제를 해결하기 위한 근거 기반 접근법 도출
> **핵심 질문:** "실제 도구 선택 성능(P@1)과 상관관계가 있고 게이밍에 강건한 description 품질 평가 방법은 무엇인가?"

---

## 클러스터 A: 환각에 강건한 평가 방법

### 논문별 요약

#### 1. FActScore (Min et al., EMNLP 2023)
- **기법:** 텍스트를 원자적 사실(atomic facts)로 분해 → 각각을 지식 소스(Wikipedia 등) 대비 검증. FActScore = 지지된 사실 / 전체 사실.
- **핵심 수치:** 인간 평가 대비 2% 미만 오류율, Pearson r=0.99
- **비용:** $0.01/100문장 (자동화, OpenAI API)
- **적용 가능성: 중-상.** 커스텀 지식 소스(JSONL 형식) 지원 → input_schema를 지식 기반으로 사용 가능. 단, 도구 description이 1-3문장으로 짧아 원자적 사실이 2-6개에 불과하여 점수가 거칠 수 있음.
- **핵심 시사점:** 원자적 분해 + 이진 검증 패턴이 직접 재사용 가능. 검색 단계는 input_schema가 작으므로 생략하고 프롬프트에 직접 포함.

#### 2. G-Eval (Liu et al., EMNLP 2023 / NeurIPS)
- **기법:** 3단계 — (1) 과제+평가 기준 입력 → LLM이 CoT 평가 단계 자동 생성, (2) CoT로 NLG 출력 평가 (1-5점), (3) 출력 토큰의 확률 가중 합산으로 연속 점수 산출.
- **핵심 수치:** Spearman 상관 0.514 (SummEval 평균), BERTScore 0.225 대비 대폭 개선. logprob 없으면 평가당 20회 LLM 호출 필요.
- **비용:** 높음 (20회 샘플링). logprob 접근 가능하면 1회.
- **적용 가능성: 중.** 품질 점수(명확성, 완결성)에는 적합하나 환각 탐지에는 부적합. Consistency 차원 Spearman 0.507으로 보통. **자기 향상 편향(self-enhancement bias)** — GPT-4가 GPT-3.5 출력에 항상 높은 점수 부여.
- **핵심 시사점:** CoT 프롬프트 생성 접근법은 가치 있음. 단, 환각 탐지에는 이진 주장 검증(FActScore/RAGAS)이 Likert 점수보다 정밀.

#### 3. SelfCheckGPT (Manakul et al., EMNLP 2023)
- **기법:** N개(기본 20) 확률적 샘플 생성 → 일관성 확인. LLM이 사실을 알면 일관됨, 환각이면 발산. 5가지 변형(BERTScore, QA, n-gram, NLI, LLM-Prompting).
- **핵심 수치:** LLM-Prompting AUC-PR 93.42. NLI AUC-PR 92.50.
- **비용:** ~$200/전체 평가 (GPT-3), ~$20 (ChatGPT). 20 샘플 필요.
- **적용 가능성: 하.** 근본 전제가 불일치 — 내부 일관성 확인이지 외부 참조 대비 검증이 아님. 우리 문제는 input_schema라는 ground truth가 있는 참조 기반 검증.
- **핵심 시사점:** NLI 기반 접근법(주장과 참조 간 모순 확인)은 유용. DeBERTa-v3-large MNLI 파인튜닝으로 LLM 호출 없이 비용 효율적 검증 가능.

#### 4. LLM-as-Judge (Zheng et al., NeurIPS 2023)
- **기법:** GPT-4를 판사로 사용. 쌍별 비교, 단독 채점, 참조 기반 채점 구성 테스트. 3가지 편향 식별 및 정량화.
- **핵심 수치:** GPT-4-인간 합의율 85% (인간-인간 81% 초과). **위치 편향**: GPT-4 65% 일관, 30% 첫 번째 위치 편향. **장황함 편향 공격**: GPT-4만 8.7% 실패 (다른 모델 91.3%). **자기 향상 편향**: GPT-4 ~10% 과대 승률.
- **적용 가능성: 상 (주의사항 포함).** 편향 식별이 우리 Goodhart 문제를 설명. **핵심 인사이트: 최적화와 평가에 같은 모델 사용 금지.** 참조 기반 채점이 수학/추론 실패율을 70%→15%로 감소.
- **핵심 시사점:** 4가지 규칙: (1) 최적화-평가 모델 분리, (2) input_schema를 참조 자료로 포함, (3) A/B 비교 시 위치 교환, (4) Likert보다 구조화된 이진 검증 선호.

#### 5. RAGAS (Shahul et al., EACL 2024)
- **기법:** RAG 파이프라인 평가 프레임워크. Faithfulness = 2단계 LLM 호출: (1) 답변에서 주장 추출, (2) 각 주장을 컨텍스트 대비 NLI 검증. 점수 = 지지된 주장 / 전체 주장.
- **핵심 수치:** Faithfulness 정확도 0.95 (WikiEval). 평가당 2회 LLM 호출.
- **비용:** 낮음 (2 LLM 호출). SelfCheckGPT(20 샘플), G-Eval(20 샘플) 대비 경제적.
- **적용 가능성: 상.** context = input_schema + 원본 description, answer = 최적화된 description으로 직접 매핑. "최적화된 설명이 도구의 실제 기능에 충실한가?" 질문에 정확히 답함.
- **핵심 시사점:** RAGAS faithfulness 패턴 직접 채택: (1) 최적화 description에서 주장 추출, (2) 각 주장을 input_schema + 원본 대비 검증, (3) 지지되지 않는 주장 = 환각. FActScore보다 저렴(검색 불필요), G-Eval보다 정밀(주장별 이진 검증).

### 교차 비교

| 방법 | Ground Truth 필요? | 평가당 비용 | 환각 탐지 능력 | 적용 가능성 |
|------|-------------------|-----------|--------------|------------|
| FActScore | 예 (지식 소스) | ~$0.01/100문장 | 상 (원자적 검증) | 중-상 |
| G-Eval | 아니오 (루브릭) | ~$0.02 (20 샘플) | 중 (Likert 점수) | 중 |
| SelfCheckGPT | 아니오 (샘플링) | ~$0.02 (20 샘플) | 중 (일관성만) | 하 |
| LLM-as-Judge | 선택적 | ~$0.002/평가 | 중 (편향 존재) | 상 (메타 가이드) |
| **RAGAS** | **예 (컨텍스트)** | **~$0.002 (2 호출)** | **상 (정확도 0.95)** | **상** |

### 추천: RAGAS Faithfulness + FActScore 분해 하이브리드

1. **주장 추출** (FActScore에서): 최적화 description을 원자적 사실로 분해 → 2-6개 사실
2. **이진 검증** (RAGAS에서): 각 사실을 input_schema + 원본 대비 NLI 검증. 검색 불필요.
3. **편향 완화** (LLM-as-Judge에서): 최적화와 평가에 다른 모델 사용. input_schema를 참조로 포함.
4. **점수 계산:** 환각률 = 1 - (지지된 사실 / 전체 사실). 게이트: 환각률 > 0이면 거부.
5. **비용 추정:** 평가당 2 LLM 호출 ≈ $0.002 (GPT-4o-mini)

---

## 클러스터 B: 검색 정렬 Description 최적화

### 핵심 논문

#### 1. doc2query / docTTTTTquery (Nogueira et al., 2019)
- **기법:** 문서에 대한 합성 쿼리를 T5로 생성하여 문서에 추가 (document expansion)
- **핵심 수치:** MRR@10 18.4→27.2 (+47.8%, MS MARCO). 40개 쿼리가 실용적 최적점.
- **적용 가능성: 상.** "이 도구를 찾을 때 사용할 쿼리"를 생성하여 최적화 가이드로 사용 가능.

#### 2. Tool-DE: "Tools are under-documented" (Lu et al., 2025) — 가장 직접 관련
- **기법:** LLM으로 도구 문서를 5개 구조화 필드로 확장: function_description, tags, when_to_use, limitations, example_usage
- **핵심 수치:** NDCG@10 46.21→56.44 (+22%), Recall@10 57.52→67.81 (+18%)
- **절제 연구 결과:** function_description과 tags는 일관되게 도움. when_to_use 도움. **example_usage는 성능을 해침** → 최종 구성에서 제외.
- **41.6%의 도구 문서에 명확한 기능 설명이나 실행 가능한 컨텍스트 가이드가 부족**
- **적용 가능성: 매우 상.** 우리 옵티마이저가 하려는 것과 본질적으로 동일.

#### 3. MCP 의미적 도구 탐색 (Mudunuri et al., 2026)
- **기법:** MCP 도구를 위한 dense embedding 기반 의미 검색
- **핵심 수치:** Hit Rate@3 97.1%, MRR 0.91
- **핵심 발견:** 검색 품질은 **"도구 description의 정보성에 의해 근본적으로 제한된다"** — 설명이 좋으면 완벽에 가까운 검색, 나쁘면 실패.

#### 4. ToolRet (Shi et al., ACL 2025)
- **기법:** 7.6k 태스크, 43k 도구 벤치마크. SOTA IR 모델도 도구 검색에서 실패함을 증명.
- **핵심 발견:** 도구 검색은 **기능적 관련성(functional relevance)** 이해가 필요 — 주제적 유사성(topical similarity)이 아님.

### Dense Retrieval 성능을 개선하는 문서 특성 (영향도 순)

1. **기능적 명확성** (Tool-DE: +13% NDCG@10) — 도구가 무엇을 하는지 간결하게 서술
2. **사용 맥락 / when-to-use** — 사용자 의도와 도구 능력 간의 갭을 연결
3. **구별적 어휘** (MCP 논문: 고유 도메인 용어가 높은 MRR) — 유사 도구와 차별화
4. **태그 / 범주 키워드** (Tool-DE) — 3-5개 도메인 키워드로 추가 검색 앵커
5. **의미적 쿼리 정렬** (doc2query: +47.8% MRR) — 예상 사용자 쿼리와 유사한 언어

**검색을 해치는 특성:**
- **예시 사용법 / 코드 스니펫** (Tool-DE 절제: 제거 시 NDCG@10 개선)
- **키워드 스터핑** (dense retrieval 문헌: 임베딩에 노이즈 추가)
- **과도하게 장황한 설명** (단일 벡터 인코딩의 용량 한계, 정보 희석)

### 시사점

- **예상 쿼리에 맞추어 최적화해야 함** — doc2query 스타일로 "이 도구를 찾을 쿼리" 생성, 이를 최적화 가이드로 사용
- **search_description에 doc2query 확장 적용 가능** — 기존의 dual output (optimized + search) 구조 활용
- **텍스트 최적화가 임베딩 모델보다 ROI 높음** — MCP 논문: "description 정보성이 검색 품질의 근본 한계"

---

## 클러스터 C: GEO 심층 분석

### GEO 원본 논문 핵심 (Aggarwal et al., KDD 2024)

**9가지 전략과 효과:**

| 순위 | 전략 | 위치 조정 단어 수 개선 | 티어 |
|------|------|---------------------|------|
| 1 | **Quotation Addition** | **+41%** | 상 |
| 2 | **Statistics Addition** | **+37%** | 상 |
| 3 | **Cite Sources** | **+30%** | 상 |
| 4 | **Fluency Optimization** | 중간 (+28% 주관) | 중 |
| 5 | **Authoritative Tone** | 8-12% | 중 |
| 6 | **Easy-to-Understand** | 15-30% | 중-하 |
| 7 | **Technical Terms** | 2-5% | 하 |
| 8 | **Unique Words** | 0-2% | 미미 |
| 9 | **Keyword Stuffing** | **-8~-10%** | **유해** |

**최적 조합:** Fluency + Statistics = +5.5% 추가. Cite + Quotation + Statistics = +30-40% 종합.

**가시성(Visibility) 메트릭:** Position-Adjusted Word Count — 인용 빈도 + 위치 가중 (앞쪽 인용 3x 가중).

### GEO 후속 연구

- **"Content is Goliath" (Ma et al., 2025):** 생성 엔진은 **낮은 perplexity(높은 예측 가능성)** 콘텐츠를 선호. perplexity 1 표준편차 감소 → 인용 확률 47%→56%. LLM 기반 "content polishing"이 역설적으로 정보 다양성을 **향상**.
- **CORE (Jin et al., 2026):** 전략적 최적화 콘텐츠 추가로 91.4% @Top-5 승격 성공률.
- **AI 검색 세션 527% 증가** (2025년 상반기 전년 대비)

### 현재 구현의 GEO 적합성 감사

| GEO 전략 | 우리 구현 | 갭 분석 |
|----------|----------|---------|
| Statistics Addition (+37%) | `stats` 차원 (regex) | **부분 일치.** 통계 존재는 확인하지만 관련성/진실성 검증 안 함. Goodhart 위험 낮음 (도구 통계는 검증 가능). |
| Technical Terms (+2-5%) | `precision` 차원 (regex) | **잘 매칭, 하지만 과대 가중.** GEO에서는 2-5% 효과이나, MCP 도구 검색에서는 임베딩 공간 분리에 중요. 도구 검색 연구에 의해 정당화됨. |
| Fluency (+28%) | **측정 안 함** | **핵심 누락.** GEO에서 일관적으로 효과적 + "Content is Goliath"에서 LLM이 낮은 perplexity 선호 확인. 임베딩 품질과 LLM 리랭킹 모두에 영향. |
| Cite Sources (+30%) | 해당 없음 | 도구 description에 외부 인용 부적합. 단, 잘 알려진 API 언급("GitHub REST API v3 사용")은 `precision`에 부분 포함. |
| Unique Words (0-2%) | `disambiguation` 일부? | GEO에서 효과 미미. 우리의 대조 문구 접근이 더 나음. |
| Authoritative Tone (8-12%) | 측정 안 함 | 중요도 낮음. 생성 엔진이 이미 이런 변화에 강건. |
| Easy-to-Understand (15-30%) | 측정 안 함 | Fluency와 중복. 가독성 수준으로 측정 가능하나 낮은 우선순위. |
| Quotation Addition (+41%) | 해당 없음 | 도구 description에 인용구 부적합. |
| Keyword Stuffing (-8~-10%) | 검사 안 함 | **갭: 안티 게이밍 검사 없음.** LLM 재작성이 자연스럽게 회피하지만 명시적 검출 필요. |

### 우리 구현만의 차원 (GEO에 없음)

| 우리 차원 | GEO 대응 | 평가 |
|----------|----------|------|
| **clarity** | Fluency + Easy-to-Understand 부분 중복 | **잘 지지됨.** CallNavi: purpose clarity가 도구 선택 #1 요인. |
| **disambiguation** | 직접 대응 없음 | **개념은 유효, 구현은 문제.** MCP 논문에서 겹치는 description = 열악한 검색 확인. 하지만 regex(대조 문구)는 게이밍 가능. 임베딩 거리로 측정해야 함. |
| **parameter_coverage** | GEO에 없음 | **새롭고 가치 있음.** 웹 콘텐츠에는 파라미터 없음. 도구에서는 LLM 호출 정확도와 구분에 도움. schema 기반 검증 필요. |
| **boundary** | **GEO에 없음** | **GEO 연구에서 지지되지 않는 발명이며 실증적으로 문제.** (1) 임베딩 모델이 부정(negation)을 잘 처리 못함 ("does not handle X"와 "handles X" 임베딩이 유사), (2) 95% 환각률, (3) 검색 성능 개선 증거 없음. **제거 또는 극단적 감소 권장.** |

---

## 클러스터 D: Goodhart's Law 회피

### 핵심 논문

#### 1. 보상 모델 과최적화 확장 법칙 (Gao et al., ICML 2023)
- **핵심 발견:** 프록시 보상 최적화 시 실제(gold) 보상은 **혹 모양 곡선**: 처음 증가, 특정 KL divergence에서 정점, 이후 감소 — 프록시 보상이 계속 증가하는 동안에도. KL 페널티는 프록시-gold 갭을 줄이지 않음, 단지 같은 경계에서 조기 종료 유발.
- **핵심 수치:** 4-5 멤버 앙상블이 과최적화를 30-75% 개선. 앙상블이 BoN에서 과최적화 완전 제거.
- **시사점:** 단일 GEO 점수 최적화 금지. 프록시 포인트(더 이상 최적화가 해로운 지점) 식별 필요.

#### 2. 도구 description 적대적 최적화
- **ToolTweak (2025):** 반복적 LLM 가이드 조작으로 선택률 20%→82% (+62pp). 효과적 조작: 주관적 주장, 암묵적 우월성 프레이밍, 기억에 남는 이름.
- **ToolFlood (2026):** 검색 레이어에 적대적 도구 주입으로 합법적 도구 억제. 1% 주입률로 95% 공격 성공률.
- **시사점:** 선택률 자체는 유효한 최적화 타겟이 아님 — 쉽게 게이밍됨. "자기 홍보 게이트" 필요 (최상급 주장, 경쟁 비교 탐지).

#### 3. 검색 메트릭 직접 최적화
- **핵심 발견:** 아무도 문서 텍스트를 P@1에 대해 end-to-end로 직접 최적화하지 않음. 이유: (1) 파이프라인이 미분 불가, (2) 쿼리 분포에 과적합, (3) 결과 텍스트가 인간에게 비직관적.
- **GEO의 접근:** 전략 기반 최적화(통계, 인용, 명확성) → end-task 메트릭으로 검증. RLHF와 유사: 보상 모델(프록시)로 최적화, 인간 선호(gold)로 검증.

### RLHF 문헌이 가르치는 것

1. **모든 프록시 메트릭에 "프록시 포인트"가 존재** — 그 이후 최적화가 해로움. 우리 GEO 스코어러는 이미 이 지점을 넘음 (ungrounded가 더 높은 GEO + 95% 환각).
2. **KL 페널티(출력을 참조에 가깝게 유지)가 가장 보편적 완화책.** 우리의 grounded 최적화가 바로 이것 — 원본 보존 + schema 기반 + 환각 제거.
3. **보상 해킹은 프록시와 실제 메트릭 간 양의 상관이 있어도 발생** — GEO와 P@1이 다소 상관되어도 GEO 최적화가 P@1을 무한히 개선하지 않음.
4. **앙상블 다양한 신호가 동시 게이밍을 방지** — 4-5개 독립 품질 메트릭 사용 권장.

### 보호 장치 설계

| 보호 장치 | 출처 | 구현 |
|-----------|------|------|
| 환각 게이트 | SEAL, ToolTweak 방어 | input_schema + 원본 대비 비교; 날조된 능력 거부 |
| 정보 보존 게이트 | KL 페널티 유사 | 원본 정보 전부 보존; 의미 유사도 하한 |
| 자기 홍보 탐지 | ToolTweak 적대적 특성 | 최상급 주장, 경쟁 비교, 서수 트릭 탐지 및 거부 |
| 단일 패스 제한 | Gao et al. 프록시 포인트 | 반복 재최적화 금지; 1회 적용 후 검증 |
| 다중 메트릭 평가 | 앙상블 RM, 제약 RLHF | 모든 게이트 통과 필수: 환각=0, 정보보존=true, 검색개선=true |
| P@1 검증 | End-task 메트릭 | 최적화 후 A/B 테스트로 실제 도구 선택 정확도 측정 |

---

> **2026-03-30 업데이트:** 아래 추천안으로 구현된 grounded optimization의 P@1 A/B 결과, δP@1 = -0.069 (검색 성능 저하). 근본원인: retrieval 경로 불일치 + GEO 보상 왜곡. 추가 필요 조치: (1) `search_description`을 retrieval 전용 경로에 연결, (2) GEO를 diagnostic metric으로 격하, (3) disambiguation 재설계. 상세: `docs/analysis/description-optimizer-root-cause-analysis.md`

## 전체 종합 및 추천

### 근거 기반 선택지

| 선택지 | 근거 | 장점 | 단점 | 확신도 |
|--------|------|------|------|--------|
| **A. GEO 휴리스틱 수정** | boundary 제거, fluency 추가 | 빠르고 무료, 기존 코드 수정만 | 여전히 regex = 여전히 게이밍 가능 | 중 |
| **B. RAGAS Faithfulness** | 정확도 0.95, 2 LLM 호출 | 환각 직접 탐지, 비용 효율적 | 품질 진단(어떤 차원이 약한지)은 불가 | 상 |
| **C. 검색 기반 평가 (P@1)** | end-task 직접 측정 | 게이밍 불가, North Star와 동일 | 평가 비용 높음, 쿼리 분포 과적합 위험 | 상 |
| **D. doc2query 확장** | +47.8% MRR, Tool-DE +22% NDCG | 검색에 직접 효과 | description이 길어짐, 인간 가독성 저하 | 중-상 |
| **E. 하이브리드 (B+C+D)** | 각 방법의 장점 결합 | 다층 방어, 게이밍 어려움 | 복잡도 증가, 비용 증가 | **최상** |

### 추천 접근법: **E. 하이브리드 (RAGAS Faithfulness + 검색 기반 + doc2query)**

**구체적 아키텍처:**

```
Phase 1: 진단 (무엇을 개선할지)
  └─ doc2query로 예상 쿼리 생성 → 쿼리 인식 프롬프트 구성
  └─ 약한 차원 식별 (clarity, disambiguation만 — boundary 제거)

Phase 2: 최적화 (LLM 재작성)
  └─ 쿼리 인식 grounded 프롬프트
  └─ input_schema + sibling_tools 기반
  └─ 단일 패스 (반복 최적화 금지)

Phase 3: 검증 (다중 게이트)
  ├─ RAGAS Faithfulness (환각 탐지, 2 LLM 호출)
  ├─ 정보 보존 (기존 게이트 유지)
  ├─ 의미 유사도 (기존 게이트 유지)
  └─ 검색 성능 비회귀 (P@1 비교, 선택적)

Phase 4: 검증 (end-to-end)
  └─ P@1 A/B 테스트 (원본 vs 최적화, 배치 단위)
```

**왜 이 접근법인가:**
1. **RAGAS Faithfulness가 환각 문제를 직접 해결** — regex 대신 주장별 이진 검증. 단, Goodhart 문제의 완전 해결에는 retrieval 경로 정렬(`search_description` 사용)이 추가로 필요.
2. **doc2query가 검색 성능에 직접 기여** — 예상 쿼리에 맞춘 최적화로 의미적 정렬 강화
3. **P@1이 궁극적 검증** — 프록시가 아닌 실제 목표 측정
4. **다중 게이트가 단일 메트릭 게이밍 방지** — RLHF 앙상블 원리 적용
5. **boundary 제거로 가장 큰 환각 원인 제거** — GEO 연구에서 지지되지 않는 차원

### GEO Scorer 구체적 개선안

**제거:**
- `boundary` 차원 → GEO에 없고, 95% 환각률, 임베딩이 부정 처리 못함

**추가:**
- `fluency` 차원 → GEO +28%, "Content is Goliath" LLM 선호 확인
- RAGAS faithfulness 게이트 → 환각 직접 탐지

**수정:**
- `disambiguation` → regex 대조 문구 대신 sibling tools 간 임베딩 거리로 측정
- `parameter_coverage` → input_schema 대비 검증 (기존 hallucination gate 활용)

**유지:**
- `clarity` → CallNavi: 도구 선택 #1 요인
- `stats` → GEO +37%, 앵커 역할
- `precision` → MCP 논문: 기술 용어가 임베딩 공간 분리에 핵심

### 결정 사항 (2026-03-29)

1. **RAGAS Faithfulness 비용 수용** — $0.002/평가 허용
2. **doc2query 쿼리 생성** — Ground truth 불완전하므로 LLM 합성 시 품질 관리 주의. 기존 GT 활용 + 신중한 LLM 합성 병행.
3. **P@1 검증 빈도** — 배치 단위 검증, 최고 성능 방향
4. **boundary 차원 완전 제거** — 코드에서 삭제 (가중치 0이 아님)
5. **fluency 측정** — 최적화-평가 모델 분리 필수 (GPT-4o-mini로 최적화 시 다른 모델로 평가)

### 추가 결정 사항 (2026-03-30, 근본원인 분석 이후)

6. **`search_description`이 retrieval 전용 텍스트** — 평가와 실서비스 모두에서 임베딩 대상은 `search_description`
7. **GEO는 diagnostic metric으로만 사용** — hard gate에서 제외
8. **3-way A/B 평가 전환** — original vs optimized_description vs search_description 비교
9. **disambiguation 재설계** — sibling 이름 나열(contrast phrasing) → target-only qualifier 중심

---

## 참고 문헌

### 클러스터 A
- [FActScore](https://arxiv.org/abs/2305.14251) — Min et al., EMNLP 2023
- [G-Eval](https://arxiv.org/abs/2303.16634) — Liu et al., EMNLP 2023
- [SelfCheckGPT](https://arxiv.org/abs/2303.08896) — Manakul et al., EMNLP 2023
- [LLM-as-Judge](https://arxiv.org/abs/2306.05685) — Zheng et al., NeurIPS 2023
- [RAGAS](https://arxiv.org/abs/2309.15217) — Shahul et al., EACL 2024

### 클러스터 B
- [doc2query](https://arxiv.org/abs/1904.08375) — Nogueira et al., 2019
- [Tool-DE](https://arxiv.org/abs/2510.22670) — Lu et al., 2025
- [MCP Tool Selection](https://arxiv.org/abs/2603.20313) — Mudunuri et al., 2026
- [ToolRet](https://arxiv.org/abs/2503.01763) — Shi et al., ACL 2025
- [ANCE](https://arxiv.org/abs/2007.00808) — Xiong et al., ICLR 2021
- [HyDE](https://arxiv.org/abs/2212.10496) — Gao et al., ACL 2023

### 클러스터 C
- [GEO](https://arxiv.org/abs/2311.09735) — Aggarwal et al., KDD 2024
- [Content is Goliath](https://arxiv.org/abs/2509.14436) — Ma et al., 2025
- [CORE](https://arxiv.org/abs/2602.03608) — Jin et al., 2026

### 클러스터 D
- [Reward Model Overoptimization](https://arxiv.org/abs/2210.10760) — Gao et al., ICML 2023
- [ToolTweak](https://arxiv.org/abs/2510.02554) — 2025
- [ToolFlood](https://arxiv.org/abs/2603.13950) — 2026
- [Goodhart Variants](https://arxiv.org/abs/1803.04585) — Garrabrant, 2017
- [Constrained RLHF](https://arxiv.org/abs/2310.04373) — Moskovitz et al., ICLR 2024
