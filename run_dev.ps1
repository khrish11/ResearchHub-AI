param(
	[string]$FirebaseProject = "demo-test",
	[int]$AuthPort = 9099,
	[int]$FirestorePort = 8081,
	[int]$StoragePort = 9199,
	[int]$BackendPort = 8010,
	[int]$FrontendPort = 5173,
	[int]$EmulatorWaitSeconds = 45
)

$ErrorActionPreference = "Stop"

$firestoreHost = "localhost:$FirestorePort"
$authHost = "localhost:$AuthPort"
$storageHost = "localhost:$StoragePort"
$backendUrl = "http://localhost:$BackendPort"

Write-Host "Starting Firebase emulators with Auth emulator on $authHost, Firestore on $firestoreHost, Storage on $storageHost (project=$FirebaseProject)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "firebase emulators:start --project=$FirebaseProject --auth port=$AuthPort --firestore port=$FirestorePort --storage port=$StoragePort"

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
