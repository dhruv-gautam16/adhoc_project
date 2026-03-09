"""
config.py
Reads all environment variables from .env and exposes them
as a typed settings object available across the entire app.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o"

    # ChromaDB
    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "codebase_knowledge"

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Ingestion
    REPOS_DIR: str = "/app/repos"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    MAX_FILE_SIZE_KB: int = 500

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Single importable instance used across the app
settings = get_settings()