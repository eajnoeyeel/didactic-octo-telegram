# Ground Truth 설계 — 스키마, Seed 전략, 품질 규칙

> 최종 업데이트: 2026-03-22
> Pydantic 모델/JSON 예시: `./ground-truth-schema.md`

---

## 스키마 개요

- 파일 형식: **JSONL** (한 줄 = 한 엔트리, Git diff 추적 용이, 스트리밍 로딩 가능)
- 파일 위치: `data/ground-truth/seed_set.jsonl`, `data/ground-truth/synthetic.jsonl`
- 모든 엔트리는 `GroundTruthEntry` Pydantic 모델로 검증

### 필수 필드

| 필드 | 설명 | 지원 지표 |
|------|------|----------|
| `query_id` | 고유 ID (e.g., `gt-search-001`) | 전체 |
| `query` | 자연어 쿼리 | 모든 지표 입력 |
| `correct_server_id` | 정답 MCP 서버 ID | Server Recall@K, MRR, Server Error Rate |
| `correct_tool_id` | 정답 Tool ID (`server_id::tool_name`, TOOL_ID_SEPARATOR="::") | Precision@1, Tool Recall@10, NDCG@5, Confusion Rate |
| `difficulty` | easy / medium / hard | 난이도별 Precision@1 분석 |
| `category` | 8개 카테고리 | 도메인별 분석, Taxonomy-gated 평가 |
| `ambiguity` | low / medium / high | 모호도별 분석 |
| `source` | manual_seed / llm_synthetic / llm_verified | 데이터 품질 추적 |
| `manually_verified` | boolean | seed vs synthetic 구분 |
| `author` | 작성자 ID 또는 모델명 | 출처 추적 |
| `created_at` | ISO 8601 | 버전 추적 |

### 선택 필드

| 필드 | 설명 | 지원 지표 |
|------|------|----------|
| `alternative_tools` | 부분 관련 대안 Tool ID 목록 | NDCG@5 graded relevance (정답=2, 대안=1, 기타=0) |
| `notes` | 어노테이션 메모 | 판단 근거 기록 |

---

## Seed Set 구성 계획 — 80개 수동 작성

### 카테고리별 분배 (8개 x 10개)

| 카테고리 | 쿼리 수 | Easy | Medium | Hard | 대표 서버 |
|----------|---------|------|--------|------|-----------|
| Search | 10 | 4 | 4 | 2 | semantic_scholar, mcp-arxiv, brave_search |
| Code | 10 | 4 | 4 | 2 | github, mcp-code-review |
| Database | 10 | 4 | 4 | 2 | postgres, sqlite, supabase |
| Communication | 10 | 4 | 4 | 2 | slack, gmail, discord |
| Productivity | 10 | 4 | 4 | 2 | notion, todoist, calendar |
| Science | 10 | 4 | 4 | 2 | mcp-arxiv, wolfram_alpha |
| Finance | 10 | 4 | 4 | 2 | stock_api, currency_converter |
| General | 10 | 4 | 4 | 2 | mcp-calculator, weather, translator |
| **총합** | **80** | **32** | **32** | **16** | — |

### 난이도 기준

- **Easy (40%)**: 쿼리에 Tool 이름/핵심 키워드 직접 포함. BM25만으로 찾을 수 있는 수준.
  - 용도: 베이스라인 측정. 이것도 못 찾으면 근본적 문제.
- **Medium (40%)**: 의미적 유사성으로 연결, 직접 키워드 없음. Dense retrieval 필요.
  - 용도: Dense retrieval vs BM25 차이 측정.
- **Hard (20%)**: 모호/다의적, 여러 Tool이 부분 적합. Reranker + Confidence 분기 필요.
  - 용도: Confusion Rate, disambiguation, NDCG@5 측정 핵심.

### Ambiguity 분포 가이드라인

- Easy 쿼리: 대부분 Low ambiguity
- Medium 쿼리: Low ~ Medium ambiguity
- Hard 쿼리: Medium ~ High ambiguity
- High ambiguity → `alternative_tools` 필수 기재

---

## 어노테이션 규칙

