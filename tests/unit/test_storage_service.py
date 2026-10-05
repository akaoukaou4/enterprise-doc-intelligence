import io

import pytest
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.core.errors import ExternalServiceError, NotFoundError
from app.services.storage import StorageService


class FakeS3Client:
    """Stands in for the boto3 client so tests need no MinIO and no network."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.last_put: dict = {}
        self.error: ClientError | None = None

    def put_object(self, **kwargs) -> None:
        if self.error:
            raise self.error
        self.last_put = kwargs
        self.objects[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, **kwargs) -> dict:
        if self.error:
            raise self.error
        key = kwargs["Key"]
        if key not in self.objects:
            raise _client_error("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[key])}

    def delete_object(self, **kwargs) -> None:
        if self.error:
            raise self.error
        self.objects.pop(kwargs["Key"], None)


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "test"}}, "TestOperation")


def _service(fake: FakeS3Client) -> StorageService:
    settings = Settings(_env_file=None, minio_bucket="test-bucket")
    return StorageService(settings, client=fake)


def test_upload_sends_bucket_key_body_and_content_type() -> None:
    fake = FakeS3Client()

    _service(fake).upload("documents/a.pdf", b"data", "application/pdf")

    assert fake.last_put == {
        "Bucket": "test-bucket",
        "Key": "documents/a.pdf",
        "Body": b"data",
        "ContentType": "application/pdf",
    }


def test_download_returns_uploaded_bytes() -> None:
    fake = FakeS3Client()
    service = _service(fake)

    service.upload("a.pdf", b"hello", "application/pdf")

    assert service.download("a.pdf") == b"hello"


def test_download_missing_key_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        _service(FakeS3Client()).download("missing.pdf")


def test_download_other_storage_error_raises_external_service_error() -> None:
    fake = FakeS3Client()
    fake.error = _client_error("AccessDenied")

    with pytest.raises(ExternalServiceError):
        _service(fake).download("a.pdf")


def test_upload_failure_raises_external_service_error() -> None:
    fake = FakeS3Client()
    fake.error = _client_error("InternalError")

    with pytest.raises(ExternalServiceError):
        _service(fake).upload("a.pdf", b"x", "application/pdf")


def test_delete_removes_object() -> None:
    fake = FakeS3Client()
    service = _service(fake)
    service.upload("a.pdf", b"x", "application/pdf")

    service.delete("a.pdf")

    assert "a.pdf" not in fake.objects
