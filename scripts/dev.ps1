# FieldShift — local dev bootstrap (plan §7 runbook, uv flavour).
#
#   .\scripts\dev.ps1              # full stack via Docker + Compose
#   .\scripts\dev.ps1 -Local       # backend+frontend on the host (uv venv)
#
# Docker is the primary path (user request: "use docker and uv").

param(
    [switch]$Local
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not $Local) {
    Write-Host "`n== FieldShift: Docker Compose ==" -ForegroundColor Cyan
    Push-Location $root
    docker compose up -d
    Write-Host "`nServices:"
    docker compose ps
    Write-Host "`n  API:      http://localhost:8000/api/v1/fields"
    Write-Host "  Docs:     http://localhost:8000/api/docs/"
    Write-Host "  UI:       http://localhost:3000"
    Write-Host "  Nginx:    http://localhost:8080"
    Pop-Location
    return
}

Write-Host "`n== FieldShift: local (uv) ==" -ForegroundColor Cyan

# --- Postgres/PostGIS (Docker) or hosted ------------------------------------
Write-Host "Starting PostGIS..."
Push-Location $root
docker compose up -d postgis
Pop-Location

# --- Backend venv via uv -----------------------------------------------------
Push-Location (Join-Path $root "backend")
if (-not (Test-Path ".venv")) {
    Write-Host "Creating venv with uv..."
    uv venv .venv
}
Write-Host "Syncing deps with uv..."
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
Write-Host "`nBackend ready. In another terminal:"
Write-Host "  .venv/bin/python manage.py runserver 8000"
Pop-Location

# --- Frontend ----------------------------------------------------------------
Push-Location (Join-Path $root "frontend")
if (-not (Test-Path "node_modules")) { npm ci }
Write-Host "`nFrontend ready. In another terminal:"
Write-Host "  npm run dev   (proxies /api -> :8000)"
Pop-Location
