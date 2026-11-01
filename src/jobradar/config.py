from functools import lru_cache

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Real environment variables take precedence over .env, which is how
    # docker-compose.yml points the api container at db:5432.
    # extra="ignore": .env also holds the POSTGRES_* variables for the db service.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: PostgresDsn


@lru_cache
def get_settings() -> Settings:
    return Settings()
