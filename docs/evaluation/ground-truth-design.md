# Ground Truth 구조 설계

> 작성: 2026-03-19
> 입력 조건: `docs/evaluation/metrics-rubric.md`의 "필요한 필드" 섹션
> 목적: 모든 평가 지표를 계산 가능하게 하는 Ground Truth 데이터 스키마 + 생성/검증 절차

---

## 1. 스키마 정의

### Pydantic 모델

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional


class Difficulty(str, Enum):
    EASY = "easy"        # 명시적 키워드 매칭 (e.g., "search papers" → search_papers)
    MEDIUM = "medium"    # 의미적 유사 (e.g., "find academic research" → search_papers)
    HARD = "hard"        # 모호/다의적 (e.g., "help me with my research" → 여러 후보 가능)


class Ambiguity(str, Enum):
    LOW = "low"          # 정답이 하나로 명확
    MEDIUM = "medium"    # 2-3개 후보가 있지만 최선이 구분됨
    HIGH = "high"        # 여러 Tool이 비슷하게 적합


class Category(str, Enum):
    SEARCH = "search"
    CODE = "code"
    DATABASE = "database"
    COMMUNICATION = "communication"
    PRODUCTIVITY = "productivity"
    SCIENCE = "science"
    FINANCE = "finance"
    GENERAL = "general"


class GroundTruthEntry(BaseModel):
    """단일 Ground Truth 엔트리 — 하나의 (쿼리, 정답) 쌍"""

    # 필수 필드 — 모든 지표 계산에 필요
    query_id: str = Field(description="고유 ID, e.g., 'gt-search-001'")
    query: str = Field(description="자연어 쿼리")
    correct_server_id: str = Field(description="정답 MCP 서버 ID")
    correct_tool_id: str = Field(description="정답 Tool ID (server_id/tool_name 형식)")

    # 분류 필드 — 세분화 분석용
    difficulty: Difficulty
    category: Category
    ambiguity: Ambiguity

    # 메타데이터 — 품질 관리
    source: str = Field(description="'manual_seed' | 'llm_synthetic' | 'llm_verified'")
    manually_verified: bool = Field(default=False)
    author: str = Field(description="작성자 ID 또는 'gpt-4o-mini' 등")
    created_at: str = Field(description="ISO 8601 날짜")

    # 선택 필드 — NDCG graded relevance용
    alternative_tools: Optional[list[str]] = Field(
        default=None,
        description="부분적으로 관련 있는 대안 Tool ID 목록 (relevance_grade=1)"
    )
    notes: Optional[str] = Field(default=None, description="어노테이션 메모")
