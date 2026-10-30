param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://')]
    [string]$ApiOrigin,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://')]
    [string]$FrontendOrigin
)

$ErrorActionPreference = 'Stop'
$api = $ApiOrigin.TrimEnd('/')
$frontend = $FrontendOrigin.TrimEnd('/')
$failures = [System.Collections.Generic.List[string]]::new()

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Uri
    )

    try {
        $response = Invoke-WebRequest -Uri $Uri -Method Get -MaximumRedirection 3
        if ($response.StatusCode -ne 200) {
            $failures.Add("$Name returned HTTP $($response.StatusCode)")
        } else {
            Write-Host "[PASS] $Name ($Uri)"
        }
        return $response
    } catch {
        $failures.Add("$Name failed: $($_.Exception.Message)")
        return $null
    }
}

$health = Test-Endpoint -Name 'API health' -Uri "$api/health"
$frontendResponse = Test-Endpoint -Name 'Frontend' -Uri $frontend

if ($health -and $health.Content -notmatch '"status"\s*:\s*"(healthy|ok)"') {
    $failures.Add('API health response did not contain a healthy/ok status')
}

if ($frontendResponse) {
    foreach ($header in @('X-Content-Type-Options', 'X-Frame-Options', 'Referrer-Policy')) {
        if (-not $frontendResponse.Headers[$header]) {
            $failures.Add("Frontend response is missing the $header header")
        }
    }
}

try {
    $corsHeaders = @{
        Origin = $frontend
        'Access-Control-Request-Method' = 'GET'
        'Access-Control-Request-Headers' = 'authorization,content-type'
    }
    $cors = Invoke-WebRequest -Uri "$api/api/v1/auth/me" -Method Options -Headers $corsHeaders
    $allowedOrigin = $cors.Headers['Access-Control-Allow-Origin']
    if ($allowedOrigin -ne $frontend) {
        $failures.Add("CORS allowed origin was '$allowedOrigin', expected '$frontend'")
    } else {
        Write-Host '[PASS] Production CORS origin'
    }
} catch {
    $failures.Add("CORS preflight failed: $($_.Exception.Message)")
}

if ($failures.Count -gt 0) {
    Write-Error ("Production smoke checks failed:`n- " + ($failures -join "`n- "))
    exit 1
}

Write-Host 'All public production smoke checks passed.'
