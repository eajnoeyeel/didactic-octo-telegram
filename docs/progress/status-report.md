# MCP Discovery Platform — 진행 현황 보고서

> 최종 업데이트: 2026-03-30
> 브랜치: `main` + `feat/description-optimizer` (활성)

---

## 요약

| 항목 | 현재 상태 |
|------|-----------|
| 완료된 Phase | Phase 0 ~ Phase 5, Description Optimizer Grounded Optimization |
| 진행중 | **disambiguation 재설계 v2** (코드 완료, P@1 0.375 — 과도한 제거 확인) |
| 다음 Phase | Phase 6 (Reranker) + OQ-2 (Pool 크롤링/인덱싱) |
| 테스트 | **389 passed** (main 233 + desc-optimizer 156) |
| 커버리지 | **92%** (feat/description-optimizer 기준) |
| Lint/Format | PASS (ruff check + ruff format) |
| 외부 서비스 | Qdrant Docker 로컬 + Smithery API + OpenAI API 실제 연동 검증 완료 |
| PR | #1 (core-pipeline), #2 (ground-truth) 머지 완료 |

### Description Optimizer 현황 (feat/description-optimizer)

| 항목 | 상태 |
|------|------|
| Grounded Optimization | 10 tasks 구현 완료 |
| A/B 비교 (30 tools) | 완료 — 환각 제거 성공, GEO scorer 한계 발견 |
| **P@1 A/B 평가** | **완료 — δP@1 = -0.069 (검색 성능 저하)** |
| **핵심 발견** | 근본원인 확인: retrieval 경로 불일치 + GEO 보상 왜곡 (분석 완료 2026-03-30) |
| 3-way A/B 평가 | 완료 — search/optimized 모두 δP@1=-0.069, sibling 오염 근본원인 |
| 근본원인 분석 | **완료** — `docs/analysis/description-optimizer-root-cause-analysis.md` |
| **disambiguation v2** | 완료 — sibling 이름 제거 성공, 그러나 P@1 0.375 (v1 0.472보다 악화) |
| **다음 단계** | sibling context 재도입 (이름 없이 카운트/카테고리만) 또는 description 최적화 중단 판단 |
| 상세 보고서 | `data/verification/retrieval_3way_ab_gt_report_v2.json` |

**Disambiguation v2 실험 결과 (2026-03-30):**
- 29 success tools, 0 sibling contamination (목표 달성)
- median P@1: 0.0→1.0 (optimized) — sibling 오염 제거로 정확히 회복
- 전체 P@1: original 0.5417, search 0.3750, optimized 0.3750
- v1 대비: search δP@1 -0.097 악화 (v1 -0.069 → v2 -0.167)
- 새 degradation 5건: modulo, find_duplicates, getGroups, create_branch, GET_POST_COMMENTS
- **결론**: sibling 이름 제거는 정당하나, context 완전 제거는 과도한 조치. 중간 지점 필요

**P@1 A/B 평가 상세 (2026-03-29):**
- 36 GT 도구 최적화 → 18 success, 18 gate-rejected
- Original P@1: 0.5417, Optimized P@1: 0.4722, **δP@1 = -0.069**
- Per-tool: 1 improved (`github::list_issues`), 3 degraded (`math-mcp::median`, `math-mcp::round`, `instagram::GET_USER_MEDIA`), 32 same
- **근본원인**: (1) search_description 미사용 (2) GEO 보상 왜곡 (3) disambiguation 오염 — 분석 완료, `docs/analysis/description-optimizer-root-cause-analysis.md`
- 가설: (a) GEO 차원 무관성 (b) 길이→임베딩 희석 (c) sibling 혼동

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
| OpenAI Embedder | `src/embedding/openai_embedder.py` | 79% (exception 경로만 미커버) |
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
- OpenAI API 키 설정 완료 → 5개 통합 테스트 모두 PASS
- 검증 항목: `embed_one()` 반환 타입/차원, `embed_batch()` 일관성 (cosine similarity > 0.999)
- **버그 발견 및 수정**: OpenAI API 비결정성으로 batch vs individual 결과가 미세하게 다름 (max abs diff ~0.00012). `rtol=1e-5` 기반 검증을 cosine similarity > 0.999 검증으로 변경

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
| GT 검증 스크립트 | `scripts/verify_ground_truth.py` | - |
| Seed Set | `data/ground_truth/seed_set.jsonl` (80 엔트리) | - |
| Synthetic GT | `data/ground_truth/synthetic.jsonl` (838 엔트리) | - |

