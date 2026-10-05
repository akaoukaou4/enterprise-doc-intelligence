import logging
from functools import lru_cache

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings, get_settings
from app.core.errors import ExternalServiceError, NotFoundError

logger = logging.getLogger(__name__)

_MISSING_KEY_CODES = {"NoSuchKey", "NotFound", "404"}


@lru_cache
def _build_client() -> BaseClient:
    """Create the S3 client once.

    Locally, MINIO_ENDPOINT points boto3 at MinIO. When it is not set,
    boto3 talks to real Amazon S3 using its default credential chain
    (IAM role on EC2), so the same code runs on AWS.
    """
    settings = get_settings()
    kwargs: dict = {
        "service_name": "s3",
        "region_name": "us-east-1",
        # MinIO needs path-style URLs: http://host:9000/bucket/key
        "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    }
    if settings.minio_endpoint:
        kwargs["endpoint_url"] = settings.minio_endpoint
    if settings.minio_access_key and settings.minio_secret_key:
        kwargs["aws_access_key_id"] = settings.minio_access_key
        kwargs["aws_secret_access_key"] = settings.minio_secret_key
    return boto3.client(**kwargs)


class StorageService:
    """Upload, download and delete files in object storage (MinIO / S3)."""

    def __init__(self, settings: Settings, client: BaseClient | None = None) -> None:
        self._bucket = settings.minio_bucket
        self._client = client if client is not None else _build_client()

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._failure("upload", key, exc) from exc

    def download(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _MISSING_KEY_CODES:
                raise NotFoundError(f"File not found in storage: {key}") from exc
            raise self._failure("download", key, exc) from exc
        except BotoCoreError as exc:
            raise self._failure("download", key, exc) from exc

    def delete(self, key: str) -> None:
        # S3 delete is idempotent: deleting a missing key is not an error.
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise self._failure("delete", key, exc) from exc

    @staticmethod
    def _failure(operation: str, key: str, exc: Exception) -> ExternalServiceError:
        # Full details go to the server log; the client gets a generic message.
        logger.error("Storage %s failed for key %s: %s", operation, key, exc)
        return ExternalServiceError("Object storage request failed.")
