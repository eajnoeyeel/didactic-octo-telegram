"""Tests for Settings configuration."""

from config import Settings


class TestSettings:
    def test_default_qdrant_url(self):
        settings = Settings()
        assert settings.qdrant_url == "http://localhost:6333"

    def test_default_confidence_gap_threshold(self):
        settings = Settings()
        assert settings.confidence_gap_threshold == 0.15

    def test_default_top_k_retrieval(self):
        settings = Settings()
        assert settings.top_k_retrieval == 10

    def test_default_top_k_rerank(self):
        settings = Settings()
        assert settings.top_k_rerank == 3

    def test_default_embedding_model(self):
        settings = Settings()
        assert settings.embedding_model == "text-embedding-3-small"

    def test_default_embedding_dimension(self):
        settings = Settings()
        assert settings.embedding_dimension == 1536

    def test_default_smithery_api_base_url(self):
        settings = Settings()
        assert settings.smithery_api_base_url == "https://registry.smithery.ai"

    def test_default_qdrant_collection_name(self):
        settings = Settings()
        assert settings.qdrant_collection_name == "mcp_tools"

    def test_optional_fields_default_none(self):
        settings = Settings()
        assert settings.openai_api_key is None
        assert settings.qdrant_api_key is None
        assert settings.cohere_api_key is None
        assert settings.langfuse_public_key is None
        assert settings.langfuse_secret_key is None
