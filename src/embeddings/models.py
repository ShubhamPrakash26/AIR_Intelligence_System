"""Embedding result types and model dimension registry."""

from __future__ import annotations

from dataclasses import dataclass


# Known output dimensions for supported embedding models.
# BGE-M3 encodes text into 1024-dimensional dense vectors.
SUPPORTED_MODELS: dict[str, int] = {
    "BAAI/bge-m3": 1024,
    "BAAI/bge-large-en-v1.5": 1024,
    "BAAI/bge-base-en-v1.5": 768,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "sentence-transformers/all-mpnet-base-v2": 768,
}

DEFAULT_DIMENSION = 1024


def get_model_dimension(model_name: str) -> int:
    """Return the output vector dimension for a supported model.

    Falls back to DEFAULT_DIMENSION (1024) for unknown models.
    """
    return SUPPORTED_MODELS.get(model_name, DEFAULT_DIMENSION)


@dataclass
class EmbeddingResult:
    """Output of embedding a single incident.

    Attributes:
        incident_id: The incident UUID this vector represents.
        text: The full text string that was embedded.
        vector: Dense float vector produced by the model.
        model_name: Name of the sentence-transformers model used.
        dimension: Expected vector dimension for validation.
    """

    incident_id: str
    text: str
    vector: list[float]
    model_name: str
    dimension: int

    def __post_init__(self) -> None:
        if not self.vector:
            raise ValueError("vector must not be empty")
        if len(self.vector) != self.dimension:
            raise ValueError(
                f"Vector dimension mismatch for incident {self.incident_id}: "
                f"expected {self.dimension}, got {len(self.vector)}"
            )
