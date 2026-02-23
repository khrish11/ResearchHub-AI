# Cleanup generated and temporary files for ResearchHub-AI (Windows PowerShell)
# Safe: removes __pycache__, .pytest_cache, frontend/dist, and test_temp DBs
# Run from repository root:  .\scripts\cleanup-workspace.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $root

Write-Output "Removing Python bytecode caches and pytest cache..."
Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue }
if (Test-Path backend/.pytest_cache) { Remove-Item -Recurse -Force backend/.pytest_cache -ErrorAction SilentlyContinue }

Write-Output "Removing test temporary DB files..."
Get-ChildItem -Path backend/tests -Filter 'test_temp*.db' -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item -Force $_.FullName -ErrorAction SilentlyContinue }

Write-Output "Removing frontend build output (dist)..."
if (Test-Path frontend/dist) { Remove-Item -Recurse -Force frontend/dist -ErrorAction SilentlyContinue }

Write-Output "Done. Remaining __pycache__ directories (should be none):"
Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | Select-Object FullName

Pop-Location
