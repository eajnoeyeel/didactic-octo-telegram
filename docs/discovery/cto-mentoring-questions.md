# CTO 멘토링 질문 목록
> 브레인스토밍 + 평가 설계 세션에서 발생한 미결 질문들 (2026-03-17 작성, 2026-03-20 업데이트)
> 멘토링: 매주 화요일, 2026-03-25 첫 세션
> 형식: "제 방향이 이렇습니다 — 옳은가요?"
> 참고: 평가 지표 상세 → `docs/evaluation/metrics-rubric.md`

---

## 아키텍처 결정

### 1. 검색 전략: 세 방법 모두 구현해서 비교 실험한다

**배경**:
LLM에게 적합한 MCP Tool을 추천하려면 수천 개 Tool 중 관련 후보를 먼저 추려야 한다. 이 과정의 방법론으로 세 가지를 검토했다.

- **Dense Vector 검색**: 쿼리와 Tool description을 임베딩 벡터로 변환해 코사인 유사도로 찾는 방식. RAG-MCP 논문에서 Tool 선택 정확도를 43%까지 끌어올렸다(기존 13%). 의미적 유사성에 강하지만 "search_papers" 같은 정확한 함수명 매칭은 약할 수 있다.
- **Hybrid (Dense + BM25 + RRF)**: 의미 검색과 키워드 검색을 합산. 두 약점을 상호 보완한다.
- **Taxonomy-gated (JSPLIT 방식)**: 쿼리 의도를 카테고리로 먼저 분류하고 해당 카테고리 내에서만 검색. 정밀도가 높지만 카테고리 경계가 모호한 쿼리에서 취약할 수 있다.

**내 방향**: 세 방법을 모두 구현하되, 공통 `PipelineStrategy` 인터페이스를 통해 교체 가능하게 설계한다. 동일한 평가 하네스로 비교 실험 후 결정한다. 현재 규모(~1,000 tools)에서는 Hybrid가 Dense 대비 키워드 매칭에서 우위를 보일 것으로 예상한다.

**확인하고 싶은 것**: 이 비교 실험 방향이 맞는지, 그리고 Taxonomy-gated를 이 규모에서 구현할 가치가 있는지.

---

### 2. Reranker: Cross-Encoder를 기본으로, Confidence 낮을 때만 LLM fallback

**배경**:
검색으로 Top-10 후보를 추린 뒤 최종 선택하는 Reranker가 필요하다. 후보:
- **Cross-Encoder**: 쿼리와 Tool을 쌍으로 묶어 점수화하는 경량 모델. API 비용 없고 빠르다.
- **LLM-as-Judge**: 대형 언어 모델에게 직접 판단 요청. 정확도 높지만 비용과 latency 증가. 추천 시스템이 LLM에 의존하는 순환 구조가 생긴다.
- **Hybrid**: Cross-Encoder 먼저, Confidence 낮을 때만 LLM fallback.

**내 방향**: Cross-Encoder를 기본으로 쓰고, Confidence가 낮은 케이스(1위와 2위 점수 차이가 작은 경우)에만 LLM fallback을 적용한다. Confidence proxy로는 raw score가 아니라 1위-2위 점수 gap을 사용한다(별도 calibration 없이 동적 분기 가능).

**확인하고 싶은 것**: 이 Hybrid Reranker 설계가 5주 프로젝트에서 현실적인지, Cross-Encoder만으로 충분한 경우가 많은지.

---

## 평가 방법론

### 3. Ground Truth: LLM 자동 생성 + 수동 seed set 검증

**배경**:
검색 전략 비교와 description 품질 실험을 하려면 "(쿼리, 정답 서버, 정답 Tool)" 트리플이 필요하다. 수동 작성은 시간이 너무 걸리고, LLM 자동 생성만으로는 품질이 불안하다("Quality Matters" 논문 arxiv 2409.16341).

**내 방향**: 각 Tool description에서 LLM으로 쿼리를 10개씩 자동 생성하되, 처음 50~100개는 직접 검수해서 생성 품질 기준을 잡는다. 이후 자동 생성 쿼리가 그 기준을 충족하는지 검증 단계를 넣는다. 완전 자동화를 신뢰하기보다 "검수된 seed set"을 품질 기준점으로 유지한다.

**확인하고 싶은 것**: 이 방향이 현실적인지, 수동 검수 규모의 최소 기준이 있는지.

---

### 4. 평가 지표: 11개 지표 + Evidence Triangulation 체계

