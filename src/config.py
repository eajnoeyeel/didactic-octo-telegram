"""Application settings via pydantic-settings."""

from pydantic import Field
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
    cohere_rerank_model: str = "rerank-v3.5"

    # Retrieval
    top_k_retrieval: int = 10
    top_k_rerank: int = 3
    confidence_gap_threshold: float = 0.15

    # External data (ADR-0011)
    external_data_dir: str = "data/external"

    # Composite scoring weights (PD7). MLP: w2=w3=0 (relevance only).
    score_weight_relevance: float = Field(1.0, description="Weight for relevance score")
    score_weight_quality: float = Field(0.0, description="Weight for quality score (GEO)")
    score_weight_boost: float = Field(0.0, description="Weight for boost score")

    # Langfuse
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
