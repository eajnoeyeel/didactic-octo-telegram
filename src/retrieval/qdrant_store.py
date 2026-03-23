"""Qdrant Cloud vector store wrapper."""

import uuid

import numpy as np
from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from models import MCPTool, SearchResult

MCP_DISCOVERY_NAMESPACE = uuid.UUID("7f1b3d4e-2a5c-4b8f-9e6d-1c0a3f5b7d9e")


class QdrantStore:
    """Qdrant Cloud wrapper for MCP tool vectors."""

    def __init__(self, client: AsyncQdrantClient, collection_name: str = "mcp_tools") -> None:
        self.client = client
        self.collection_name = collection_name

    async def ensure_collection(self, dimension: int) -> None:
        collections = await self.client.get_collections()
        existing = [c.name for c in collections.collections]
        if self.collection_name in existing:
            logger.info(f"Collection '{self.collection_name}' already exists")
            return
        await self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
        )
        logger.info(f"Created collection '{self.collection_name}' (dim={dimension})")

    async def upsert_tools(self, tools: list[MCPTool], vectors: list[np.ndarray]) -> None:
        points = [
            PointStruct(
                id=self.generate_point_id(tool.tool_id),
                vector=vector.tolist(),
                payload=self.tool_to_payload(tool),
            )
            for tool, vector in zip(tools, vectors)
        ]
        await self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f"Upserted {len(points)} points to '{self.collection_name}'")

    async def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        server_id_filter: str | None = None,
    ) -> list[SearchResult]:
        query_filter = None
        if server_id_filter:
            query_filter = Filter(
                must=[FieldCondition(key="server_id", match=MatchValue(value=server_id_filter))]
            )
        results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector.tolist(),
            limit=top_k,
            query_filter=query_filter,
        )
        return [
            SearchResult(
                tool=self.payload_to_tool(hit.payload),
                score=hit.score,
                rank=i + 1,
            )
            for i, hit in enumerate(results)
        ]

    @staticmethod
    def build_tool_text(tool: MCPTool) -> str:
        if tool.description:
            return f"{tool.tool_name}: {tool.description}"
        return tool.tool_name

    @staticmethod
    def tool_to_payload(tool: MCPTool) -> dict:
        return {
            "tool_id": tool.tool_id,
            "server_id": tool.server_id,
            "tool_name": tool.tool_name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }

    @staticmethod
    def payload_to_tool(payload: dict) -> MCPTool:
        return MCPTool(
            server_id=payload["server_id"],
            tool_name=payload["tool_name"],
            tool_id=payload["tool_id"],
            description=payload.get("description"),
            input_schema=payload.get("input_schema"),
        )

    @staticmethod
    def generate_point_id(tool_id: str) -> str:
        return str(uuid.uuid5(MCP_DISCOVERY_NAMESPACE, tool_id))
