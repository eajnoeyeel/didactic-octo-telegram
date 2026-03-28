# Description Optimizer 근본원인 분석 및 개선 계획

> **Date:** 2026-03-29
> **Branch:** `feat/description-optimizer`
> **Status:** 비교 검증 완료, 근본적 문제 발견

---

## 1. 실험 결과 요약

| 지표 | 값 | 평가 |
|------|-----|------|
| 샘플 크기 | 30 tools | 적정 |
| 성공률 | 22/30 (73%) | 수치상 양호 |
| 평균 GEO 개선 | +0.1792 | **수치는 양이나 실질 개선 미미** |
| Gate Rejected | 8/30 (27%) | Gate는 정상 작동 |
| stats 차원 | -0.0523 (하락) | 최적화가 오히려 기존 정보 파괴 |
| precision 차원 | +0.0227 (무의미) | 사실상 노이즈 |

---

## 2. 핵심 문제: Goodhart's Law (순환 검증)

> "When a measure becomes a target, it ceases to be a good measure."

### 문제의 구조

```
HeuristicAnalyzer (regex 패턴으로 점수 산출)
     ↓ "이 차원이 약함" 피드백
LLM Optimizer (약한 차원에 맞는 문구 삽입)
     ↓ 최적화된 설명
HeuristicAnalyzer (같은 regex로 재측정)
     ↓ "점수 올랐음!" ← 순환 검증
```

**동일한 휴리스틱이 "무엇을 개선할지"도 정의하고, "개선되었는지"도 판단한다.**
LLM은 실제 품질이 아니라 regex 패턴 매칭을 최적화하게 된다.

---

## 3. 차원별 상세 원인 분석

### 3.1 Disambiguation (+0.4182) — 가짜 개선

**현상:** 91%의 성공 건에서 "개선"
**실제:** LLM이 `"Unlike other tools..."`, `"specifically for..."` 같은 템플릿 문구를 삽입

```
# 실제 최적화 결과 예시
Original: "Deletes a specific comment from a file in Slack"
Optimized: "...Unlike other tools that may only retrieve messages,
            this tool specifically modifies the labeling..."
```

**문제:** "Unlike other tools"는 어떤 다른 tool과 비교하는지 명시하지 않음.
Regex(`unlike|in contrast|as opposed to`)만 매칭하면 0.3점 획득.
LLM이 **의미 있는 구분** 대신 **패턴 매칭 문구**를 삽입.

### 3.2 Boundary (+0.3864) — 환각(Hallucination)

**현상:** 95%의 성공 건에서 "개선"
**실제:** LLM이 실제 도구의 제한사항을 모른 채로 제한사항을 날조

```
# 환각 사례 1: slack::SLACK_DELETE_A_COMMENT_ON_A_FILE
Added: "It does not handle comments on channels or direct messages."
→ 원본에 없는 제한사항. 사실 여부 불명.

# 환각 사례 2: aryankeluskar/polymarket-mcp::get_trades
Added: "does not handle trades from other markets"
→ 원본에 없는 제한사항 날조.

# 환각 사례 3: gmail::GMAIL_ADD_LABEL_TO_EMAIL
Added: "does not support batch processing of messages or the creation of new labels"
→ 실제 API가 batch를 지원하는지 LLM은 알 수 없음.
```

**근본 원인:** 프롬프트의 boundary 가이드라인이 날조를 유도:
> `"Add explicit limitations: 'Does NOT handle X', 'Cannot Y', 'Not suitable for Z'"`

LLM에게 도구의 실제 API 스펙(input_schema 등)을 제공하지 않으므로, 그럴듯한 제한사항을 **창작**할 수밖에 없음.

### 3.3 Parameter Coverage (+0.2386) — 환각

**현상:** 73%의 성공 건에서 "개선"
**실제:** LLM이 파라미터를 날조하는 반복 패턴 존재

```
# 반복되는 날조 패턴:
"Accepts a required `query` string parameter and an optional `limit` integer."
→ 이 문구가 실제 파라미터와 무관하게 여러 tool에 반복 삽입됨
```

**근본 원인:** 프롬프트에 `input_schema`를 제공하지 않음.
LLM에게 "파라미터를 언급하라"고 하면서 파라미터 정보를 주지 않으면, 날조 외에 방법이 없음.

