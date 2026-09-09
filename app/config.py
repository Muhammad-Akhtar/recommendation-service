from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://redis:6379"
    redis_timeout: float = 1
    cache_ttl: int = 120

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "recommendations"
    postgres_user: str = "recommendation_user"
    postgres_password: str = "recommendation_password"

    kafka_bootstrap_servers: str = "kafka:29092"
    kafka_topic: str = "user-interactions"
    kafka_consumer_group: str = "recommendation-service"

    # Apicurio Registry Confluent-compatible API (ccompat v7)
    schema_registry_url: str = "http://schema-registry:8080/apis/ccompat/v7"
    kafka_value_subject: str = "user-interactions-value"

    # Active recommendation model version (Task 19)
    model_version: str = "v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
