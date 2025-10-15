"""
Configuration management for the RAG backend.
Supports both local and AWS deployment environments.
"""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Environment
    environment: str = Field(default="local", env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")

    # API Configuration
    api_title: str = "RAG Blog API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api"
    # CORS not needed - same origin via CloudFront (prod) and React proxy (local)

    # Data configuration
    data_source: str = Field(default="local", env="DATA_SOURCE")  # "local" or "s3"
    data_dir: str = Field(default="data", env="DATA_DIR")
    chunks_file: str = "chunks.json"
    embeddings_file: str = "embeddings.npy"
    metadata_file: str = "metadata.json"
    bm25_file: str = "bm25_index.pkl"

    # Content configuration
    content_dir: str = Field(default="content/posts", env="CONTENT_DIR")
    image_dir: str = Field(default="content/images", env="IMAGE_DIR")
    image_base_url: str = Field(default="/images", env="IMAGE_BASE_URL")

    # Embedding configuration
    embedding_provider: str = Field(default="local", env="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", env="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=384, env="EMBEDDING_DIMENSION")

    # LLM configuration
    llm_provider: str = Field(default="ollama", env="LLM_PROVIDER")
    llm_model: str = Field(default="llama3.2", env="LLM_MODEL")
    ollama_host: str = Field(default="http://localhost:11434", env="OLLAMA_HOST")

    # OpenRouter configuration
    openrouter_api_key: str = Field(default="", env="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="meta-llama/llama-3.2-3b-instruct", env="OPENROUTER_MODEL")
    openrouter_site_url: str = Field(default="https://donaldmcgillivray.com", env="OPENROUTER_SITE_URL")
    openrouter_app_name: str = Field(default="RAG Blog", env="OPENROUTER_APP_NAME")

    # AWS Configuration (for production)
    aws_region: str = Field(default="us-east-1", env="AWS_REGION")
    s3_bucket: Optional[str] = Field(default=None, env="S3_BUCKET")
    bedrock_model_id: str = Field(default="anthropic.claude-3-haiku-20240307-v1:0", env="BEDROCK_MODEL_ID")
    bedrock_embedding_model: str = Field(default="amazon.titan-embed-text-v1", env="BEDROCK_EMBEDDING_MODEL")

    # Search configuration
    search_top_k: int = Field(default=10, env="SEARCH_TOP_K")
    search_alpha: float = Field(default=0.7, env="SEARCH_ALPHA")  # Weight for dense retrieval
    search_rerank: bool = Field(default=True, env="SEARCH_RERANK")

    # Generation configuration
    generation_max_tokens: int = Field(default=2048, env="GENERATION_MAX_TOKENS")
    generation_temperature: float = Field(default=0.7, env="GENERATION_TEMPERATURE")
    generation_system_prompt: str = Field(
        default="""You are Donald McGillivray, author of technical blog posts about AI,
        software engineering, and system reliability. Generate content that maintains
        the technical depth and writing style from the source material.""",
        env="GENERATION_SYSTEM_PROMPT"
    )

    # Caching
    cache_ttl: int = Field(default=3600, env="CACHE_TTL")  # seconds
    enable_cache: bool = Field(default=True, env="ENABLE_CACHE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings


def is_production() -> bool:
    """Check if running in production environment."""
    return settings.environment == "production"


def is_local() -> bool:
    """Check if running in local environment."""
    return settings.environment == "local"
