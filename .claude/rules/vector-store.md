# Vector Store Rules — Qdrant Cloud

## Qdrant Client Usage

```python
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
)

client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
```

- **AsyncQdrantClient only**: 한 프로세스에 하나, DI로 전달
- **Free tier**: 1GB (약 40K tools 수용)

## Collection Design

| Collection | 용도 | Vector Dimension |
|------------|------|-----------------|
| `mcp_servers` | Server-level embedding | 모델 의존 (1536 or 1024) |
| `mcp_tools` | Tool-level embedding | 모델 의존 |

```python
await client.create_collection(
    collection_name="mcp_tools",
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
)
```

## Upsert Pattern

```python
points = [
    PointStruct(
        id=abs(hash(tool.tool_id)) % (2**63),
        vector=vector.tolist(),
        payload={
            "tool_id": tool.tool_id,
            "server_id": tool.server_id,
            "tool_name": tool.tool_name,
            "description": tool.description,
        },
    )
    for tool, vector in zip(tools, vectors)
]
await client.upsert(collection_name=collection, points=points)
```

- **ID**: `abs(hash(tool_id)) % (2**63)` — deterministic, upsert-safe
- **Payload**: 검색 결과 재구성에 필요한 필드만 저장

## Search Pattern

```python
results = await client.search(
    collection_name="mcp_tools",
    query_vector=query_vector.tolist(),
    limit=top_k,
    query_filter=Filter(
        must=[FieldCondition(key="server_id", match=MatchValue(value=server_id))]
    ) if server_id else None,
)
```

- `server_id` 필터: Sequential Strategy의 Layer 2에서 사용
- Top-K: config의 `top_k_retrieval` (기본 10)

## Embedding Text Format

```python
def build_tool_text(tool: MCPTool) -> str:
    return f"{tool.tool_name}: {tool.description}"

def build_server_text(server: MCPServer) -> str:
    return f"{server.name}: {server.description}"
```

## Batch Indexing

```python
async def index_tools(tools: list[MCPTool], embedder: Embedder, batch_size: int = 50):
    for i in range(0, len(tools), batch_size):
        batch = tools[i:i + batch_size]
        texts = [build_tool_text(t) for t in batch]
        vectors = await embedder.embed_batch(texts)
        await qdrant.upsert_tools(batch, vectors)
```

## Testing

- Unit tests: mock `AsyncQdrantClient`, assert upsert/search 호출
- Integration tests: `@pytest.mark.skipif(not os.getenv("QDRANT_URL"))` 로 guard
- Payload 변환 함수(`_tool_to_payload`, `_build_tool_text`)는 순수 함수 — 별도 단위 테스트