### 3.4 Clarity (+0.0614) — 미미한 개선, 일부 퇴행

**현상:** 50%만 개선됨 (나머지 50%는 동일하거나 하락)
**실제:** 이미 명확한 설명(clarity 0.85)이 최적화 후 오히려 하락(0.60)하는 사례 다수

```
# github::create_or_update_file
Clarity: 0.85 → 0.60 (하락)
→ 원본의 구조화된 설명이 장황한 산문체로 대체됨
```

**근본 원인:** 전체 재작성(full rewrite) 방식이 기존의 좋은 구조를 파괴.

### 3.5 Stats (-0.0523) — 퇴행

**현상:** 0%가 개선됨 (전부 동일하거나 하락)
**실제:** 원본에 있던 구체적 수치(`81 fields per stock`, `OWASP Top 10`, `100 results`)가 재작성 과정에서 소실

```
# pi3ch/secdim::get_vulnerable_practice_labs
Stats: 0.80 → 0.10 (대폭 하락)
→ 원본의 "Args:" 섹션과 구체적 수치가 삭제됨
```

**근본 원인:** LLM이 "약한 차원 개선"에 집중하면서, 기존에 강한 정보를 보존하지 못함.

### 3.6 Precision (+0.0227) — 사실상 무변화

**현상:** 32%만 개선됨
**실제:** 기술 용어(SQL, REST, JSON 등)는 원본에 없으면 LLM이 추가할 수 없음 (환각 없이는)

**이것은 정상:** 원본에 없는 기술적 세부사항은 추가할 수 없어야 한다.

---

## 4. LLM 프롬프트 문제

### 4.1 환각 유도 가이드라인

현재 `prompts.py`의 차원별 가이드라인:

```python
"boundary": "Add explicit limitations: 'Does NOT handle X', 'Cannot Y', 'Not suitable for Z'."
"parameter_coverage": "Mention key input parameters with types or constraints."
"disambiguation": "State what this tool does NOT do vs. similar tools."
```

이 3개 차원의 가이드라인이 **도구에 대한 사실적 정보 없이 사실적 주장을 하라**고 요구.

### 4.2 정보 비대칭

| LLM이 아는 것 | LLM이 모르는 것 |
|---|---|
| 원본 description 텍스트 | 실제 input_schema |
| GEO 약한 차원 목록 | 실제 API 동작 |
| 차원별 개선 힌트 | 실제 제한사항 |
| | 실제 파라미터 이름/타입 |
| | 유사 도구와의 실제 차이점 |

### 4.3 전체 재작성 vs 증강(Augmentation)

현재: description 전체를 다시 씀 → 기존의 좋은 부분까지 손실
필요: 원본을 보존하고, 사실에 기반한 정보만 추가

---

## 5. Quality Gate의 한계

Quality Gate는 2가지를 검증:
1. **GEO 비회귀** — 점수가 떨어지지 않았는지 ← 점수 자체가 문제이므로 무의미
2. **의미 유사도** (cosine >= 0.75) — 환각 탐지 불가

```
환각된 boundary 문장: "Does not support batch processing"
→ 원본과 의미적으로 관련 있음 (같은 도메인)
→ cosine similarity = 0.82 → Gate PASS
→ 하지만 사실이 아닌 정보가 포함됨
```

**Gate가 잡아내는 것:** 완전히 다른 주제로 벗어난 경우
**Gate가 잡지 못하는 것:** 같은 도메인 내에서의 사실 날조

---

## 6. 개선 계획

### Phase A: 정보 기반(Grounded) 최적화 (핵심)

**목표:** LLM이 날조 대신 실제 데이터에 기반하여 최적화하도록 전환

#### A-1. input_schema를 프롬프트에 포함

```python
# 현재
prompt = f"Improve this description: {original_description}"

# 개선
prompt = f"""Improve this description:
Description: {original_description}
Input Schema: {json.dumps(input_schema, indent=2)}

Rules:
- Parameter names and types MUST match the input_schema exactly
- Do NOT add parameters not in the schema
- Do NOT add limitations not inferable from the description
"""
```

**효과:** parameter_coverage가 사실에 기반하게 됨. 날조 제거.

