"""OpenAI text-embedding-3-small embedder implementation."""

import numpy as np
from openai import AsyncOpenAI

from embedding.base import Embedder


class OpenAIEmbedder(Embedder):
    """Embedder using OpenAI's text-embedding API."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
    ) -> None:
        self.model = model
        self.dimension = dimension
        self._client = AsyncOpenAI(api_key=api_key)

    async def embed_one(self, text: str) -> np.ndarray:
        response = await self._client.embeddings.create(
            input=[text], model=self.model,
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    async def embed_batch(self, texts: list[str], batch_size: int = 50) -> list[np.ndarray]:
        all_vectors: list[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self._client.embeddings.create(
                input=batch, model=self.model,
            )
            vectors = [
                np.array(item.embedding, dtype=np.float32) for item in response.data
            ]
            all_vectors.extend(vectors)
        return all_vectors
