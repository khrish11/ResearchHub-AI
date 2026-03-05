$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$hooksPath = Join-Path $repoRoot ".githooks"

if (-not (Test-Path $hooksPath)) {
    throw "Hooks directory not found: $hooksPath"
}

git config core.hooksPath ".githooks"
Write-Output "Configured git hooks path: .githooks"

$hookFile = Join-Path $hooksPath "pre-push"
if (Test-Path $hookFile) {
    Write-Output "Installed hook: .githooks/pre-push"
}
