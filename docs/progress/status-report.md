# MCP Discovery Platform — 진행 현황 보고서

> 최종 업데이트: 2026-03-25
> 브랜치: `main`

---

## 요약

| 항목 | 현재 상태 |
|------|-----------|
| 완료된 Phase | Phase 0 ~ Phase 4 |
| 다음 Phase | Phase 5 (평가 하네스) |
| 테스트 | **187 passed**, 6 skipped |
| 커버리지 | **98%** (목표 80%+ 대폭 초과) |
| Lint/Format | PASS (ruff check + ruff format) |
| 외부 서비스 | Qdrant Docker 로컬 + Smithery API 실제 연동 검증 완료 |
| PR | #1 (core-pipeline), #2 (ground-truth) 머지 완료 |

---

## Phase별 완료 현황

### Phase 0: 프로젝트 기반 — 완료

| 산출물 | 파일 | 커버리지 |
|--------|------|----------|
| 패키지 관리 | `pyproject.toml` (uv) | - |
| 설정 | `src/config.py` (pydantic-settings) | 100% |
| 데이터 모델 | `src/models.py` (Pydantic v2) | 100% |
| 테스트 | `tests/unit/test_config.py`, `test_models.py` | - |

**주요 모델**: `MCPTool`, `MCPServer`, `MCPServerSummary`, `SearchResult`, `GroundTruthEntry`
- `tool_id` 포맷: `"{server_id}::{tool_name}"` (TOOL_ID_SEPARATOR = `::`)
- `GroundTruthEntry`: Difficulty/Category/Ambiguity Enum, source 필드, alternative_tools

### Phase 1: 데이터 수집 — 완료

| 산출물 | 파일 | 커버리지 |
|--------|------|----------|
| Smithery HTTP 클라이언트 | `src/data/smithery_client.py` | **100%** |
| Smithery 크롤러 오케스트레이터 | `src/data/crawler.py` | 100% |
| MCP 직접 연결 | `src/data/mcp_connector.py` | **100%** |
| 서버 선별기 | `src/data/server_selector.py` | 100% |
| 수집 스크립트 | `scripts/collect_data.py` | - |
| 시드 데이터 | `data/raw/servers.jsonl` (3 서버, 58 도구) | - |

**통합 테스트로 검증된 항목** (`tests/integration/test_smithery_integration.py`):
- 실제 Smithery Registry API (`https://registry.smithery.ai`)에 접속하여 검증
- `fetch_server_list()`: 실제 페이지네이션 + 응답 파싱
- `fetch_server_detail()`: 실제 서버 상세 + 도구 목록 파싱
- `fetch_all_summaries()`: 다중 페이지 크롤링
- `_request_with_retry()`: 429/5xx 재시도, ConnectError 재시도, 비재시도 에러(400) 즉시 실패
- `_rate_limit()`: 실제 시간 기반 검증
- Context manager (`__aenter__`/`__aexit__`)

### Phase 2: 임베딩 + Vector Store — 완료

| 산출물 | 파일 | 커버리지 |
|--------|------|----------|
| Embedder ABC | `src/embedding/base.py` | 100% |
| OpenAI Embedder | `src/embedding/openai_embedder.py` | 79% |
| Qdrant Store | `src/retrieval/qdrant_store.py` | **96%** |
| Tool Indexer | `src/data/indexer.py` | 100% |
| 인덱스 빌드 스크립트 | `scripts/build_index.py` | - |

**통합 테스트로 검증된 항목** (`tests/integration/test_qdrant_integration.py`):
- 실제 Qdrant Docker (`localhost:6333`)에 접속하여 검증
- `ensure_collection()`: 컬렉션 생성 + 멱등성 (이미 존재 시 재생성 안 함)
- `upsert_tools()`: 실제 벡터 upsert + 멱등성 (중복 upsert 시 포인트 수 유지)
- `search()`: 실제 벡터 유사도 검색 + top_k 제한 + server_id 필터 + 빈 컬렉션
- `search_server_ids()`: 실제 검색 후 server_id 추출
- 에러 핸들링: 잘못된 연결, 존재하지 않는 컬렉션에서의 upsert/search 실패 검증

**버그 발견 및 수정**: `qdrant-client >= 1.12`에서 `client.search()` → `client.query_points()` API 변경을 통합 테스트로 발견. `qdrant_store.py`의 `search()`와 `search_server_ids()` 메서드를 새 API에 맞게 수정.