**배경**:
4/26 제출까지 끌어올릴 수 있는 극한의 완성도를 목표로 한다. 초기 6개 베이스라인에서 논문 리서치를 거쳐 11개 지표 체계로 확장했다.

**내 방향 (11개 지표, 3계층 구조)**:
- **North Star**: Precision@1 (최종 추천 정확도)
- **Input Metrics (4)**: Server Recall@K, Tool Recall@10, Confusion Rate, Description Quality Score
- **Health Metrics (3)**: ECE (Confidence Calibration), Latency p50/p95/p99, Server Classification Error Rate
- **Evidence Triangulation (핵심 테제 증명)**:
  - **8a. A/B Lift** (Causal): 자체 MCP 서버의 Poor vs Good description → Selection Rate 차이. 인과 관계 직접 증명.
  - **8b. Spearman r** (Correlational): Pool 전체 Tool의 quality_score vs selection_rate 상관. 일반화 가능성 증명.
  - **8c. Regression R²** (Explanatory): 어떤 quality 요소(specificity, disambiguation 등)가 가장 중요한지 분해.
- **Secondary**: NDCG@5, MRR, Pass Rate (자체 MCP 서버 한정)

"description을 잘 쓰면 더 많이 선택된다"는 주장을 단순 상관이 아닌 **인과적 + 상관적 + 설명적** 3중 증거로 입증하는 것이 목표.

**확인하고 싶은 것**: 이 지표 체계와 evidence triangulation 접근이 5주 프로젝트에서 현실적인지, CTO 관점에서 이 정도의 엄밀함이 어떻게 평가되는지.

---

### 5. Position Bias: 평가 시 입력 순서 랜덤화로 통제

**배경**:
LLM에게 Tool 목록을 보여줄 때 첫 번째나 마지막 항목을 더 잘 선택하는 Position Bias가 알려진 문제다. Reranker가 2위로 정렬한 Tool을 LLM이 단순히 위치 때문에 선택할 수 있다.

**내 방향**: 평가 시 Reranker가 내놓은 Top-K 목록을 매 쿼리마다 랜덤으로 섞어서 위치 효과를 평균화한다. 이를 통해 실제 추천 품질만 측정되게 한다.

**확인하고 싶은 것**: 이 통제 방법이 충분한지, Cross-Encoder 방식에서도 이 bias가 유의미하게 나타나는지.

---

## 구현 세부사항 (방향 검증)

### 6. Confidence 분기: 1위-2위 점수 gap을 proxy로 사용

**배경**:
동적 Confidence 분기(확신 높으면 Top-1 반환, 낮으면 Top-3 + 힌트)를 구현하려면 신뢰할 수 있는 Confidence 수치가 필요하다. Cross-Encoder의 raw score를 그대로 확률로 쓰면 "0.95점이지만 실제 정확도는 70%"인 mis-calibration 문제가 생긴다(점수 척도와 실제 확률 척도가 다를 수 있음).

**내 방향**: 별도 calibration 모델 없이, 1위 점수와 2위 점수의 **차이(gap)**를 Confidence proxy로 사용한다. Gap이 크면 "분명히 1위가 맞다"는 의미이므로 Top-1 반환, Gap이 작으면 "비슷비슷하다"는 의미이므로 Top-3 + disambiguation 반환. 이 방식은 구현이 단순하고 직관적으로 설명 가능하다.

**확인하고 싶은 것**: 이 gap 기반 Confidence 방식이 실제로 잘 작동하는지, 더 좋은 단순한 대안이 있는지.

---

### 7. 평가 자동화: 커스텀 하네스 직접 작성

**배경**:
세 가지 검색 전략 비교, description 품질별 정확도 측정, Confusion Matrix 분석을 자동으로 돌리는 평가 파이프라인이 필요하다. RAGAS(Es et al., EACL 2024) 같은 기존 RAG 평가 프레임워크가 있지만, 이 프로젝트의 2-Layer 구조(서버 → Tool), Confusion Matrix, Provider Analytics는 커스텀 지표라 그대로 쓰기 어렵다.

**내 방향**: `evaluate(strategy, test_queries, ground_truth) → metrics` 형태의 단순한 Python 하네스를 직접 작성한다. `Evaluator` 추상 클래스를 두어 지표를 플러그인처럼 추가할 수 있게 설계한다. RAGAS는 참고용으로 쓰되, 핵심 지표는 직접 구현한다.

**확인하고 싶은 것**: 이 접근이 맞는지, 직접 구현 시 미리 고려해야 할 함정이 있는지.
