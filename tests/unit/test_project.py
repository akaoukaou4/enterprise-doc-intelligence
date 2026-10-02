from pathlib import Path


def test_project_metadata_exists() -> None:
    pyproject = Path("pyproject.toml")

    assert pyproject.exists()
    assert pyproject.is_file()
