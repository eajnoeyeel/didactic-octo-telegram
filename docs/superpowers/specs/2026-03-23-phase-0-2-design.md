# Phase 0-2 구현 설계: Foundation, Data Collection, Embedding & Vector Store

> 작성일: 2026-03-23
> 상위 문서: `docs/plan/phase-0-2.md`, `docs/design/architecture.md`
> 접근 방식: Approach B — Async Pipeline with Staged Crawling

---

## 1. 목적

MCP Discovery Platform의 코드 기반을 구축한다. Phase 0-2는 다음을 포함한다:

- **Phase 0**: 프로젝트 스켈레톤 (의존성, 설정, 데이터 모델)
- **Phase 1**: Smithery Registry 크롤링을 통한 MCP 서버/도구 데이터 수집
- **Phase 2**: 도구 설명 임베딩 + Qdrant 벡터 인덱스 구축

Phase 2 완료 시 "쿼리 → 벡터 검색 → 유사 도구 반환"이 가능한 상태가 된다.

---

## 2. 기존 설계 대비 변경 사항

Smithery API 실제 동작 분석(2026-03-23)을 통해 기존 설계 문서와의 6가지 불일치를 발견하고 수정한다.

### R1: Smithery List vs Detail API 불일치

**문제**: `docs/plan/phase-0-2.md`의 `parse_server(raw) → MCPServer`는 list endpoint 응답에서 tools까지 파싱할 수 있다고 가정. 실제로는:
- **List** (`GET /servers?page=N&pageSize=50`): 서버 메타데이터만 반환 (qualifiedName, displayName, description, useCount, verified, isDeployed). **tools 없음**.
- **Detail** (`GET /servers/{qualifiedName}`): 전체 데이터 반환 (tools 배열 포함, 각 tool에 name, description, inputSchema).

**해결**: Crawler를 3개 모듈로 분리:
- `smithery_client.py` — HTTP 클라이언트 (list + detail 엔드포인트)
- `server_selector.py` — 필터링/큐레이션 로직
- `crawler.py` — 오케스트레이터 (client → selector → detail fetch)

### R2: tool_id 구분자 `/` 모호성

**문제**: 설계의 `tool_id = "{server_id}/{tool_name}"` 형식에서 Smithery qualifiedName에 `/`가 포함됨 (예: `@smithery-ai/github`). `@smithery-ai/github/search_issues`는 파싱 불가.

**해결**: 구분자를 `::` 로 변경. `@smithery-ai/github::search_issues`는 명확히 파싱 가능.
- `TOOL_ID_SEPARATOR = "::"` 상수를 `models.py`에 정의, 전체 코드에서 참조.
- 하류 문서(ground-truth-schema.md 등) 모두 업데이트.

### R3: Qdrant Point ID 비결정적

**문제**: `abs(hash(tool_id)) % (2**63)` — Python `hash()`는 `PYTHONHASHSEED`에 의해 실행마다 달라짐. 재인덱싱 시 동일 tool에 다른 ID가 생성되어 중복 point 발생.

**해결**: `uuid.uuid5(MCP_DISCOVERY_NAMESPACE, tool_id)` 사용.
- 결정적 (동일 입력 → 동일 UUID)
- Qdrant가 UUID point ID 네이티브 지원
- 충돌 확률 사실상 0

### R4: 크롤링 범위 선택 기준

**문제**: DP7은 50-100 서버 큐레이션이지만, 4034개에서 어떻게 선택할지 미정.

**해결**: 3단계 필터링:
1. `is:deployed` 필터 (실제 운영 중인 서버만)
2. `useCount` 내림차순 정렬 (인기 기반)
3. 큐레이션 리스트 파일(`data/curation/selected_servers.txt`) 지원 (수동 오버라이드)

### R5: MCP Direct Connector 범위 축소

**문제**: Phase 1에 `mcp_connector.py`(직접 JSON-RPC `tools/list` 호출)가 포함되어 있지만, Smithery detail endpoint가 이미 tool 데이터를 제공. 자체 MCP 서버(OQ-3)는 Phase 4+.

**해결**: Phase 1에서는 인터페이스 정의 + mock 테스트만 구현. `scripts/collect_data.py`는 SmitheryCrawler만 사용.

