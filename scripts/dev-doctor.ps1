param(
    [string]$BackendEnvPath = "backend/.env",
    [string]$FrontendEnvPath = "frontend/.env"
)

$ErrorActionPreference = "Stop"
$failures = @()

function Test-Cmd {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        $script:failures += "Missing required command: $Name"
        return $false
    }
    return $true
}

Write-Host "Running Soyog dev doctor..."

Test-Cmd python | Out-Null
Test-Cmd node | Out-Null
Test-Cmd npm | Out-Null
Test-Cmd gcloud | Out-Null

if (Test-Path $BackendEnvPath) {
    Write-Host "Found $BackendEnvPath"
} else {
    $failures += "Missing backend env file: $BackendEnvPath"
}

if (Test-Path $FrontendEnvPath) {
    Write-Host "Found $FrontendEnvPath"
} else {
    $failures += "Missing frontend env file: $FrontendEnvPath"
}

if (-not $failures.Count) {
    try {
        $pythonVersion = python --version 2>&1
        $nodeVersion = node --version 2>&1
        $npmVersion = npm --version 2>&1
        Write-Host "Python: $pythonVersion"
        Write-Host "Node:   $nodeVersion"
        Write-Host "npm:    $npmVersion"
    } catch {
        $failures += "Failed to read one or more tool versions."
    }
}

if ($failures.Count -gt 0) {
    Write-Error "Dev doctor failed:"
    $failures | ForEach-Object { Write-Error " - $_" }
    exit 1
}

Write-Host "Dev doctor passed. Environment looks ready."
