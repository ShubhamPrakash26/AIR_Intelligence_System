"""Embedding generation for clinical incidents."""

from src.embeddings.engine import EmbeddingEngine
from src.embeddings.models import EmbeddingResult, get_model_dimension

__all__ = ["EmbeddingEngine", "EmbeddingResult", "get_model_dimension"]