### R6: MCPTool의 parameters / input_schema 중복

**문제**: MCPTool에 `parameters`와 `input_schema` 두 필드가 존재. 어떤 것이 SOT(Source of Truth)인지 불명확.

**해결**: `input_schema: dict | None`만 유지. `parameter_names` computed property로 파라미터 이름 목록 제공.

---

## 3. Phase 0: Project Foundation

### 3.1 프로젝트 스켈레톤

```
mcp-discovery/
├── pyproject.toml
├── .env.example
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── data/__init__.py
│   ├── embedding/__init__.py
│   └── retrieval/__init__.py
└── tests/
    └── unit/
        ├── test_config.py
        └── test_models.py
```

**pyproject.toml**:
- Python >= 3.12
- dependencies: fastapi, uvicorn, pydantic, pydantic-settings, qdrant-client, openai, httpx, python-dotenv, langfuse, wandb, scipy, numpy
- dev: pytest, pytest-asyncio, pytest-cov, ruff
- `[tool.pytest.ini_options]`: asyncio_mode="auto", testpaths=["tests"], pythonpath=["src"]

### 3.2 Settings (`src/config.py`)

`BaseSettings` + `SettingsConfigDict(env_file=".env", extra="ignore")`.

| 필드 | 기본값 | 용도 |
|------|--------|------|
| smithery_api_base_url | "https://registry.smithery.ai" | Smithery API |
| openai_api_key | (필수) | 임베딩 |
| embedding_model | "text-embedding-3-small" | 임베딩 모델 |
| embedding_dimension | 1536 | 벡터 차원 |
| qdrant_url | "http://localhost:6333" | Qdrant |
| qdrant_api_key | None | Qdrant Cloud |
| qdrant_collection_name | "mcp_tools" | 컬렉션 이름 |
| cohere_api_key | None | Reranker (Phase 3+) |
| top_k_retrieval | 10 | 검색 상위 K |
| top_k_rerank | 3 | 리랭킹 상위 K |
| confidence_gap_threshold | 0.15 | 신뢰도 분기 임계값 |
| langfuse_public_key | None | 트레이싱 |
| langfuse_secret_key | None | 트레이싱 |

### 3.3 데이터 모델 (`src/models.py`)

**상수**:
```python
TOOL_ID_SEPARATOR = "::"
```

**MCPServerSummary** (신규 — Smithery list endpoint용):
```python
class MCPServerSummary(BaseModel):
    qualified_name: str
    display_name: str
    description: str | None = None
    use_count: int = 0
    is_verified: bool = False
    is_deployed: bool = False
```

**MCPServer**:
```python
class MCPServer(BaseModel):
    server_id: str           # Smithery qualifiedName
    name: str                # displayName
    description: str | None = None
    homepage: str | None = None
    tools: list["MCPTool"] = []
```

**MCPTool** (수정):
```python
class MCPTool(BaseModel):
    server_id: str           # 필드 순서 중요: validator가 참조하는 필드를 먼저 정의
    tool_name: str
    tool_id: str             # "{server_id}::{tool_name}" — server_id, tool_name 뒤에 위치
    description: str | None = None
    input_schema: dict | None = None

    @computed_field
    @property
    def parameter_names(self) -> list[str]:
        """input_schema에서 파라미터 이름 추출. 향후 required 필드 구분 등 확장 가능."""
        if not self.input_schema:
            return []
        props = self.input_schema.get("properties", {})
        return list(props.keys())

    @field_validator("tool_id")
    @classmethod
    def validate_tool_id(cls, v, info):
        server_id = info.data.get("server_id", "")
        tool_name = info.data.get("tool_name", "")
        expected = f"{server_id}{TOOL_ID_SEPARATOR}{tool_name}"
        if v != expected:
            raise ValueError(f"tool_id must be '{expected}', got '{v}'")
        return v
```

> **주의**: Pydantic v2 `field_validator`는 필드 정의 순서대로 실행된다. `server_id`와 `tool_name`이 `tool_id`보다 먼저 정의되어야 validator에서 참조 가능하다.

**SearchResult, FindBestToolRequest, FindBestToolResponse, GroundTruthEntry**: 기존 `docs/plan/phase-0-2.md` 설계 유지. tool_id 구분자만 `::` 적용.

