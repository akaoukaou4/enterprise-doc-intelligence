from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Enterprise Doc Intelligence"
    app_version: str = "0.1.0"
    app_env: str = "development"  # reads APP_ENV
    debug: bool = False  # reads DEBUG
    log_level: str = "INFO"  # reads LOG_LEVEL

    # extra="ignore": .env also holds DATABASE_URL, MINIO_*, etc.
    # We model them as each phase needs them.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
