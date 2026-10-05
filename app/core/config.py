from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Enterprise Doc Intelligence"
    app_version: str = "0.1.0"
    app_env: str = "development"  # reads APP_ENV
    debug: bool = False  # reads DEBUG
    log_level: str = "INFO"  # reads LOG_LEVEL

    # reads DATABASE_URL. Optional so the app and tests can start without
    # a database (e.g. in CI); code that needs it fails with a clear message.
    database_url: str | None = None

    # Object storage (S3 API). MinIO locally, Amazon S3 on AWS.
    # Optional for the same reason as database_url.
    # minio_endpoint includes the scheme (http:// or https://), so no
    # separate "secure" flag is needed.
    minio_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_bucket: str = "documents"

    # Maximum accepted PDF size in megabytes. reads MAX_UPLOAD_MB
    max_upload_mb: int = 20

    # extra="ignore": .env also holds MINIO_SECURE, etc.
    # We model them as each phase needs them.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