### 3.4 TDD 순서
1. `tests/unit/test_config.py`: Settings() defaults 검증
2. `tests/unit/test_models.py`: 모든 모델 인스턴스화 + tool_id validator 검증
3. 구현 후 `uv run pytest tests/unit/ -v` PASS

### 3.5 완료 기준
- [ ] `uv run pytest tests/unit/test_config.py tests/unit/test_models.py -v` PASS
- [ ] 모든 모델 import 가능
- [ ] 커밋: `feat: project foundation — config, models, deps`

---

## 4. Phase 1: Data Collection

### 4.1 파일 구조

```
src/data/
├── __init__.py
├── smithery_client.py    # Smithery Registry API 클라이언트
├── server_selector.py    # 서버 필터링/큐레이션
├── crawler.py            # 크롤링 오케스트레이터
└── mcp_connector.py      # Direct MCP 연결 (인터페이스만)

scripts/
└── collect_data.py       # 크롤링 실행 CLI

data/
├── raw/
│   └── servers.jsonl     # 크롤링 결과
└── curation/
    ├── candidates.jsonl      # 필터링 전 후보 (옵션)
    └── selected_servers.txt  # 큐레이션된 서버 (옵션)
```

### 4.2 SmitheryClient (`src/data/smithery_client.py`)

Smithery Registry API와의 모든 HTTP 통신을 담당한다.

```python
class SmitheryClient:
    def __init__(self, base_url: str, rate_limit_seconds: float = 0.5):
        """
        Args:
            base_url: Smithery Registry API base URL
            rate_limit_seconds: 요청 간 최소 대기 시간
        """

    async def fetch_server_list(
        self, page: int = 1, page_size: int = 50
    ) -> list[MCPServerSummary]:
        """List endpoint: 서버 메타데이터 목록 (tools 미포함)."""

    async def fetch_all_summaries(
        self, max_pages: int = 10
    ) -> list[MCPServerSummary]:
        """전체 서버 목록 페이지네이션.
        종료 조건: (1) max_pages 도달 또는 (2) 응답의 servers 배열이 빈 경우 또는
        (3) 응답의 pagination.currentPage >= pagination.totalPages.
        """

    async def fetch_server_detail(
        self, qualified_name: str
    ) -> MCPServer:
        """Detail endpoint: 서버 상세 + tools 배열."""

    @staticmethod
    def parse_server_summary(raw: dict) -> MCPServerSummary:
        """List endpoint 응답 → MCPServerSummary."""

    @staticmethod
    def parse_server_detail(raw: dict) -> MCPServer:
        """Detail endpoint 응답 → MCPServer (tools 포함)."""
```

**구현 세부사항**:
- `httpx.AsyncClient` 사용, timeout 30초
- rate limiting: `asyncio.sleep(rate_limit_seconds)` between requests
- 429/5xx 재시도: exponential backoff (1s, 2s, 4s), max 3회
- detail 파싱 시 tool_id 생성: `f"{qualified_name}{TOOL_ID_SEPARATOR}{tool['name']}"`

### 4.3 ServerSelector (`src/data/server_selector.py`)

크롤링 대상 서버 선택 로직을 캡슐화한다.

```python
def filter_deployed(
    summaries: list[MCPServerSummary],
) -> list[MCPServerSummary]:
    """is_deployed=True인 서버만 반환."""

def sort_by_popularity(
    summaries: list[MCPServerSummary],
) -> list[MCPServerSummary]:
    """use_count 내림차순 정렬."""

def load_curated_list(path: Path) -> list[str]:
    """텍스트 파일에서 qualifiedName 목록 로드 (한 줄에 하나)."""

def select_servers(
    summaries: list[MCPServerSummary],
    curated_list: Path | None = None,
    max_servers: int = 100,
    require_deployed: bool = True,
) -> list[MCPServerSummary]:
    """
    서버 선택 파이프라인:
    1. curated_list 있으면 해당 목록만 필터
    2. 없으면: deployed 필터 → popularity 정렬 → max_servers 잘라내기
    """
```

### 4.4 SmitheryCrawler (`src/data/crawler.py`)

client와 selector를 조합하여 전체 크롤링 흐름을 실행한다.

