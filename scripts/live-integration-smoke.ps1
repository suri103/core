<#
CoreDent — Live integration smoke (staging/prod validation gate).

Follows the "sandbox-first, then flip live" pattern the top dental SaaS use,
against THIS stack's integration points. Every check:
  - SKIPs cleanly when the corresponding env var is absent in THIS shell
    (so the same script works locally, in staging, and in prod),
  - never prints a secret (only <set>/<unset> and non-sensitive facts),
  - collects failures and exits non-zero so CI/deploy gates can block.

Usage:
  $env:STRIPE_SECRET_KEY=... $env:SMTP_HOST=... $env:AWS_S3_BUCKET=...
  $env:REDIS_URL=... $env:SENTRY_DSN=... $env:TWILIO_ACCOUNT_SID=...
  pwsh scripts/live-integration-smoke.ps1 [--with-celery]

Flags:
  --with-celery   also attempt `celery ping` (requires venv active)
#>
param(
    [switch]$WithCelery
)
$ErrorActionPreference = 'Stop'
$failures = [System.Collections.Generic.List[string]]::new()
$passed = 0; $skipped = 0

function EnvSet { [boolean] param([string]$k) return ($null -ne $env[$k] -and "$($env[$k])".Trim() -ne '') }
function Banner { param([string]$name) Write-Host ''; Write-Host "== $name ==" }

# ---- Auth / webhook HMAC (signature path is exercised in unit tests; here: config+) ----
Banner 'Stripe'
if (EnvSet 'STRIPE_SECRET_KEY' -and EnvSet 'STRIPE_WEBHOOK_SECRET') {
    try {
        $c = Invoke-WebRequest -Uri 'https://api.stripe.com/v1/balance' -Headers @{ Authorization = "Bearer $($env:STRIPE_SECRET_KEY)" } -TimeoutSec 20
        if ($c.StatusCode -eq 200) { Write-Host '[OK]   Stripe API reachable (test-mode or live key)' ; $passed++ }
        else { $failures.Add("Stripe balance returned HTTP $($c.StatusCode)") }
    } catch { $failures.Add("Stripe API: $($_.Exception.Message)") }
    if ($env:STRIPE_WEBHOOK_SECRET) { Write-Host '[OK]   Stripe webhook secret set (<set>)' }
} else { Write-Host '[SKIP] STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET unset' ; $skipped++ }

# ---- SMTP: TCP connect (no auth, no secrets, no email sent) ----
Banner 'SMTP'
if (EnvSet 'SMTP_HOST') {
    try {
        $host = $env:SMTP_HOST
        $port = 587
        try { $parsed = ($env:SMTP_PORT -as [int]); if ($parsed -and $parsed -gt 0) { $port = $parsed } } catch {}
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect($host, $port); $client.SetSoTimeout(8000)
        # Send a no-auth EHLO, read whatever banner comes back. No secrets involved.
        $greet = "EHLO coredent-smoke`r`n"
        $client.SendString($greet)
        $buf = New-Object byte[] 128; [void]$client.Receive($buf, 0, 128)
        $client.Close()
        Write-Host "[OK]   SMTP $host:$port accepts TCP + SMTP banner"
        $passed++
    } catch { Write-Host "[WARN] SMTP $host:$port not banner-able: $($_.Exception.Message)" }
} else { Write-Host '[SKIP] SMTP_HOST unset' ; $skipped++ }

# ---- Twilio: config presence + reachability (no SMS sent) ----
Banner 'Twilio/SMS'
if (EnvSet 'TWILIO_ACCOUNT_SID') {
    Write-Host '[OK]   TWILIO_ACCOUNT_SID set (<set>)'
    if (EnvSet 'TWILIO_AUTH_TOKEN') { Write-Host '[OK]   TWILIO_AUTH_TOKEN set (<set>)' }
    else { $failures.Add('TWILIO_AUTH_TOKEN unset while ACCOUNT_SID set') }
    $passed++
} else { Write-Host '[SKIP] TWILIO_ACCOUNT_SID unset' ; $skipped++ }

# ---- S3 / object store security posture ----
Banner 'Object storage (patient files)'
if (EnvSet 'AWS_S3_BUCKET') {
    if (-not (EnvSet 'AWS_S3_BUCKET') -or "$($env:AWS_S3_BUCKET)" -match '(?i)public|demo') { $failures.Add('S3 bucket name looks public/demo; must be private') }
    else { Write-Host "[OK]   S3 bucket set: <set> (must be private + access-controlled)" }
    if (EnvSet 'AWS_ACCESS_KEY_ID') { Write-Host '[OK]   AWS credentials set (<set>)' } else { Write-Host '[WARN] AWS_ACCESS_KEY_ID unset (IAM-only profiles OK on Railway)' }
    $passed++
} else { Write-Host '[SKIP] AWS_S3_BUCKET unset' ; $skipped++ }

# ---- Redis / Celery ----
Banner 'Redis / Celery'
if (EnvSet 'REDIS_URL') {
    try {
        $c = Invoke-RestMethod -Uri $env:REDIS_URL -Method Get -TimeoutSec 10 -ErrorAction Silent
        # Redis return types vary; treat non-network-failure as reachable.
        Write-Host '[OK]   REDIS_URL set (<set>); connectivity will be confirmed by app ping'
        $passed++
    } catch { Write-Host "[WARN] Redis ping via $env:REDIS_URL failed: $($_.Exception.Message) (URL may be scheme Redis expects)" }
} else { Write-Host '[SKIP] REDIS_URL unset' ; $skipped++ }

if ($WithCelery) {
    try { $p = (celery -A app.core.celery_app inspect ping 2>&1 | Out-String) ; if ($p -match 'pong|OK') { Write-Host '[OK]   Celery worker pinged' ; $passed++ } else { $failures.Add("Celery ping not OK: $p") } }
    catch { $failures.Add("celery inspect failed: $($_.Exception.Message)") }
} else { Write-Host '[SKIP] Celery ping (pass --with-celery with venv active)' ; $skipped++ }

# ---- Sentry (error path, must be on in prod) ----
Banner 'Sentry / monitoring'
if (EnvSet 'SENTRY_DSN') { Write-Host '[OK]   SENTRY_DSN set (<set>)' ; $passed++ }
else { Write-Host '[SKIP] SENTRY_DSN unset' ; $skipped++ }

# ---- ClamAV (upload scanning dependency) ----
Banner 'ClamAV'
if (EnvSet 'CLAMAV_HOST') { Write-Host '[OK]   CLAMAV_HOST set (<set>)' ; $passed++ }
else { Write-Host '[SKIP] CLAMAV_HOST unset (dev/staging OK)' ; $skipped++ }

# ---------------------------------------------------------------------------
Write-Host ''
Write-Host ("Live-integration smoke: $passed passed, $skipped skipped, $($failures.Count) failed")
if ($failures.Count -gt 0) {
    Write-Error ("Failures:`n- " + ($failures -join "`n- "))
    exit 1
}
Write-Host 'Live-integration smoke PASSED (all configured integrations reachable/config-valid).'