**구현:**
- `MCPTool.input_schema`는 이미 모델에 존재 (`models.py:line 69`)
- `servers.jsonl`에 `input_schema` 포함 여부 확인 필요
- `OptimizationPipeline.run()`에 `input_schema` 파라미터 추가
- `LLMDescriptionOptimizer.optimize()`에 schema 전달

#### A-2. Boundary 가이드라인 제거 또는 제한

```python
# 현재 (환각 유도)
"boundary": "Add explicit limitations: 'Does NOT handle X', 'Cannot Y'"

# 개선 옵션 1: 제거
# boundary 점수는 input_schema의 제약조건에서만 추론

# 개선 옵션 2: 제한
"boundary": "Only state limitations that are explicitly mentioned in or
             directly inferable from the original description.
             Do NOT invent limitations."
```

#### A-3. Disambiguation을 도구 간 비교로 전환

현재: "Unlike other tools..." (어떤 도구인지 모름)
개선: 같은 서버 내 유사 도구 목록을 제공하여 실제 구분점 작성

```python
# 같은 서버의 다른 도구 이름 + 설명을 context로 제공
sibling_tools = [t for t in server.tools if t.tool_id != target_tool.tool_id]
prompt += f"\nOther tools on this server:\n"
for t in sibling_tools[:5]:
    prompt += f"- {t.tool_name}: {t.description[:100]}\n"
prompt += "\nExplain how this tool differs from the above."
```

### Phase B: 증강(Augmentation) 방식으로 전환

**목표:** 전체 재작성 대신, 원본 보존 + 정보 추가 방식

#### B-1. Append 방식

```python
# 현재: 전체 재작성
optimized = llm_rewrite(original)

# 개선: 원본 보존 + 추가 정보 삽입
additions = llm_generate_additions(original, input_schema, sibling_tools)
optimized = original + "\n\n" + additions
```

**효과:**
- clarity, stats, precision 퇴행 방지 (원본 보존)
- 좋은 원본 설명이 파괴되지 않음

#### B-2. 선택적 최적화 (약한 차원만)

```python
# GEO >= 0.5인 차원은 건드리지 않음
weak_dims = [d for d in report.dimension_scores if d.score < 0.5]
if not weak_dims:
    return original  # 이미 충분히 좋음

# 약한 차원에 대해서만 추가 정보 생성
prompt = f"The following aspects need improvement: {weak_dims}\n"
prompt += "Add ONLY information addressing these weaknesses. Do NOT rewrite existing text."
```

### Phase C: 평가 체계 개선

**목표:** 순환 검증 탈피 — 독립적인 평가 기준 수립

#### C-1. LLM-as-Judge 평가 (독립 평가자)

HeuristicAnalyzer와 **별개의** LLM 기반 평가를 추가:

```python
class LLMJudge:
    """최적화 결과를 독립적으로 평가하는 LLM 판사."""

    async def evaluate(self, original: str, optimized: str, input_schema: dict) -> JudgeReport:
        prompt = f"""
        Compare the original and optimized MCP tool descriptions.

        Original: {original}
        Optimized: {optimized}
        Actual input schema: {json.dumps(input_schema)}

        Evaluate on:
        1. Factual accuracy: Does optimized contain only true information? (0-1)
        2. Hallucination check: Are there claims not supported by original or schema? (list them)
        3. Clarity comparison: Which is clearer for an LLM selecting tools? (original/optimized/tie)
        4. Information preservation: What information from original was lost? (list)
        5. Overall: Is the optimized version genuinely better? (yes/no/mixed)
        """
```

**효과:** 환각 탐지 가능. 사실 정확성 검증 가능.

#### C-2. Tool Selection 기반 평가 (end-to-end)

최종적으로 가장 의미 있는 평가는 **실제 도구 선택 정확도**:

```python
async def tool_selection_eval(query: str, tool_pool: list[MCPTool], ground_truth: str):
    """원본 설명 vs 최적화 설명으로 도구 선택 정확도 비교."""

    # 1. 원본 설명으로 검색
    results_original = await pipeline.search(query, tools_with_original_desc)

    # 2. 최적화 설명으로 검색
    results_optimized = await pipeline.search(query, tools_with_optimized_desc)

    # 3. Precision@1 비교
    p1_original = results_original[0].tool_id == ground_truth
    p1_optimized = results_optimized[0].tool_id == ground_truth
```