```python
class SmitheryCrawler:
    def __init__(self, client: SmitheryClient):
        """client 주입."""

    async def crawl(
        self,
        max_pages: int = 10,
        curated_list: Path | None = None,
        max_servers: int = 100,
    ) -> list[MCPServer]:
        """
        크롤링 흐름:
        1. client.fetch_all_summaries(max_pages) → 전체 서버 목록
        2. select_servers(summaries, curated_list, max_servers) → 대상 선택
        3. 각 대상: client.fetch_server_detail(qualified_name) → MCPServer
        4. 진행률 로깅 ("Fetched 42/100 servers...")
        """

    def save(
        self,
        servers: list[MCPServer],
        output_dir: Path = Path("data/raw"),
    ) -> Path:
        """JSONL 형식으로 저장. 반환: 파일 경로."""

    @staticmethod
    def load(path: Path) -> list[MCPServer]:
        """JSONL 파일에서 MCPServer 목록 로드."""
```

### 4.5 MCPDirectConnector (`src/data/mcp_connector.py`) — 인터페이스만

Phase 1에서는 인터페이스 정의와 mock 기반 테스트만 구현한다.

```python
class MCPDirectConnector:
    async def fetch_tools(
        self, server_id: str, endpoint_url: str
    ) -> list[MCPTool]:
        """JSON-RPC tools/list 호출로 도구 목록 조회."""

    @staticmethod
    def parse_tools(server_id: str, response: dict) -> list[MCPTool]:
        """JSON-RPC 응답 → MCPTool 목록 파싱."""
```

### 4.6 Collection Script (`scripts/collect_data.py`)

```bash
uv run scripts/collect_data.py                          # 기본: top 100 deployed
uv run scripts/collect_data.py --server-list path.txt   # 큐레이션 목록
uv run scripts/collect_data.py --max-servers 50         # 서버 수 제한
uv run scripts/collect_data.py --max-pages 5            # 페이지 제한
```

### 4.7 테스트 전략

| 테스트 파일 | 범위 |
|------------|------|
| `test_smithery_client.py` | parse_server_summary, parse_server_detail (mock HTTP) |
| `test_server_selector.py` | filter_deployed, sort_by_popularity, select_servers |
| `test_crawler.py` | 크롤링 흐름 (mock client), save/load JSONL |
| `test_mcp_connector.py` | parse_tools (mock JSON-RPC response) |

### 4.8 TDD 순서
각 모듈은 **실패 테스트 작성 → 구현 → 통과 확인** 순서를 따른다. CLI 파싱은 argparse 사용.

### 4.9 완료 기준
- [ ] 모든 unit test PASS
- [ ] `scripts/collect_data.py --max-servers 10` 스모크 테스트 성공
- [ ] `data/raw/servers.jsonl` 생성 및 내용 확인
- [ ] 커밋: `feat: Smithery crawler with staged fetching` + `feat: MCP direct connector interface`

---

## 5. Phase 2: Embedding & Vector Store

### 5.1 파일 구조

```
src/embedding/
├── __init__.py
├── base.py               # Embedder ABC
└── openai_embedder.py    # OpenAI text-embedding-3-small

src/retrieval/
├── __init__.py
└── qdrant_store.py       # Qdrant Cloud wrapper

src/data/
└── indexer.py            # Batch embed + upsert 오케스트레이터

scripts/
└── build_index.py        # 인덱스 빌드 CLI
```

### 5.2 Embedder ABC (`src/embedding/base.py`)

```python
class Embedder(ABC):
    model: str
    dimension: int

    @abstractmethod
    async def embed_one(self, text: str) -> np.ndarray:
        """단일 텍스트 임베딩."""

    @abstractmethod
    async def embed_batch(
        self, texts: list[str], batch_size: int = 50
    ) -> list[np.ndarray]:
        """배치 텍스트 임베딩. batch_size 단위로 청킹."""
```

### 5.3 OpenAIEmbedder (`src/embedding/openai_embedder.py`)

- `AsyncOpenAI` 클라이언트
- model = `text-embedding-3-small`, dimension = 1536
- `embed_batch`: batch_size(기본 50) 단위로 청킹하여 API 호출
- 에러 처리: rate limit (429) 시 exponential backoff

### 5.4 QdrantStore (`src/retrieval/qdrant_store.py`)

