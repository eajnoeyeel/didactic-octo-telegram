# Description Optimizer — MCP-Zero Retrieval Validation

> Date: 2026-03-30
> Branch: `feat/description-optimizer`
> Scope: retrieval-aligned refactor 이후 `data/raw/mcp_zero_servers.jsonl` 기준 오프라인 검증

---

## 1. 검증 목적

`retrieval_description`을 canonical embedding text로 전환한 뒤, 실제 MCP-Zero tool pool에서 retrieval 품질이 개선되는지 확인한다.

이번 문서는 다음 질문에 답한다.

1. `mcp_zero` 풀에서 description optimizer가 실제로 `Recall@10`, `MRR`, `P@1`을 올리는가?
2. 개선이 일부 tool에 국한되는가, 아니면 전체적으로 확산되는가?
3. 현재 bottleneck은 description 품질인가, gate 통과율인가?

---

## 2. 평가 셋 구성

`data/raw/mcp_zero_servers.jsonl`은 tool pool이지만 정답 라벨을 포함하지 않으므로, 기존 GT에서 pool에 실제로 존재하는 정답만 남겨 evaluation set을 구성했다.

### Source Files

- Tool pool: `data/raw/mcp_zero_servers.jsonl`
- Raw GT sources:
  - `data/ground_truth/seed_set.jsonl`
  - `data/ground_truth/mcp_atlas.jsonl`
- Filtered GT:
  - `data/verification/mcp_zero_gt_filtered.jsonl`

### Filter Result

- Queries: `178`
- Unique correct tools: `32`
- Unique servers: `10`
- Covered servers:
  - `airtable`, `calculator`, `exa`, `fetch`, `filesystem`, `git`, `github`, `memory`, `mongodb`, `slack`

이 구성은 "MCP-Zero 전체 pool에서, 현재 보유 GT가 실제로 평가 가능한 부분집합"을 의미한다.

---

## 3. Optimization Coverage

Filtered GT의 정답 도구 32개에 대해 retrieval-aligned optimizer를 실행했다.

- Output artifact: `data/verification/mcp_zero_gt_optimized_descriptions.jsonl`
- Available GT tools in pool: `32/32`
- `success`: `7`
- `gate_rejected`: `25`
- `failed`: `0`

### Success Tools

- `airtable::list_bases`
- `calculator::calculate`
- `exa::web_search_exa`
- `filesystem::list_directory`
- `github::list_issues`
- `memory::read_graph`
- `mongodb::list-collections`

### Query Coverage Of Success Tools

성공한 7개 tool이 실제로 영향을 줄 수 있는 쿼리는 `61/178`개였다.

즉 이번 실험은 "현재 gate 정책을 유지한 실사용 상태"의 성능을 본 결과이며, 가장 큰 제약은 여전히 gate throughput이다.

---

## 4. Primary Result — Query-Level Metrics

Query 단위가 실제 retrieval 사용 단위이므로, 아래 수치를 primary readout으로 사용한다.

Artifact:
- `data/verification/mcp_zero_query_level_eval.json`

| Metric | Original | Optimized | Delta |
|--------|----------|-----------|-------|
| `P@1` | `0.2753` | `0.3427` | `+0.0674` |
| `Recall@10` | `0.6517` | `0.6629` | `+0.0112` |
| `MRR` | `0.4136` | `0.4439` | `+0.0304` |
| `Avg Rank` | `188.76` | `206.59` | `+17.83` |
| `Median Rank` | `3.5` | `4.0` | `+0.5` |

### Paired Outcome Counts

- `top1 win`: `13`
- `top1 loss`: `1`
- `top10 win`: `3`
- `top10 loss`: `1`
- `rank improved`: `35`
- `rank degraded`: `23`
- `rank same`: `120`

### Statistical Readout

