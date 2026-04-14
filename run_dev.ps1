param(
	[string]$FirebaseProject = "demo-test",
	[int]$FirestorePort = 8080,
	[int]$BackendPort = 8010,
	[int]$FrontendPort = 5173,
	[int]$EmulatorWaitSeconds = 45
)

$ErrorActionPreference = "Stop"

$firestoreHost = "localhost:$FirestorePort"
$backendUrl = "http://localhost:$BackendPort"

Write-Host "Starting Firestore emulator on $firestoreHost (project=$FirebaseProject)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "gcloud beta emulators firestore start --project=$FirebaseProject --host-port=$firestoreHost"

Write-Host "Waiting for Firestore emulator readiness..."
$ready = $false
for ($i = 0; $i -lt $EmulatorWaitSeconds; $i++) {
	try {
		$null = Invoke-WebRequest -Uri "http://$firestoreHost" -UseBasicParsing -TimeoutSec 1
		$ready = $true
		break
	}
	catch {
		Start-Sleep -Milliseconds 1000
	}
}

if (-not $ready) {
	throw "Firestore emulator did not become ready within $EmulatorWaitSeconds seconds."
}

Write-Host "Starting backend on $backendUrl..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; `$env:FIRESTORE_EMULATOR_HOST='$firestoreHost'; python -m uvicorn main:app --reload --port $BackendPort"

Write-Host "Starting frontend (Vite) on port $FrontendPort..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev -- --port $FrontendPort"

Write-Host "Dev stack launched successfully."
