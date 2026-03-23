"""Application settings via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Smithery
    smithery_api_base_url: str = "https://registry.smithery.ai"

    # OpenAI (required for Phase 2 embedding, optional for Phase 1 crawling)
    openai_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection_name: str = "mcp_tools"

    # Cohere (Phase 3+)
    cohere_api_key: str | None = None

    # Retrieval
    top_k_retrieval: int = 10
    top_k_rerank: int = 3
    confidence_gap_threshold: float = 0.15

    # Langfuse
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
