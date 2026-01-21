from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration
    openai_api_key: str = ""
    zhipuai_api_key: str = ""
    qwen_api_key: str = ""
    base_url: str = ""
    qwen_base_url: str = ""
    default_llm: str = ""
    qwen_model_name: str = ""

    # MySQL Configuration
    mysql_host: str = "localhost"
    mysql_port: int = 3307
    mysql_user: str = ""
    mysql_password: str = ""
    mysql_database: str = ""

    # PostgreSQL Configuration
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "kodi"
    pg_password: str = ""
    pg_database: str = "ttd"

    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # Application Settings
    max_query_results: int = 1000
    query_timeout: int = 30
    session_ttl: int = 3600

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()