**이것이 North Star 메트릭과 직결되는 진정한 검증.**
"최적화된 설명이 실제로 도구 선택 정확도를 높이는가?"

#### C-3. Heuristic Analyzer 가중치 재조정

현재: 6차원 동일 가중치 (각 1/6)
문제: boundary +0.6 (환각)이 clarity -0.3 (실제 품질 하락)을 상쇄

```python
# 개선안: 신뢰도 기반 가중치
DIMENSION_WEIGHTS = {
    "clarity": 0.25,         # 가장 중요 (LLM이 읽는 핵심)
    "precision": 0.20,       # 기술적 정확성
    "parameter_coverage": 0.20,  # input_schema 기반일 때만 의미 있음
    "disambiguation": 0.15,  # 실제 비교일 때만 의미 있음
    "boundary": 0.10,        # 사실 기반일 때만 의미 있음
    "stats": 0.10,           # 있으면 좋지만 필수 아님
}
```

### Phase D: Quality Gate 강화

#### D-1. 환각 탐지 Gate 추가

```python
class HallucinationGate:
    """input_schema와 비교하여 파라미터 환각 탐지."""

    def check(self, optimized: str, input_schema: dict) -> GateResult:
        # 최적화된 설명에서 언급한 파라미터 추출
        mentioned_params = extract_param_names(optimized)
        # 실제 스키마의 파라미터와 비교
        actual_params = set(input_schema.get("properties", {}).keys())
        hallucinated = mentioned_params - actual_params
        if hallucinated:
            return GateResult(passed=False, reason=f"Hallucinated params: {hallucinated}")
```

#### D-2. 정보 보존 Gate 추가

```python
class InformationPreservationGate:
    """원본의 핵심 정보가 최적화본에 보존되었는지 검증."""

    def check(self, original: str, optimized: str) -> GateResult:
        # 원본의 숫자/단위 보존 확인
        original_numbers = extract_numbers_with_context(original)
        optimized_text = optimized.lower()
        lost_info = [n for n in original_numbers if n not in optimized_text]
        # 원본의 기술 용어 보존 확인
        original_terms = extract_tech_terms(original)
        lost_terms = [t for t in original_terms if t.lower() not in optimized_text]
```

---

## 7. 구현 우선순위

| 순위 | 작업 | 효과 | 난이도 | 예상 소요 |
|------|------|------|--------|----------|
| **1** | A-1: input_schema 프롬프트 포함 | 환각 대폭 감소 | 중 | 1 session |
| **2** | A-2: Boundary 가이드라인 제한 | 환각 감소 | 하 | 0.5 session |
| **3** | B-1: Append 방식 전환 | 퇴행 방지 | 중 | 1 session |
| **4** | A-3: Sibling tools context | 실제 disambiguation | 중 | 1 session |
| **5** | C-1: LLM-as-Judge | 독립 평가 | 상 | 2 sessions |
| **6** | D-1: Hallucination Gate | 자동 환각 탐지 | 중 | 1 session |
| **7** | C-2: Tool Selection Eval | 진정한 end-to-end 검증 | 상 | 2 sessions |
| **8** | C-3: 가중치 재조정 | 점수 신뢰도 향상 | 하 | 0.5 session |

### 권장 실행 순서

```
Phase 1 (즉시): A-1 + A-2 + B-1 → 환각 제거 + 퇴행 방지
Phase 2 (다음): A-3 + D-1 → 실제 정보 기반 개선
Phase 3 (이후): C-1 + C-2 → 독립적 평가 체계 구축
```

---

## 8. 결론

**현재 Description Optimizer의 GEO 점수 +0.1792 상승은 실질적 품질 개선이 아니다.**

근본 원인은:
1. **순환 검증** (같은 휴리스틱이 타겟이자 평가자)
2. **정보 비대칭** (LLM에게 실제 도구 스펙을 제공하지 않음)
3. **환각 유도 프롬프트** (사실 없이 사실적 주장을 요구)
4. **전체 재작성** (기존 좋은 정보 파괴)

개선의 핵심은 **"LLM이 아는 것만 쓰게 하기"**:
- input_schema 제공 → 파라미터 환각 제거
- boundary 제한 → 제한사항 환각 제거
- sibling tools 제공 → 실제 disambiguation
- append 방식 → 기존 정보 보존
- 독립 평가 → 순환 검증 탈피
