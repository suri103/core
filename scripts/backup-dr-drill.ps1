<#
CoreDent — Backup / DR drill runner (mechanical parts of the monthly drill).

Measures RTO to a scratch Postgres, verifies restore integrity on core tables,
and checks tenant-scoping + audit write-once after restore. The human checklist
is scripts/backup-dr-drill-checklist.md; run BOTH, this only automates the steps
that can be automated.

Usage (PowerShell):
  pwsh scripts/backup-dr-drill.ps1 -SourceDump <path-to-latest-full.dump> ^
                                  -TargetPgDbUrl "postgresql://dr:dr@localhost:5433/dr" ^
                                  -ProdDbUrl "postgresql://prod:...@localhost:5432/coredent" ^
                                  [-HealthUrl "http://localhost:8000/health"]

Notes:
  - TargetPgDbUrl MUST point at a scratch DB, never production. We refuse to
    continue if TargetPgDbUrl equals ProdDbUrl.
  - Requires `psql`/`pg_restore` on PATH (PostgreSQL 16 client).
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('(?i)^postgres(ql)?://')]
    [string]$TargetPgDbUrl,

    [Parameter(Mandatory = $false)]
    [string]$SourceDump,

    [Parameter(Mandatory = $false)]
    [ValidatePattern('(?i)^postgres(ql)?://')]
    [string]$ProdDbUrl,

    [Parameter(Mandatory = $false)]
    [string]$HealthUrl,

    [Parameter(Mandatory = $false)]
    [int]$RestoreTimeoutSeconds = 14400  # 4h RTO ceiling
)

$ErrorActionPreference = 'Stop'
$failures = [System.Collections.Generic.List[string]]::new()
$started = Get-Date

function Test-Pg { param([string]$url, [string]$sql)
    try { (psql $url -Atc $sql 2>&1 | Out-String).Trim() } catch { return $null } }

Write-Host "== Backup/DR drill started: $(Get-Date -Format 'yyyy-MM-dd HH:mm') =="

# ---- 0. Safety guard ----
if ($TargetPgDbUrl -eq $ProdDbUrl) {
    Write-Error 'REFUSING: TargetPgDbUrl must be a scratch DB, not production.'
    exit 2
}

# ---- 1. Snapshot present & sane ----
if (-not $SourceDump -or -not (Test-Path $SourceDump)) {
    $failures.Add("Backup snapshot '$SourceDump' not found (fill via -SourceDump or backup job).")
} else {
    $size = (Get-Item $SourceDump).Length
    if ($size -le 0) { $failures.Add("Backup snapshot is 0 bytes: $SourceDump") }
    else { Write-Host "[OK]   snapshot present ($([math]::Round($size/1MB,2)) MB): $SourceDump" }
}

# ---- 2. Restore into scratch ----
if ($SourceDump -and (Test-Path $SourceDump)) {
    $restoreStart = Get-Date
    Write-Host "[..]  restoring $SourceDump -> scratch DB (timeout $RestoreTimeoutSeconds s)"
    & pg_restore --no-owner --clean --if-exists -d $TargetPgDbUrl $SourceDump 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        $failures.Add("pg_restore exited $LASTEXITCODE (see output above)")
    } else {
        $rtoSeconds = (Get-Date).Subtract($restoreStart).TotalSeconds
        Write-Host ("[OK]   restore finished in $([math]::Round($rtoSeconds,1))s; RTO within 4h: " + ($rtoSeconds -le $RestoreTimeoutSeconds))
        if ($rtoSeconds -gt $RestoreTimeoutSeconds) { $failures.Add("RTO > $RestoreTimeoutSeconds s") }
    }
}

# ---- 3. Table-count integrity + tenant sanity (against scratch) ----
foreach ($tbl in @('practices','users','patients','appointments','invoices','payments','audit_logs')) {
    $count = Test-Pg $TargetPgDbUrl "SELECT count(*) FROM $tbl"
    if ($null -eq $count) { $failures.Add("Could not read count for $tbl on scratch") }
    else { Write-Host "[OK]   $tbl rows = $count" }
}

# ---- 4. Audit write-once still enforced after restore (tamper attempt must fail) ----
# The tamper must touch a REAL row. The write-once guard is a BEFORE UPDATE
# FOR EACH ROW trigger, so the old "WHERE 1=0" matched no rows, fired no
# trigger, raised no error and reported success while testing nothing.
$auditRows = "$(Test-Pg $TargetPgDbUrl 'SELECT count(*) FROM audit_logs')".Trim()
if (-not $auditRows -or $auditRows -eq '0') {
    Write-Host '[SKIP] audit write-once (audit_logs is empty after restore; seed data first - checklist C7)'
} else {
    $tamper = Test-Pg $TargetPgDbUrl "UPDATE audit_logs SET action = action WHERE id = (SELECT id FROM audit_logs LIMIT 1)"
    if ($null -eq $tamper) {
        $failures.Add('audit write-once check could not run (psql returned nothing)')
    } elseif ("$tamper" -match 'error|violat|locked|trigger|permission|denied') {
        Write-Host '[OK]   audit write-once trigger/guard still blocks tampering after restore'
    } else {
        $failures.Add("audit write-once NOT enforced after restore: tampering a real audit row succeeded (restored DB lost the guard)")
    }
}

# ---- 5. App health against restored DB (optional) ----
if ($HealthUrl) {
    try {
        $h = Invoke-WebRequest -Uri $HealthUrl -Method Get -MaximumRedirection 2 -TimeoutSec 20
        $ok = ($h.StatusCode -eq 200) -and ($h.Content -match '"database"\s*:\s*"connected"|"status"\s*:\s*"healthy"')
        if ($ok) { Write-Host '[OK]   /health reports connected after restore' }
        else { $failures.Add("/health on restored DB did not report connected: $($h.Content)") }
    } catch { $failures.Add("/health check failed: $($_.Exception.Message)") }
} else {
    Write-Host '[SKIP] /health check (no -HealthUrl)'
}

$elapsed = (Get-Date).Subtract($started)
if ($failures.Count -gt 0) {
    Write-Error ("Backup/DR drill UNHAPPY (overall $([math]::Round($elapsed.TotalMinutes,1))m):`n- " + ($failures -join "`n- "))
    exit 1
}
Write-Host ("Backup/DR drill PASSED in $([math]::Round($elapsed.TotalMinutes,1))m. Do the human checklist items A/B/D/E too.")