- `delta P@1` 95% CI: `[+0.0281, +0.1067]`
- `delta Recall@10` 95% CI: `[-0.0112, +0.0393]`
- `delta MRR` 95% CI: `[+0.0069, +0.0529]`
- exact binomial `p` for top-1 discordant pairs: `0.0018`
- exact binomial `p` for top-10 discordant pairs: `0.6250`

### Interpretation

현재 구현은 다음을 보인다.

1. `P@1`과 `MRR`은 의미 있게 개선된다.
2. `Recall@10`은 소폭 개선되지만 아직 강한 통계적 확신은 없다.
3. 상위권 rank는 좋아졌지만, long-tail rank는 일부 쿼리에서 악화된다.

즉 retrieval-aligned refactor의 방향성은 맞지만, 아직 "candidate recall을 안정적으로 넓히는 단계"보다는 "일부 쿼리에서 top-1/top-few를 끌어올리는 단계"에 가깝다.

---

## 5. Secondary Result — Tool-Average Diagnostic

기존 스크립트 `scripts/run_retrieval_ab_eval.py`는 tool별 metric 평균을 리포트한다. 이 값은 보조 진단으로만 해석해야 한다.

Artifact:
- `data/verification/mcp_zero_retrieval_ab_report.json`

| Metric | Original | Optimized | Delta |
|--------|----------|-----------|-------|
| `Recall@10` | `0.5648` | `0.5699` | `+0.0052` |
| `P@1` | `0.2227` | `0.2465` | `+0.0238` |
| `MRR` | `0.3555` | `0.3623` | `+0.0069` |

- per-tool improved: `2`
- per-tool degraded: `1`
- per-tool same: `29`

이 리포트도 개선 방향은 동일하지만, query 수가 많은 tool과 적은 tool을 동일 가중치로 평균내므로 primary success metric으로 쓰기엔 부적절하다.

---

## 6. 핵심 해석

### 6.1 긍정적 신호

- `retrieval_description` canonicalization 이후 성능 방향이 historical regression에서 반전됐다.
- 특히 top-1 retrieval과 MRR 개선은 현재 optimizer가 "더 나은 상위 후보 정렬"에 기여함을 시사한다.

### 6.2 현재 bottleneck

- 32개 GT tool 중 `25개`가 gate에서 막혔다.
- gate reject의 대부분은 `Similarity < 0.75`였다.
- 따라서 현재 병목은 "LLM이 retrieval text를 못 쓰는 것"보다 "현재 gate가 너무 많은 candidate rewrite를 원문 fallback으로 되돌리는 것"에 더 가깝다.

### 6.3 주의할 점

- 평균 rank는 악화되었다. 일부 성공 tool, 특히 `exa::web_search_exa`와 `calculator::calculate` 주변에서 tail 쿼리 변동성이 크다.
- 따라서 다음 단계는 단순히 더 많이 rewrite하는 것이 아니라, gate 통과율을 높이되 long-tail rank regression을 같이 감시하는 방향이어야 한다.

---

## 7. 현재 결론

2026년 3월 30일 기준, description optimizer의 retrieval-aligned refactor는 `mcp_zero` 기반 오프라인 평가에서 **부분적이지만 실제 성능 향상**을 보였다.

- `P@1`: 개선
- `MRR`: 개선
- `Recall@10`: 소폭 개선, 아직 확정적이지 않음
- 최대 병목: gate reject 비율 `25/32`

따라서 현재 단계의 결론은 다음과 같다.

> `retrieval_description` 중심 리디자인은 옳았고, 다음 성능 레버는 GEO가 아니라 gate throughput과 long-tail regression control이다.

---

## 8. 다음 작업 권장

1. gate reject 25건을 유형별로 분해해 similarity threshold, contamination, hallucination 기여도를 정리한다.
2. `Similarity >= 0.75` 기준이 과도한지 재검증한다.
3. query-level `Recall@10`을 primary, `MRR`를 secondary, `P@1`를 downstream diagnostic으로 유지한다.
4. success tool 7개에 집중된 개선이 다른 domains로 일반화되는지 추가 평가한다.
