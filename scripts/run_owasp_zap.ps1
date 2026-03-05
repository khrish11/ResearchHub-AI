param(
    [Parameter(Mandatory = $true)]
    [string]$TargetUrl
)

$ErrorActionPreference = "Stop"

Write-Host "Running OWASP ZAP baseline against $TargetUrl"
docker run --rm -t owasp/zap2docker-stable `
  zap-baseline.py `
  -t $TargetUrl `
  -a