```

### 필드 ↔ 지표 매핑

| 필드 | 지원하는 지표 |
|------|-------------|
| `query` | 모든 지표의 입력 |
| `correct_server_id` | Server Recall@K, MRR, Server Error Rate |
| `correct_tool_id` | Precision@1, Tool Recall@10, NDCG@5, Confusion Rate |
| `difficulty` | 난이도별 성능 분석 (Easy/Medium/Hard 그룹별 Precision@1) |
| `category` | 도메인별 성능 분석, Taxonomy-gated 전략 평가 |
| `ambiguity` | 모호도별 분석, Confusion Rate와의 교차 분석 |
| `alternative_tools` | NDCG@5 graded relevance (정답=2, 대안=1, 기타=0) |
| `manually_verified` | seed set vs synthetic 구분, 품질 기준점 |
| `source` | 데이터 품질 추적 |

---

## 2. 데이터 형식 — JSONL

```jsonl
{"query_id":"gt-search-001","query":"find recent papers about transformer architectures","correct_server_id":"semantic_scholar","correct_tool_id":"semantic_scholar/search_papers","difficulty":"easy","category":"search","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-20","alternative_tools":["mcp_arxiv/search_arxiv"],"notes":"키워드 'papers'가 명시적으로 매칭됨"}
{"query_id":"gt-search-002","query":"I need academic research on attention mechanisms","correct_server_id":"semantic_scholar","correct_tool_id":"semantic_scholar/search_papers","difficulty":"medium","category":"search","ambiguity":"medium","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-20","alternative_tools":["mcp_arxiv/search_arxiv"],"notes":"'academic research'가 의미적으로 papers와 연결"}
{"query_id":"gt-search-003","query":"help me with my research","correct_server_id":"semantic_scholar","correct_tool_id":"semantic_scholar/search_papers","difficulty":"hard","category":"search","ambiguity":"high","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-20","alternative_tools":["mcp_arxiv/search_arxiv","google_scholar/search"],"notes":"'research'가 모호 — 논문? 웹 검색? 데이터 분석?"}
```

**왜 JSONL인가**:
- 한 줄 = 한 엔트리 → Git diff에서 변경 추적 용이
- 스트리밍 로딩 가능 (대규모 데이터셋에서 메모리 절약)
- Pandas `read_json(lines=True)`로 즉시 DataFrame 변환

**파일 위치**: `data/ground_truth/seed_set.jsonl`, `data/ground_truth/synthetic.jsonl`

---

## 3. Seed Set 구성 계획 — 80개 수동 작성

### 카테고리별 분배 (8개 카테고리 × 10개)

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

### 난이도 기준 상세

**Easy (40%)**:
- 쿼리에 Tool 이름 또는 핵심 키워드가 직접 포함
- 예: "search papers on arxiv" → `mcp_arxiv/search_arxiv`
- 임베딩 검색 없이도 키워드 매칭으로 찾을 수 있는 수준
- 용도: 베이스라인 측정. 이것조차 못 찾으면 근본적 문제.

**Medium (40%)**:
- 의미적 유사성으로 연결되지만 직접적 키워드는 없음
- 예: "find academic literature about LLMs" → `semantic_scholar/search_papers`
- 임베딩 검색의 의미 이해 능력이 필요
- 용도: Dense retrieval vs BM25 차이 측정.

**Hard (20%)**:
- 모호하거나 다의적, 여러 Tool이 부분적으로 적합
- 예: "help me analyze this data" → 여러 후보 중 context에 따라 다름
- Reranker + Confidence 분기의 진가가 드러나는 케이스
- 용도: Confusion Rate, disambiguation, NDCG@5 측정 핵심.

### Ambiguity 분포 가이드라인

- Easy 쿼리: 대부분 Low ambiguity
- Medium 쿼리: Low ~ Medium ambiguity
- Hard 쿼리: Medium ~ High ambiguity
- High ambiguity인 경우 `alternative_tools` 필수 기재

---

## 4. 어노테이션 가이드라인

### 규칙

1. **하나의 쿼리에 반드시 하나의 `correct_tool_id`**: 가장 적합한 Tool 하나만 정답. "둘 다 정답"은 불허 — 그 대신 `alternative_tools`에 차선을 기록.

2. **`correct_server_id`는 `correct_tool_id`에서 자동 파생 가능**: 하지만 명시적으로 기재. Layer 1 독립 평가에 필요.

3. **difficulty 판정 기준**:
   - 쿼리를 보고 "BM25만으로 찾을 수 있나?" → Easy
   - "임베딩 검색이 필요한가?" → Medium
   - "Reranker나 disambiguation이 필요한가?" → Hard

4. **ambiguity 판정 기준**:
   - "이 쿼리로 5명에게 물어보면 같은 Tool을 고를까?"
   - 5/5 동의 → Low, 3-4/5 → Medium, 2/5 이하 → High

5. **alternative_tools 작성 기준**:
   - ambiguity가 Medium 이상이면 반드시 기재
   - "이 쿼리의 정답으로 골랐어도 틀렸다고 할 수 없는" Tool들

6. **notes 활용**:
   - 왜 이 난이도/모호도로 분류했는지 근거
   - 특수한 케이스의 경우 판단 로직

---

## 5. Synthetic 쿼리 생성 — LLM 기반

### 생성 프로세스

```
Tool Description 입력
    ↓
LLM (GPT-4o-mini) — Tool당 10개 쿼리 생성
    ↓
난이도 자동 분류 (LLM에게 Easy/Medium/Hard 태깅 요청)
    ↓
품질 게이트 (아래 기준)
    ↓
data/ground_truth/synthetic.jsonl에 저장
```

### 프롬프트 템플릿

```
You are generating test queries for a tool recommendation system.

Tool: {tool_name}
Server: {server_id}
Description: {tool_description}

Generate 10 natural language queries that a user would ask when they need this tool.
Distribute difficulty:
- 4 queries: Easy (contains obvious keywords)
- 4 queries: Medium (semantic match, no direct keywords)
- 2 queries: Hard (ambiguous, could match multiple tools)

For each query, output JSON:
{
  "query": "...",
  "difficulty": "easy|medium|hard",
  "ambiguity": "low|medium|high",
  "notes": "why this difficulty/ambiguity"
}

