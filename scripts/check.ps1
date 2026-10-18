uv run ruff check .
if ($LASTEXITCODE -ne 0) { exit 1 }
uv run ruff format --check .
if ($LASTEXITCODE -ne 0) { exit 1 }
uv run pytest -q
if ($LASTEXITCODE -ne 0) { exit 1 }
Write-Host "ALL CHECKS PASSED"