**미커버 (3 lines)**: `create_collection` 실패 시 except 분기 (line 44-46) — 정상 Qdrant에서는 발생 불가

**OpenAI Embedder** (`tests/integration/test_openai_integration.py`):
- OpenAI API 키 필요 → 키 없으면 skip (6 skipped 중 3개)
- 준비된 테스트: `embed_one()` 반환 타입/차원, `embed_batch()` 일관성

### Phase 3: 코어 파이프라인 — 완료

| 산출물 | 파일 | 커버리지 |
|--------|------|----------|
| PipelineStrategy ABC + Registry | `src/pipeline/strategy.py` | 100% |
| Gap-based 신뢰도 분기 | `src/pipeline/confidence.py` | 100% |
| Sequential Strategy (2-Layer) | `src/pipeline/sequential.py` | 100% |
| Flat Strategy (1-Layer, E0용) | `src/pipeline/flat.py` | 100% |

모든 파이프라인 모듈 100% 커버리지.

### Phase 4: Ground Truth — 완료

| 산출물 | 파일 | 커버리지 |
|--------|------|----------|
| GT 로딩/필터/병합/분할 | `src/data/ground_truth.py` | **99%** |
| Synthetic GT 생성 | `src/data/ground_truth.py` (`generate_synthetic_gt`) | 포함 |
| Quality Gate | `src/data/ground_truth.py` (`QualityGate` 클래스) | 포함 |
| GT 생성 스크립트 | `scripts/generate_ground_truth.py` | - |
| Seed Set | `data/ground_truth/seed_set.jsonl` (80 엔트리) | - |

**Seed Set 구성** (80개):
- 8 카테고리 × 10개 = 80 엔트리
- 난이도 분포: Easy 4 : Medium 4 : Hard 2
- 5개 서버: `EthanHenrickson/math-mcp`, `@anthropic/claude-code`, `@smithery-ai/github`, `@anthropic/fetch-mcp`, `@anthropic/filesystem-mcp`

**추가된 엣지 케이스 테스트**:
- non-list JSON 반환 시 빈 결과
- hard + low ambiguity + 대안 도구 없음 → 스킵
- medium ambiguity + 대안 도구 없음 → low로 다운그레이드
- LLM 호출 실패 시 해당 도구만 스킵, 나머지 계속 생성
- `created_at` 미지정 시 `date.today()` 자동 사용
- easy 난이도 → 도구명 누출(leakage) 체크 면제

**미커버 (2 lines)**: `GroundTruthEntry` 생성 시 Pydantic validation except 분기 (line 269-270) — 정상 데이터에서 발생 불가

---

## 인프라 현황

### 연결된 외부 서비스

| 서비스 | 상태 | 검증 방식 |
|--------|------|-----------|
| **Qdrant Docker** | 실행 중 (`localhost:6333`) | 통합 테스트 11개 통과 |
| **Smithery Registry** | 연결 완료 (`registry.smithery.ai`) | 통합 테스트 8개 통과 |

### 미연결 외부 서비스

| 서비스 | 용도 | 비용 | Phase |
|--------|------|------|-------|
| OpenAI API | 임베딩 + Synthetic GT 생성 | ~$1-2/월 | Phase 2, 4 |
| Cohere API | Reranker (`Rerank 3`) | Free tier | Phase 6 |
| Langfuse | LLM 트레이싱 | 무료 | Phase 11 |
| W&B | 실험 추적 | 무료 (개인) | Phase 10 |

---

## 테스트 현황

```
187 passed, 6 skipped
전체 커버리지: 98%
```

### 테스트 구조

```
tests/
├── unit/                  # 단위 테스트 (159개) — 외부 서비스 불필요
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_crawler.py
│   ├── test_smithery_client.py
│   ├── test_mcp_connector.py
│   ├── test_server_selector.py
│   ├── test_embedder.py
│   ├── test_qdrant_store.py
│   ├── test_indexer.py
│   ├── test_pipeline_strategy.py
│   ├── test_confidence.py
│   ├── test_sequential_strategy.py
│   ├── test_flat_strategy.py
│   └── test_ground_truth.py
└── integration/           # 통합 테스트 (22개) — 실제 서비스 연동
    ├── test_qdrant_integration.py     # 실제 Qdrant Docker
    ├── test_smithery_integration.py   # 실제 Smithery API
    └── test_openai_integration.py     # 실제 OpenAI API (키 필요)
```

