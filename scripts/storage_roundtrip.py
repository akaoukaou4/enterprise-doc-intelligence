"""Manual check: upload, download and delete a small file in the real MinIO.

Run from the project root:  uv run python -m scripts.storage_roundtrip
"""

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.services.storage import StorageService

KEY = "healthcheck/roundtrip.txt"


def main() -> None:
    storage = StorageService(get_settings())

    storage.upload(KEY, b"hello storage", "text/plain")
    print("uploaded")

    data = storage.download(KEY)
    assert data == b"hello storage", f"unexpected content: {data!r}"
    print("downloaded and content matches")

    storage.delete(KEY)
    print("deleted")

    try:
        storage.download(KEY)
    except NotFoundError:
        print("download after delete -> NotFoundError (correct)")
    else:
        raise SystemExit("file still exists after delete")


if __name__ == "__main__":
    main()
