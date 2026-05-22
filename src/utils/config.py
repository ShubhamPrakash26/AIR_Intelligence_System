"""Configuration management for the AIR system."""

from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """

    # Application
    app_name: str = "AIR Clinical Incident Intelligence Engine"
    app_version: str = "1.0.0"
    debug: bool = False

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False

    # LLM Configuration
    openai_api_key: str | None = None
    llm_model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2000

    # Embedding Configuration
    embedding_model: str = "BAAI/bge-m3"
    embedding_batch_size: int = 32

    # Vector Store Configuration
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection_name: str = "incidents"

    # Data Paths
    data_dir: Path = Path("data")
    input_dir: Path = Path("data/input")
    output_dir: Path = Path("data/processed")
    embeddings_dir: Path = Path("data/embeddings")

    # Processing
    batch_size: int = 32
    num_workers: int = 4

    # Validation
    confidence_threshold: float = 0.7
    validation_retries: int = 3

    # Persistence
    enable_persistence: bool = False
    database_url: str = "sqlite:///./air.db"

    # Clustering
    clustering_algorithm: str = "hdbscan"
    min_cluster_size: int = 5
    min_samples: int = 5

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


# Global settings instance
settings = Settings()
