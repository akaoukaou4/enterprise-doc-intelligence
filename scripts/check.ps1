uv run ruff check .
if ($LASTEXITCODE -ne 0) { exit 1 }
uv run ruff format --check .
if ($LASTEXITCODE -ne 0) { exit 1 }
uv run pytest -q
if ($LASTEXITCODE -ne 0) { exit 1 }
if (Get-Command terraform -ErrorAction SilentlyContinue) {
    terraform -chdir=infra fmt -check -recursive
    if ($LASTEXITCODE -ne 0) { exit 1 }
    terraform -chdir=infra init -backend=false -input=false
    if ($LASTEXITCODE -ne 0) { exit 1 }
    terraform -chdir=infra validate
    if ($LASTEXITCODE -ne 0) { exit 1 }
} else {
    Write-Host "WARNING: terraform not installed, Terraform files NOT checked"
}
Write-Host "ALL CHECKS PASSED"
