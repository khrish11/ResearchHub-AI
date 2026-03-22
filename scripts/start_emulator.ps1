# Start Firestore emulator for local development/testing
# Usage: .\scripts\start_emulator.ps1

$ErrorActionPreference = "Stop"

Write-Host "Starting Firestore emulator on localhost:8080 (gRPC) and localhost:9080 (REST)..." -ForegroundColor Cyan

# Kill any existing emulator processes
$emulatorProcesses = Get-Process | Where-Object { $_.CommandLine -like "*cloud_firestore_emulator*" }
if ($emulatorProcesses) {
    Write-Host "Killing existing emulator processes..." -ForegroundColor Yellow
    $emulatorProcesses | Stop-Process -Force
    Start-Sleep -Seconds 2
}

# Set required environment variables
$env:FIRESTORE_EMULATOR_HOST = "localhost:8080"
$env:FIREBASE_PROJECT_ID = "studio-5606596663-2ca06"

# Use full path to gcloud (installed via Cloud SDK)
$gcloudPath = "C:\Users\Girish P\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

# Start the emulator in background
Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList "/c", "`"$gcloudPath`" beta emulators firestore start --project=studio-5606596663-2ca06 --host-port=localhost:8080" `
    -NoNewWindow `
    -PassThru

Start-Sleep -Seconds 10

# Verify it's running
$tcpTest = Test-NetConnection -ComputerName "localhost" -Port 8080 -WarningAction SilentlyContinue
if ($tcpTest.TcpTestSucceeded) {
    Write-Host "Firestore emulator is running on localhost:8080 (gRPC) and localhost:9080 (REST)" -ForegroundColor Green
    Write-Host ""
    Write-Host "To run tests with the emulator:" -ForegroundColor Yellow
    Write-Host '  $env:FIRESTORE_EMULATOR_HOST = "localhost:8080"' -ForegroundColor White
    Write-Host "  python -m pytest tests/" -ForegroundColor White
} else {
    Write-Host "WARNING: Emulator may not be running yet. Try again in a few seconds." -ForegroundColor Red
    Write-Host "Or check: curl http://localhost:9080/v1/projects/studio-5606596663-2ca06/databases/(default)/documents" -ForegroundColor Gray
}