Rules:
- Do NOT include the tool name in the query
- Vary sentence structures (question, command, description of need)
- Hard queries should genuinely be ambiguous
- Include both English and Korean queries if the tool supports Korean
```

### 품질 게이트 (Quality Gate)

생성된 synthetic 쿼리가 seed set과 비교해서 품질 기준을 충족하는지 검증:

| 기준 | 측정 방법 | 통과 조건 |
|------|----------|----------|
| **난이도 분포 일치** | seed set의 Easy:Medium:Hard 비율과 비교 | 각 비율 차이 < 15% |
| **쿼리 다양성** | 생성된 쿼리 간 코사인 유사도 평균 | 평균 유사도 < 0.7 (너무 비슷한 쿼리 방지) |
| **키워드 누출** | Easy가 아닌 쿼리에 Tool 이름 직접 포함 여부 | Medium/Hard에서 Tool 이름 포함 = 0% |
| **사람 검증 샘플** | 무작위 20% 수동 확인 | 난이도/모호도 판정 일치율 >= 80% |
| **Obvious 쿼리 비율** | "너무 쉬운" 쿼리 = Tool description을 거의 그대로 옮긴 것 | < 10% |

**Obvious 쿼리 정의**: Tool description과의 ROUGE-L 점수가 0.6 이상인 쿼리. Description을 그대로 복사한 것은 실제 사용자 쿼리를 반영하지 못함.

### 검증 파일럿 절차

1. Seed set 80개 중 20개를 선택
2. 해당 20개 Tool에 대해 LLM으로 쿼리 10개씩 생성
3. 생성된 200개와 seed 20개 비교:
   - 겹치는 쿼리 비율
   - 난이도 분포 차이
   - 수동 품질 평가 (1-5점)
4. 품질 게이트 통과 여부 확인 후 나머지 Tool에 대해 확대 생성

---

## 6. 자체 MCP 서버 통합 — A/B Description 실험용

### A/B Pair 구조

프로젝트 테제 검증 (evidence triangulation)을 위해, 자체 구축 MCP 서버는 각각 두 가지 description 버전으로 등록:

| 서버 | Version A (Poor) | Version B (Good) |
|------|-----------------|-------------------|
| `mcp-arxiv` | "A tool for searching papers" | "Search arXiv academic papers by keyword, author, or date range. Returns title, abstract, authors, and PDF link. NOT for web search or news — use for scholarly articles only." |
| `mcp-calculator` | "Calculator tool" | "Evaluate mathematical expressions, convert units (metric↔imperial, currency with live rates), and compute statistics (mean, median, std). NOT for symbolic math or equation solving." |
| `mcp-korean-news` | "Korean news search" | "Search Korean news articles from major outlets (조선일보, 한겨레, 연합뉴스 등) by keyword and date range. Returns headline, summary, source, and URL. NOT for English news or academic papers." |

### Ground Truth에서의 표현

```jsonl
{"query_id":"gt-ab-arxiv-001","query":"find recent machine learning papers","correct_server_id":"mcp_arxiv_v2","correct_tool_id":"mcp_arxiv_v2/search_arxiv","difficulty":"easy","category":"search","ambiguity":"low","source":"manual_seed","manually_verified":true,"author":"iyeonjae","created_at":"2026-03-20","notes":"A/B test pair - same query, measured against both versions"}
```

### A/B 실험 프로세스

1. **동일 쿼리셋**을 Version A Pool과 Version B Pool에 각각 실행
2. 두 Pool의 Precision@1 차이 = **Selection Rate Lift** (primary evidence)
3. 모든 Tool의 (quality_score, selection_rate) 쌍으로 **Spearman** (secondary evidence)
4. 다변량 회귀로 quality 요소별 기여도 = **Regression R²** (supplementary evidence)

---

## 7. 데이터 디렉토리 구조

```
data/
├── ground_truth/
│   ├── seed_set.jsonl           # 수동 작성 80개
│   ├── synthetic.jsonl          # LLM 생성 + 품질 게이트 통과분
│   └── quality_gate_report.json # 파일럿 검증 결과
├── tool_pools/
│   ├── base_pool.json           # 기본 50서버 Pool 정의
│   ├── high_similarity_pool.json
│   ├── low_similarity_pool.json
│   └── description_quality_pool.json  # A/B pair 포함
└── server_metadata/
    ├── smithery_crawl.json      # Smithery에서 수집한 서버 메타데이터
    └── self_built/              # 자체 MCP 서버 tools/list 결과
        ├── mcp_arxiv_v1.json
        ├── mcp_arxiv_v2.json
        ├── mcp_calculator_v1.json
        ├── mcp_calculator_v2.json
        ├── mcp_korean_news_v1.json
        └── mcp_korean_news_v2.json
```

---

## 8. 로딩 유틸리티 인터페이스

```python
from pathlib import Path
from typing import Iterator

def load_ground_truth(
    path: Path,
    difficulty: Difficulty | None = None,
    category: Category | None = None,
    only_verified: bool = False,
) -> list[GroundTruthEntry]:
    """Ground Truth 로딩 + 필터링

    Args:
        path: JSONL 파일 경로 (seed_set.jsonl 또는 synthetic.jsonl)
        difficulty: 특정 난이도만 필터
        category: 특정 카테고리만 필터
        only_verified: True면 manually_verified=True만 반환

    Returns:
        필터 조건에 맞는 GroundTruthEntry 리스트
    """
    ...

def merge_ground_truth(*paths: Path) -> list[GroundTruthEntry]:
    """여러 JSONL 파일을 합침 (seed + synthetic). query_id 중복 검사."""
    ...

def split_by_difficulty(
    entries: list[GroundTruthEntry]
) -> dict[Difficulty, list[GroundTruthEntry]]:
    """난이도별 그룹 분리 — 난이도별 성능 분석용"""
    ...
```

---

## 9. 다음 단계

1. **즉시**: `data/ground_truth/` 디렉토리 생성, seed_set.jsonl 작성 시작
2. **Smithery 크롤링 후**: 서버 메타데이터 수집 → Pool 정의 파일 작성
3. **자체 MCP 서버 구축 후**: A/B pair description 등록 → description_quality_pool.json 완성
4. **파일럿 검증**: seed set 20개 기반 synthetic 생성 → 품질 게이트 → 확대 생성
5. **코드 구현**: `src/evaluation/ground_truth.py` — 위 Pydantic 모델 + 로딩 유틸리티