```python
MCP_DISCOVERY_NAMESPACE = uuid.UUID("7f1b3d4e-2a5c-4b8f-9e6d-1c0a3f5b7d9e")

class QdrantStore:
    def __init__(
        self,
        client: AsyncQdrantClient,
        collection_name: str = "mcp_tools",
    ):
        """Qdrant Cloud 래퍼."""

    async def ensure_collection(self, dimension: int) -> None:
        """컬렉션 생성 (COSINE distance). 이미 존재하면 skip."""

    async def upsert_tools(
        self,
        tools: list[MCPTool],
        vectors: list[np.ndarray],
    ) -> None:
        """도구 + 벡터를 Qdrant에 upsert. UUID v5 point ID 사용."""

    async def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        server_id_filter: str | None = None,
    ) -> list[SearchResult]:
        """벡터 유사도 검색. server_id_filter로 특정 서버 내 검색 가능."""

    @staticmethod
    def build_tool_text(tool: MCPTool) -> str:
        """임베딩용 텍스트 생성.
        - description 있으면: "{tool_name}: {description}"
        - description 없으면: "{tool_name}" (description=None인 tool도 인덱싱 대상에 포함,
          단 build_index.py에서 경고 로깅)
        """

    @staticmethod
    def tool_to_payload(tool: MCPTool) -> dict:
        """Qdrant payload: tool_id, server_id, tool_name, description, input_schema."""

    @staticmethod
    def payload_to_tool(payload: dict) -> MCPTool:
        """Qdrant payload → MCPTool 역변환. search() 내부에서 사용."""

    @staticmethod
    def generate_point_id(tool_id: str) -> str:
        """결정적 UUID v5: uuid.uuid5(MCP_DISCOVERY_NAMESPACE, tool_id).
        MCP_DISCOVERY_NAMESPACE는 프로젝트 전용으로 무작위 생성된 고정 UUID.
        """
```

### 5.5 ToolIndexer (`src/data/indexer.py`)

```python
class ToolIndexer:
    def __init__(self, embedder: Embedder, store: QdrantStore):
        """embedder와 store를 조합."""

    async def index_tools(
        self, tools: list[MCPTool], batch_size: int = 50
    ) -> int:
        """
        인덱싱 흐름:
        1. QdrantStore.build_tool_text(tool) per tool → texts
        2. embedder.embed_batch(texts, batch_size)
        3. store.upsert_tools(tools, vectors)
        반환: 인덱싱된 도구 수.
        """
```

### 5.6 Build Index Script (`scripts/build_index.py`)

```bash
uv run scripts/build_index.py                              # 기본
uv run scripts/build_index.py --input data/raw/servers.jsonl
uv run scripts/build_index.py --batch-size 100
```

흐름: servers.jsonl 로드 → tools flatten → embed → upsert → "Indexed N tools from M servers" 출력.

### 5.7 테스트 전략

| 테스트 파일 | 범위 |
|------------|------|
| `test_embedder.py` | Embedder ABC, OpenAIEmbedder 인스턴스화 + model/dimension (mock) |
| `test_qdrant_store.py` | build_tool_text, tool_to_payload, payload_to_tool, generate_point_id |
| `test_indexer.py` | index_tools 흐름 (mock embedder + mock store) — 필수 |

Integration test (API 키 필요 시 skip):
- 실제 OpenAI embed → Qdrant upsert → search → SearchResult 반환

### 5.8 TDD 순서
각 모듈은 **실패 테스트 작성 → 구현 → 통과 확인** 순서를 따른다.

### 5.9 완료 기준
- [ ] 모든 unit test PASS
- [ ] `scripts/build_index.py` 실행 성공 (Qdrant Cloud 연결 필요)
- [ ] 커밋: `feat: Embedder abstraction + OpenAI embedder` + `feat: Qdrant vector store + indexer`

---

## 6. 위험 완화 계획