**Seed Set 구성** (80개):
- 8 카테고리 × 10개 = 80 엔트리
- 난이도 분포: Easy 4 : Medium 4 : Hard 2
- 5개 서버: `EthanHenrickson/math-mcp`, `@anthropic/claude-code`, `@smithery-ai/github`, `@anthropic/fetch-mcp`, `@anthropic/filesystem-mcp`

**Synthetic GT 구성** (838개, 2026-03-26 생성):
- 8개 서버, 89개 도구 × ~10 쿼리 (일부 validation 실패로 skip)
- 난이도 분포: Easy 42.5%, Medium 40.6%, Hard 16.9% (seed 대비 QualityGate PASS)
- Tool name leakage: 실질 위반 0건 (짧은 도구명 오탐만 존재)
- Seed + Synthetic merge 시 query_id 중복 없음 (총 918개)

**추가된 엣지 케이스 테스트**:
- non-list JSON 반환 시 빈 결과
- hard + low ambiguity + 대안 도구 없음 → 스킵
- medium ambiguity + 대안 도구 없음 → low로 다운그레이드
- LLM 호출 실패 시 해당 도구만 스킵, 나머지 계속 생성
- `created_at` 미지정 시 `date.today()` 자동 사용
- easy 난이도 → 도구명 누출(leakage) 체크 면제

**미커버 (2 lines)**: `GroundTruthEntry` 생성 시 Pydantic validation except 분기 (line 269-270) — 정상 데이터에서 발생 불가

### Phase 5: 평가 하네스 — 완료

| 산출물 | 파일 | 커버리지 |
|--------|------|----------|
| 메트릭 순수 함수 + dataclass | `src/evaluation/metrics.py` | **100%** |
| evaluate() 비동기 오케스트레이터 | `src/evaluation/harness.py` | **100%** |
| 메트릭 단위 테스트 (31개) | `tests/evaluation/test_metrics.py` | - |
| 하네스 통합 테스트 (9개) | `tests/evaluation/test_harness.py` | - |

**구현된 7개 메트릭**:
- Precision@1 (North Star)
- Recall@K
- MRR (Mean Reciprocal Rank)
- NDCG@5 (Graded relevance: correct=2, alternative=1)
- Confusion Rate (confusion vs miss 분류 — 에러 없을 시 `nan`)
- ECE (Expected Calibration Error, gap-based confidence)
- Latency (p50 / p95 / p99 / mean)

**설계 원칙**:
- `metrics.py`: 순수 함수만, I/O 없음, 독립 단위 테스트 가능
- `harness.py`: async 오케스트레이터, `strategy.search()` 1회/쿼리 호출, `compute_confidence()`로 신뢰도 추출
- `asyncio_mode="auto"` 활용 — `@pytest.mark.asyncio` 불필요

---

## 인프라 현황

### 연결된 외부 서비스

| 서비스 | 상태 | 검증 방식 |
|--------|------|-----------|
| **Qdrant Docker** | 실행 중 (`localhost:6333`) | 통합 테스트 11개 통과 |
| **Smithery Registry** | 연결 완료 (`registry.smithery.ai`) | 통합 테스트 8개 통과 |
| **OpenAI API** | 연결 완료 (임베딩 + Synthetic GT) | 통합 테스트 6개 통과 |

### 미연결 외부 서비스

| 서비스 | 용도 | 비용 | Phase |
|--------|------|------|-------|
| Cohere API | Reranker (`Rerank 3`) | Free tier | Phase 6 |
| Langfuse | LLM 트레이싱 | 무료 | Phase 11 |
| W&B | 실험 추적 | 무료 (개인) | Phase 10 |

---

## 테스트 현황