### 커버리지 상세

| 파일 | 커버리지 | 비고 |
|------|----------|------|
| `config.py` | 100% | |
| `models.py` | 100% | |
| `crawler.py` | 100% | |
| `indexer.py` | 100% | |
| `server_selector.py` | 100% | |
| `pipeline/*` (4개) | 100% | |
| `data/smithery_client.py` | **100%** | 실제 Smithery API로 검증 |
| `data/mcp_connector.py` | **100%** | |
| `data/ground_truth.py` | **99%** | except 분기 2줄만 미커버 |
| `retrieval/qdrant_store.py` | **96%** | 실제 Qdrant Docker로 검증 |
| `embedding/openai_embedder.py` | 79% | OpenAI API 키 필요 → skip |

### 스킵된 테스트 (6개)

| 테스트 | 이유 | 해결 조건 |
|--------|------|-----------|
| `test_generate_synthetic_gt_integration` | OPENAI_API_KEY 없음 | API 키 설정 |
| `test_openai_integration.py` (3개) | OPENAI_API_KEY 없음 | API 키 설정 |
| `test_embedder.py` (2개) | OPENAI_API_KEY 없음 | API 키 설정 |

모든 스킵은 OpenAI API 키 부재 때문. 키 설정 시 자동으로 실행됨.

---

## 주요 변경 사항 (이번 세션)

### 1. Qdrant API 호환성 버그 수정
- **문제**: `qdrant-client >= 1.12`에서 `client.search()` API가 `client.query_points()`로 변경됨
- **발견 경위**: 통합 테스트에서 실제 Qdrant Docker에 연결하여 발견
- **수정**: `qdrant_store.py`의 `search()`와 `search_server_ids()` 메서드를 `query_points()` API로 변경
- **교훈**: 실제 서비스 연동 테스트가 없었다면 프로덕션에서야 발견했을 버그

### 2. 통합 테스트 추가 (22개)
- `test_qdrant_integration.py`: 실제 Qdrant Docker 대상 11개 테스트
- `test_smithery_integration.py`: 실제 Smithery Registry API 대상 8개 테스트
- `test_openai_integration.py`: OpenAI API 대상 3개 테스트 (키 필요 시 skip)

### 3. 엣지 케이스 테스트 보강
- `ground_truth.py`: 6개 엣지 케이스 추가 (90% → 99%)
- `mcp_connector.py`: tool name 누락 케이스 추가 (88% → 100%)
- `qdrant_store.py`: `payload_to_tool` 실패 케이스 추가

### 4. 플레이스홀더 테스트 삭제
- `test_legacy_schema_removed` (pytest.skip 플레이스홀더) 삭제

---

## Git 히스토리

| PR | 브랜치 | 내용 |
|----|--------|------|
| #1 | `feat/core-pipeline` | Phase 0~3 (기반, 데이터, 임베딩, 파이프라인) |
| #2 | `feat/ground-truth` | Phase 4 (Ground Truth 생성) |

---

## 다음 단계

### 즉시 가능 (외부 서비스 불필요)
1. **Phase 5: 평가 하네스** 구현 시작
   - `src/evaluation/evaluator.py` — Evaluator ABC
   - Precision@1, Recall@K, MRR, Confusion Rate, ECE, Spearman 메트릭 구현
   - `src/evaluation/harness.py` — `evaluate(strategy, queries, gt) → Metrics`

### 백로그: OpenAI API 키 확보 후 진행

> Phase 4 파일럿 검증 및 임베딩 관련 작업이 OpenAI API 키에 의존. 키 확보 시 즉시 실행 가능.

| 우선순위 | 항목 | 의존 |
|---------|------|------|
| 높음 | `openai_embedder.py` 커버리지 79% → 100% (통합 테스트 활성화, skip 6개 해소) | Phase 2 |
| 높음 | Synthetic GT 생성 실행 (`scripts/generate_ground_truth.py`) | Phase 4 |
| 높음 | 임베딩 인덱스 빌드 (`scripts/build_index.py`) | Phase 2 |
| 중간 | E0 실험: 1-Layer vs 2-Layer 검증 | Phase 5 완료 후 |