| 위험 | 완화 | 검증 | Fallback |
|------|------|------|----------|
| R1: List에 tools 없음 | 2단계 SmitheryClient | 10서버 스모크 테스트 | raw JSON 캐시 후 오프라인 재시도 |
| R2: `/` 모호성 | `::` 구분자 + `TOOL_ID_SEPARATOR` 상수 | Pydantic validator | `:::` triple colon |
| R3: hash() 비결정적 | UUID v5 + 고정 namespace | 중복 UUID assert | Qdrant auto UUID |
| R4: 크롤링 범위 미정 | deployed 필터 + popularity + 큐레이션 | 후보 목록 수동 리뷰 | verified 조건 완화 |
| R5: MCP connector 시기상조 | 인터페이스+mock만 | unit test PASS | Phase 4+에서 구현 |
| R6: 필드 중복 | input_schema만 + computed property | model test | to_parameters() 추가 |

| R7: Smithery API rate limit/IP 차단 | detail fetch 결과 점진적 저장 (1건씩 append), 중단 후 resume 지원 | 100서버 크롤링 완주 | rate_limit_seconds 증가 (0.5→1.0) |
| R8: Smithery API 스키마 변경 | parse_*에서 예상치 못한 필드/누락 시 경고 로깅 + 해당 서버 skip | 파싱 실패 서버 0건 확인 | 전체 크롤링 중단 방지 |

**추가 완화 조치**:
- Smithery API 장애 대비: 첫 성공 크롤링 결과(`servers.jsonl`)를 git에 커밋. Phase 2는 캐시 데이터로 진행 가능.
- `TOOL_ID_SEPARATOR` 하드코딩 금지: 전체 코드에서 상수 참조만 허용.
- `::` 구분자 충돌 가능성: Smithery qualifiedName은 `@`, `-`, `/`, 영숫자로 구성되고 MCP tool name은 영숫자+언더스코어. `::` 는 두 문자집합 모두에 포함되지 않으므로 충돌 불가.

**범위 결정 (ADR)**:
- Phase 2는 **Tool Index(`mcp_tools` 컬렉션)만** 생성한다. Server Index는 Phase 3(Sequential Strategy 구현 시) 또는 Phase 7(Hybrid Search 구현 시)에서 추가한다. 이는 의도적 범위 축소이며, architecture-diagrams.md의 2-Layer 다이어그램과의 차이를 인지하고 있다.

---

## 7. 설계 문서 업데이트 대상

| 문서 | 변경 내용 |
|------|----------|
| `docs/plan/phase-0-2.md` | 6가지 변경사항 전체 반영 (3파일 분리, :: 구분자, UUID v5 등) |
| `docs/design/code-structure.md` | `smithery_client.py`, `server_selector.py` 추가, `MCPServerSummary` 모델 추가 |
| `docs/design/architecture.md` | DP7에 크롤링 선택 기준 추가, tool_id 구분자 :: 명시 |
| `docs/design/ground-truth-schema.md` | tool_id 형식 `{server_id}::{tool_name}` 으로 업데이트 + JSON 예시 수정 |
| `docs/design/ground-truth-design.md` | correct_tool_id 형식 `::` 구분자 적용 |
| `docs/plan/implementation.md` | 공통 컨벤션의 tool_id 형식 `::` 구분자 적용 |

---

## 8. 의존성 & 실행 순서

```
Phase 0 (Day 1-2) — 외부 의존성 없음
  └─ pyproject.toml → config.py → models.py → tests

Phase 1 (Day 2-4) — Phase 0 models 의존 + Smithery API
  ├─ smithery_client.py → server_selector.py → crawler.py → collect_data.py
  └─ mcp_connector.py (병렬, 독립)

Phase 2 (Day 4-6) — Phase 0 config/models + Phase 1 data + OpenAI API + Qdrant Cloud
  └─ base.py → openai_embedder.py → qdrant_store.py → indexer.py → build_index.py
```

**병렬화**: Phase 2의 `base.py` + `openai_embedder.py`는 Phase 1 후반과 병렬 가능 (Phase 0 models만 의존).

---

## 9. End-to-End 검증

Phase 2 완료 후 전체 파이프라인 검증:

1. `uv run pytest tests/ -v` — 전체 unit test PASS
2. `uv run scripts/collect_data.py --max-servers 10` — 10개 서버 크롤링
3. `data/raw/servers.jsonl` 내용 확인 (서버 + tools 포함)
4. `uv run scripts/build_index.py --input data/raw/servers.jsonl` — Qdrant 인덱스 빌드
5. Integration test: search query → Qdrant 검색 → SearchResult 반환