1. **하나의 쿼리에 반드시 하나의 `correct_tool_id`**: "둘 다 정답" 불허. 차선은 `alternative_tools`에 기록
2. **`correct_server_id`는 `correct_tool_id`에서 파생 가능하지만 명시적 기재**: Layer 1 독립 평가에 필요
3. **difficulty 판정**:
   - "BM25만으로 찾을 수 있나?" → Easy
   - "임베딩 검색이 필요한가?" → Medium
   - "Reranker나 disambiguation이 필요한가?" → Hard
4. **ambiguity 판정**: "5명에게 물어보면 같은 Tool을 고를까?" — 5/5 → Low, 3-4/5 → Medium, 2/5 이하 → High
5. **alternative_tools**: ambiguity Medium 이상이면 필수. "이것이 정답이어도 틀렸다고 할 수 없는" Tool들
6. **notes**: 난이도/모호도 분류 근거, 특수 케이스 판단 로직 기록

---

## Synthetic 쿼리 생성 — LLM 기반

### 프로세스

```
Tool Description 입력
    |
LLM (GPT-4o-mini) — Tool당 10개 쿼리 생성
    |
난이도 자동 분류 (LLM에게 Easy/Medium/Hard 태깅 요청)
    |
품질 게이트 (아래 기준)
    |
data/ground-truth/synthetic.jsonl에 저장
```

### 품질 게이트 (Quality Gate)

| 기준 | 측정 방법 | 통과 조건 |
|------|----------|----------|
| 난이도 분포 일치 | seed set 비율과 비교 | 각 비율 차이 < 15% |
| 쿼리 다양성 | 생성 쿼리 간 코사인 유사도 평균 | 평균 유사도 < 0.7 |
| 키워드 누출 | Medium/Hard에 Tool 이름 직접 포함 여부 | 0% |
| 사람 검증 샘플 | 무작위 20% 수동 확인 | 난이도/모호도 판정 일치율 >= 80% |
| Obvious 쿼리 비율 | Tool description과 ROUGE-L >= 0.6인 쿼리 | < 10% |

### 검증 파일럿 절차

1. Seed set 80개 중 20개 선택
2. 해당 20개 Tool에 LLM으로 쿼리 10개씩 생성 (200개)
3. 생성 200개와 seed 20개 비교: 겹침 비율, 난이도 분포 차이, 수동 품질 평가 (1-5점)
4. 품질 게이트 통과 확인 후 나머지 Tool에 확대 생성

---

## 자체 MCP 서버 — A/B Description 실험용

### A/B Pair 구조

| 서버 | Version A (Poor) | Version B (Good) |
|------|-----------------|-------------------|
| `mcp-arxiv` | "A tool for searching papers" | "Search arXiv academic papers by keyword, author, or date range. Returns title, abstract, authors, and PDF link. NOT for web search or news." |
| `mcp-calculator` | "Calculator tool" | "Evaluate math expressions, convert units (metric/imperial, currency with live rates), compute statistics (mean, median, std). NOT for symbolic math." |
| `mcp-korean-news` | "Korean news search" | "Search Korean news from major outlets (조선일보, 한겨레, 연합뉴스 등) by keyword and date. Returns headline, summary, source, URL. NOT for English news." |

### A/B 실험 프로세스

1. 동일 쿼리셋 → Version A Pool, Version B Pool에 각각 실행
2. Precision@1 차이 = **Selection Rate Lift** (primary evidence)
3. 모든 Tool의 (quality_score, selection_rate) → **Spearman** (secondary evidence)
4. 다변량 회귀로 quality 요소별 기여도 = **Regression R-squared** (supplementary evidence)

---

## 데이터 디렉토리 구조

```
data/
+-- ground-truth/
|   +-- seed_set.jsonl           # 수동 작성 80개
|   +-- synthetic.jsonl          # LLM 생성 + 품질 게이트 통과분
|   +-- quality_gate_report.json # 파일럿 검증 결과
+-- tool-pools/
|   +-- base_pool.json           # 기본 50서버 Pool 정의
|   +-- high_similarity_pool.json
|   +-- low_similarity_pool.json
|   +-- description_quality_pool.json  # A/B pair 포함
+-- server-metadata/
    +-- smithery_crawl.json      # Smithery 서버 메타데이터
    +-- self_built/              # 자체 MCP 서버 tools/list 결과
        +-- mcp_arxiv_v1.json / v2.json
        +-- mcp_calculator_v1.json / v2.json
        +-- mcp_korean_news_v1.json / v2.json
```
