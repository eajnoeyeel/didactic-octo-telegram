# Description Optimizer — GEO-P@1 불일치 근본원인 분석

> Date: 2026-03-30
> Branch: `feat/description-optimizer`
> Scope: grounded 최적화 이후에도 남아 있는 `GEO improvement != retrieval improvement` 문제 분석

---

## 1. 결론 요약

이번 문제의 핵심은 `GEO`라는 이름 자체가 아니라, **현재 GEO 최적화 방식과 실제 retrieval 경로가 서로 다른 방향을 보고 있다**는 점이다.

확인된 우선순위는 다음과 같다.

1. **평가/검색 경로 불일치**
   - 아키텍처와 프롬프트는 `search_description`을 retrieval 전용 텍스트로 전제하지만,
     실제 P@1 A/B 평가는 `optimized_description`을 임베딩한다.
   - 검색 경로도 기본적으로 `tool.description`만 임베딩한다.
2. **GEO 휴리스틱의 보상 왜곡**
   - 현재 휴리스틱은 길이 증가, fluency 신호, contrast phrasing 같은 패턴을 보상한다.
   - 이 패턴은 사람에게는 “설명이 풍부해졌다”로 보일 수 있지만, dense retrieval에는 노이즈가 된다.
3. **Disambiguation의 retrieval 오염**
   - sibling tool과의 차이를 설명한다는 명목으로 다른 연산/도구 이름을 문장 안에 집어넣는다.
   - 그 결과 target과 sibling 사이 의미 경계가 흐려지고 confusion이 증가한다.
4. **Gate의 역할 한계**
   - 현재 gate는 safety 검증에는 유효하지만 retrieval regression을 막지 못한다.
   - 즉 “사실은 맞지만 검색에는 불리한 설명”이 통과할 수 있다.

따라서 문제는 “GEO가 항상 틀렸다”가 아니라, **현재 브랜치의 GEO 중심 보상 함수가 search objective와 맞지 않는다**는 것이다.

---

## 2. 관찰된 사실

### 2.1 최종 retrieval 결과

`data/verification/retrieval_ab_report.json` 기준:

- Original `P@1 = 0.5417`
- Optimized `P@1 = 0.4722`
- Delta `P@1 = -0.0694`
- Original `MRR = 0.6372`
- Optimized `MRR = 0.5769`
- Tool-level 결과: `1 improved / 3 degraded / 32 same`

즉, grounded 최적화가 환각은 줄였지만 **실제 tool selection accuracy는 떨어졌다**.

### 2.2 성공 건 길이 팽창

`data/verification/gt_optimized_descriptions.jsonl`의 `status=success` 18건 기준:

- 원본 평균 길이: `15.06 words`
- `optimized_description` 평균 길이: `94.06 words`
- `search_description` 평균 길이: `22.78 words`

현재 acceptance를 통과한 텍스트는 대체로 “조금 더 좋아진 설명”이 아니라 **원문보다 훨씬 길어진 새로운 문단**에 가깝다.

### 2.3 탐색적 상관 신호

성공 건 18개만 놓고 본 탐색 결과:

- `geo_delta` vs `P@1 delta`: `Pearson ≈ -0.468`
- `geo_delta` vs `MRR delta`: `Pearson ≈ -0.432`
- `search_description length delta` vs `P@1 delta`: `Pearson ≈ -0.505`

표본 수가 작기 때문에 통계적 주장으로 쓰기에는 이르지만, 방향성은 명확하다.
**지금 구현에서는 GEO가 오를수록 retrieval이 좋아진다는 근거가 없고, 오히려 반대로 움직인다.**

---

## 3. 1순위 원인: 평가/검색 경로 불일치

이 문제는 단순한 가설이 아니라 코드 레벨에서 확인된다.

### 3.1 `search_description`은 생성되지만 평가에 쓰이지 않는다

`src/description_optimizer/models.py`와 `src/description_optimizer/optimizer/prompts.py`는
`search_description`을 “embedding-based vector search”용 텍스트로 명시한다.

그러나 `scripts/run_retrieval_ab_eval.py`의 `load_optimized()`는 `optimized_description`만 로드한다.

즉 현재 P@1 A/B는 사실상 아래 질문을 하고 있다.

> “사람용으로 길게 다시 쓴 설명을 그대로 임베딩했을 때 search가 좋아지는가?”

반대로 실제 의도였던 질문은 아래여야 한다.

> “retrieval 전용으로 분리된 `search_description`을 임베딩했을 때 search가 좋아지는가?”

### 3.2 메인 retrieval 경로도 `search_description`을 쓰지 않는다

`src/retrieval/qdrant_store.py`의 `build_tool_text()`는 `tool_name + description`만 임베딩 텍스트로 사용한다.
`MCPTool`에도 retrieval 전용 텍스트 필드가 없다.

즉 현재 구조에서는 `search_description`이 있어도 **실험과 실서비스 모두에서 주 경로에 연결되지 않는다**.

### 3.3 의미

이 불일치 하나만으로도 “GEO는 좋아졌지만 P@1은 하락” 현상이 설명된다.
현재 시스템은 retrieval용 산출물을 만들고도, **실제 검색에서는 다른 산출물을 평가하고 있기 때문**이다.

---

## 4. 2순위 원인: GEO 휴리스틱이 retrieval에 불리한 패턴을 보상함

`src/description_optimizer/analyzer/heuristic.py`는 다음 신호에 높은 점수를 준다.

- 길이 증가
- 문장 수 증가
- connector/transition words
- contrast phrases
- qualifier words

