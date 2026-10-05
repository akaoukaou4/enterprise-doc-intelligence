from app.core.config import Settings
from app.db.models import Document


def test_document_table_name_and_columns() -> None:
    table = Document.__table__

    assert table.name == "documents"
    assert set(table.columns.keys()) == {
        "id",
        "filename",
        "storage_key",
        "content_type",
        "size_bytes",
        "status",
        "created_at",
    }


def test_document_storage_key_is_unique() -> None:
    assert Document.__table__.columns["storage_key"].unique is True


def test_storage_settings_are_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("MINIO_ENDPOINT", "http://example:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "key")
    monkeypatch.setenv("MINIO_SECRET_KEY", "secret")  # pragma: allowlist secret
    monkeypatch.setenv("MINIO_BUCKET", "my-bucket")

    settings = Settings(_env_file=None)

    assert settings.minio_endpoint == "http://example:9000"
    assert settings.minio_access_key == "key"
    assert settings.minio_secret_key == "secret"  # pragma: allowlist secret
    assert settings.minio_bucket == "my-bucket"
