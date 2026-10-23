from functools import lru_cache

from pydantic import SecretStr
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

    # Hugging Face id of the embedding model. reads EMBEDDING_MODEL_ID.
    # The chunker's tokenizer and the embedding service both use this one
    # setting, so chunk size is always measured by the model that embeds it.
    # The database column is vector(768): another model needs the same size
    # or a new migration (the service checks this when the model loads).
    embedding_model_id: str = "google/embeddinggemma-300m"

    # Load the embedding model in the background when the API starts. reads
    # PRELOAD_EMBEDDING_MODEL. Off by default: tests and CI must never need the
    # gated model. Switch it on in your local .env (D-49).
    preload_embedding_model: bool = False

    # Gemini API (answer generation). reads GEMINI_API_KEY and GEMINI_MODEL.
    # The key is optional so the app, tests and CI start without it. It is a
    # SecretStr, so printing or logging the settings never shows the value;
    # code that needs it calls .get_secret_value().
    # The model name is a setting because models get retired and replaced.
    # Use a stable name, never a "-latest" alias or a preview model.
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"

    # extra="ignore": .env also holds MINIO_SECURE, etc.
    # We model them as each phase needs them.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