이 신호는 “설명이 풍부해 보인다”는 휴리스틱에는 맞지만, dense retrieval에는 다음 부작용이 있다.

1. query와 직접 관련 없는 토큰이 늘어난다
2. 핵심 action/object 신호가 희석된다
3. sibling 또는 대안 연산 이름이 섞이면서 분리도가 낮아진다

특히 현재 prompt는 `optimized_description`을 50-200 words로 유도한다.
원문 평균 15단어인 도구 설명에 이 목표를 적용하면, **대부분의 최적화는 구조적으로 길이 팽창을 수반할 수밖에 없다.**

---

## 5. 3순위 원인: Disambiguation이 “분리”가 아니라 “오염”으로 구현됨

현재 grounded prompt는 sibling tools를 context로 넣고, heuristic analyzer는 contrast phrasing을 reward한다.
이 조합은 retrieval 관점에서 좋지 않은 텍스트를 만들기 쉽다.

탐색 결과, 성공 건 18개 중 16개 `optimized_description`에 아래 류의 문구가 들어갔다.

- `unlike ...`
- `specifically designed ...`
- `focuses solely on ...`

이런 문구는 문장 품질 지표에는 점수를 주지만, retrieval 관점에서는 아래 두 문제가 있다.

1. target을 설명하면서 sibling/distractor의 어휘를 함께 넣는다
2. “무엇이 아닌가”를 길게 설명하느라 “무엇인가”의 밀도가 낮아진다

### 5.1 degraded 사례 1: `math-mcp::median`

- 원문: `Calculates the median of a list of numbers`
- 최적화 후: mean, mode, addition, subtraction, division 등 다른 연산과의 비교가 길게 포함됨
- 결과: GEO는 `0.10 -> 0.458`로 상승했지만 `P@1`은 `1.0 -> 0.0`

이 케이스에서 실패한 이유는 median을 더 잘 설명해서가 아니라,
**median 설명 안에 다른 수학 연산의 어휘를 너무 많이 넣었기 때문**이다.

### 5.2 degraded 사례 2: `math-mcp::round`

- 원문: `Rounds a number to the nearest integer`
- 최적화 후: addition, subtraction, multiplication, division과의 차이를 설명하는 긴 문단으로 확장
- 결과: GEO는 `0.05 -> 0.375`로 상승했지만 `P@1`은 `1.0 -> 0.0`

사용자 query는 “nearest integer”라는 강한 의도를 갖고 있는데,
최적화 텍스트는 그 신호를 강화하기보다 **산술 연산 일반론**으로 확장됐다.

### 5.3 degraded 사례 3: `instagram::INSTAGRAM_GET_USER_MEDIA`

- 원문: `Get Instagram user's media (posts, photos, videos).`
- 최적화 후: pagination, limit, graph version, create/post 계열 sibling과의 대비 설명이 추가됨
- 결과: GEO는 `0.117 -> 0.442`로 상승했지만 `P@1`은 `1.0 -> 0.0`

이 케이스는 수학 도구와 달리 sibling 이름이 직접 들어가며,
`GET` 계열 tool이 `CREATE/POST` 계열 어휘와 섞이는 문제를 보여준다.

---

## 6. 4순위 원인: Gate는 safety용이지 retrieval용이 아님

현재 gate는 다음을 검사한다.

- semantic similarity
- hallucinated params
- info preservation
- faithfulness

이 검사는 모두 중요하다. 하지만 retrieval regression을 막는 데는 충분하지 않다.

예를 들어 아래 텍스트는 모두 통과할 수 있다.

- 사실은 맞음
- schema도 지킴
- 원문 의미도 대체로 유지함
- 그러나 query와 무관한 비교 문구가 길게 늘어남

즉 gate는 “틀린 설명”은 막아도, **“맞지만 검색에는 불리한 설명”은 막지 못한다.**

---

## 7. 무엇이 근본 원인이고, 무엇이 증상인가

### 근본 원인

- retrieval 전용 산출물과 실제 retrieval 경로가 분리되어 있음
- GEO 휴리스틱이 retrieval objective와 다른 패턴을 보상함

### 증상

- 길이 팽창
- sibling 이름 오염
- contrast phrasing 남용
- GEO 상승과 P@1 하락의 동시 발생

즉 “설명이 길어졌다” 자체가 1차 원인은 아니다.
길이 팽창은 **잘못된 보상 함수와 잘못된 임베딩 대상 선택이 낳은 결과**다.

---

## 8. 대응 방향

이 분석이 지지하는 대응 방향은 아래와 같다.

1. retrieval은 `search_description`을 기준으로 재정렬한다
2. `optimized_description`은 사람용 설명으로 역할을 분리한다
3. GEO는 diagnostic metric으로만 남기고 hard gate에서 제외한다
4. disambiguation은 sibling 이름 나열이 아니라 target-only qualifier 중심으로 재설계한다
5. evaluation은 `original vs optimized_description vs search_description` 3-way 비교로 바꾼다

---

## 9. 문서 정비에 주는 함의

이 분석을 기준으로 문서도 아래 원칙을 따라야 한다.

- “optimized description이 곧 retrieval text”라는 전제를 제거
- “boundary 제거로 Goodhart 해결” 같은 과거 결론은 superseded 처리
- `search_description`을 retrieval 전용 출력으로 명시
- GEO는 primary success metric이 아니라 diagnostic metric으로 위치 조정

즉, 문서 수정은 부수 작업이 아니라 **근본원인 분석의 직접적인 결과물**이다.
