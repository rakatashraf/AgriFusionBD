# FieldShift — judge demo runbook (plan §7). Walks the full flow and checks.
#
#   .\scripts\demo.ps1
#
# Assumes the stack is up (docker compose up -d, or the -Local path).

$ErrorActionPreference = "Stop"
$api = "http://localhost:8000/api/v1"

function Check($name, $script) {
    try {
        $script
        Write-Host "  [ok] $name" -ForegroundColor Green
    } catch {
        Write-Host "  [FAIL] $name : $_" -ForegroundColor Red
    }
}

Write-Host "`n== FieldShift demo checks (plan §7) ==" -ForegroundColor Cyan

# 1) Seeded fields through the API
Check "GET /fields returns seeded fields" {
    $r = Invoke-RestMethod "$api/fields" -Headers @{ "X-Auth" = "demo" } -ErrorAction Stop
    if (-not ($r.Count -ge 3)) { throw "expected >=3 fields, got $($r.Count)" }
}

# 3) Submit a comparison twice -> same rule_version, one run per idempotency key
Write-Host "`n  (run the submit-twice + weight-flip checks in the browser; the"
Write-Host "   money-shot is dragging waterEfficiency 0.1 -> 0.7 and watching the"
Write-Host "   ranking change with stated reasons.)"

Write-Host "`n== Judge walkthrough (3 min) ==" -ForegroundColor Cyan
Write-Host "  1. /farmer/fields            -> field map, click a field"
Write-Host "  2. field detail              -> NASA POWER + HLS evidence (coverage-labelled)"
Write-Host "  3. request comparison        -> sliders -> trade-off matrix"
Write-Host "  4. evidence / method page    -> dataset lineage, rule version"
Write-Host "  5. open officer case         -> accept / question / reject"
Write-Host "  6. export                    -> CSV/GeoJSON + provenance.json download"
Write-Host "`nOffline drill: cut the network, confirm cached snapshots render with"
Write-Host "  stale badges and no unhandled errors (plan §7 check 6)."
