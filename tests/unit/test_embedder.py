"""Tests for Embedder ABC and OpenAIEmbedder."""

import inspect
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from embedding.base import Embedder


class TestEmbedderABC:
    def test_is_abstract(self):
        assert inspect.isabstract(Embedder)

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Embedder()

    def test_has_embed_one(self):
        assert hasattr(Embedder, "embed_one")

    def test_has_embed_batch(self):
        assert hasattr(Embedder, "embed_batch")