```
233 passed, 0 skipped
전체 커버리지: 98.56%
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
├── evaluation/            # 평가 하네스 테스트 (40개) — Phase 5
│   ├── test_metrics.py    # 7개 메트릭 순수 함수 단위 테스트 (31개)
│   └── test_harness.py    # evaluate() 오케스트레이터 통합 테스트 (9개)
└── integration/           # 통합 테스트 (28개) — 실제 서비스 연동
    ├── test_qdrant_integration.py     # 실제 Qdrant Docker
    ├── test_smithery_integration.py   # 실제 Smithery API
    └── test_openai_integration.py     # 실제 OpenAI API
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
| `embedding/openai_embedder.py` | 79% | exception 경로만 미커버 (통합 테스트 PASS) |

### 스킵된 테스트

스킵 테스트 없음 (2026-03-25 OpenAI API 키 설정 완료로 전부 해소).

---

## 주요 변경 사항 (이번 세션)

### 0. OpenAI API 통합 테스트 활성화 (2026-03-25)
- **변경**: `.env`에 `OPENAI_API_KEY` 추가, `tests/conftest.py`에 `load_dotenv()` 추가
- **결과**: skip 6개 → 0개, 전체 193 passed
- **버그 수정**: `test_batch_matches_individual`에서 OpenAI API 비결정성 대응 — `rtol=1e-5` 기반 검증을 cosine similarity > 0.999로 변경
- **교훈**: 외부 API의 비결정성을 고려한 테스트 설계 필요 (exact match 대신 semantic equivalence 검증)

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

### 5. Synthetic GT 생성 + 검증 (2026-03-26)
- **Synthetic GT 생성**: `scripts/generate_ground_truth.py` 실행 → 838개 엔트리 생성
  - 8개 서버, 89개 도구, gpt-4o-mini로 Tool당 10개 쿼리 생성
  - 난이도 분포: Easy 42.5%, Medium 40.6%, Hard 16.9% (QualityGate PASS)
  - 52개 엔트리 validation skip (hard + low ambiguity 조합)
- **스크립트 보강**: `generate_ground_truth.py`에 dotenv 로드 + tool name leakage 검사 추가
- **검증 스크립트**: `scripts/verify_ground_truth.py` 신규 작성
  - 통계, QualityGate, 샘플, merge 검증, data integrity 5단계 검증
  - Verdict: PASS
- **pyproject.toml**: scripts/ 디렉토리에 E402 (import order) ruff 예외 추가

---

## Git 히스토리

| PR | 브랜치 | 내용 |
|----|--------|------|
| #1 | `feat/core-pipeline` | Phase 0~3 (기반, 데이터, 임베딩, 파이프라인) |
| #2 | `feat/ground-truth` | Phase 4 (Ground Truth 생성) |

---

## 다음 단계

### 우선순위 1: Description Optimizer disambiguation 재설계
1. ~~**논문 리서치**~~ — 완료 (`description_optimizer/docs/research-phase2-synthesis.md`)
2. ~~**GEO-P@1 근본원인 분석**~~ — 완료 (`docs/analysis/description-optimizer-root-cause-analysis.md`)
3. ~~**Retrieval 경로 재정렬 + 3-way A/B**~~ — 완료 (search/optimized 모두 δP@1=-0.069, sibling 오염 확인)
4. **disambiguation 재설계** — sibling 이름 제거, target-only qualifier 중심
5. **3-way A/B 재검증** — disambiguation 개선 후 original vs optimized vs search 재평가
6. **GEO diagnostic 전환** — hard gate에서 제외

### 우선순위 2: 기존 파이프라인 진행
1. **OQ-2: 임베딩 인덱스 빌드** — `scripts/collect_data.py` + `scripts/build_index.py --pool-size 50`으로 Pool 50 인덱싱
2. **E0 실험** — `evaluate(flat_strategy, gt_queries)` vs `evaluate(sequential_strategy, gt_queries)` 비교

### 백로그

| 우선순위 | 항목 | 상태 |
|---------|------|------|
| ~~높음~~ | ~~GEO Scorer 개선 리서치~~ | **완료** (근본원인 분석으로 대체) |
| ~~높음~~ | ~~Grounded Optimization 구현 (10 tasks)~~ | **완료** (2026-03-29) |
| ~~높음~~ | ~~`openai_embedder.py` 통합 테스트 활성화~~ | **완료** |
| ~~높음~~ | ~~Synthetic GT 생성 실행~~ — 838개 생성 | **완료** |
| ~~높음~~ | ~~Retrieval 경로 재정렬 + 3-way A/B 평가~~ | **완료** (sibling 오염 확인) |
| **높음** | disambiguation 재설계 (sibling 이름 제거) → 3-way A/B 재검증 | **대기** |
| **높음** | GEO diagnostic 전환 | 대기 |
| 높음 | 임베딩 인덱스 빌드 (`scripts/build_index.py`) | 대기 |
| 중간 | E0 실험: 1-Layer vs 2-Layer 검증 | Phase 5 완료 후 |
| ~~중간~~ | ~~Precision@1 end-to-end 평가~~ | **완료** (δP@1=-0.069) |
