<#
CoreDent — production gate: one command that must pass before a deploy is approved.

Runs (in order, stop-on-failure for the code gates):
  1. Backend compile + targeted test set  (pytest)
  2. Frontend typecheck                   (npm run typecheck)
  3. Frontend eslint                      (npm run lint)
  4. Live-integration smoke               (SKIP-friendly; pass explicitly via --skip-integrations)
  5. Backup/DR drill                      (only with --drill <dump>; otherwise SKIP)

Usage:
  pwsh scripts/gate-production.ps1                    # code gates only
  pwsh scripts/gate-production.ps1 --with-integrations  # + live-integration smoke
  pwsh scripts/gate-production.ps1 --drill latest.dump --with-integrations  # full
#>
param(
    [switch]$WithIntegrations,
    [string]$Drill   = $null,
    [string]$Root    = (Split-Path (Split-Path $script:PSCommandPath -Parent) -Parent)  # repo root
)
$ErrorActionPreference = 'Stop'
$failures = [System.Collections.Generic.List[string]]::new()
$api = Join-Path $Root 'coredent-api'
$web = Join-Path $Root 'coredent-style-main'

Write-Host "== CoreDent production gate @ $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') =="

# ---- 1. Backend: compile + targeted suite ----
Write-Host ''; Write-Host '== 1. Backend =='
Push-Location $api
try {
    python -m py_compile app/api/v1/api.py app/main.py app/models/__init__.py app/services/platform_service.py
    if ($LASTEXITCODE -ne 0) { $failures.Add('py_compile failed') }
    python -m pytest tests/test_production_gaps.py tests/test_patients.py tests/test_reports.py tests/test_billing.py tests/test_billing_comprehensive.py -q --tb=short --no-cov -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { $failures.Add('backend pytest suite failed') }
} catch { $failures.Add("backend gate error: $($_.Exception.Message)") } finally { Pop-Location }

# ---- 2. Frontend typecheck ----
Write-Host ''; Write-Host '== 2. Frontend typecheck =='
Push-Location $web
try {
    npm run typecheck
    if ($LASTEXITCODE -ne 0) { $failures.Add('frontend typecheck failed') }
} catch { $failures.Add("typecheck error: $($_.Exception.Message)") } finally { Pop-Location }

# ---- 3. Frontend lint ----
Write-Host ''; Write-Host '== 3. Frontend lint =='
Push-Location $web
try {
    npm run lint
    if ($LASTEXITCODE -ne 0) { $failures.Add('frontend lint failed') }
} catch { $failures.Add("lint error: $($_.Exception.Message)") } finally { Pop-Location }

# ---- 4. Live integration smoke ----
Write-Host ''; Write-Host '== 4. Live integrations =='
if ($WithIntegrations) {
    Push-Location $Root
    try { pwsh scripts/live-integration-smoke.ps1; if ($LASTEXITCODE -ne 0) { $failures.Add('live integration smoke failed') } }
    catch { $failures.Add("integration smoke error: $($_.Exception.Message)") } finally { Pop-Location }
} else { Write-Host '[SKIP] pass --with-integrations' }

# ---- 5. Backup/DR drill ----
Write-Host ''; Write-Host '== 5. Backup/DR =='
if ($Drill) {
    Push-Location $Root
    try { pwsh scripts/backup-dr-drill.ps1 -SourceDump $Drill; if ($LASTEXITCODE -ne 0) { $failures.Add('DR drill failed') } }
    catch { $failures.Add("DR drill error: $($_.Exception.Message)") } finally { Pop-Location }
} else { Write-Host '[SKIP] pass --drill <path-to-latest.dump>' }

# ---------------------------------------------------------------------------
Write-Host ''
if ($failures.Count -gt 0) {
    Write-Error ("PRODUCTION GATE FAILED:`n- " + ($failures -join "`n- "))
    exit 1
}
Write-Host 'PRODUCTION GATE PASSED (code gates + any provided ops gates).'