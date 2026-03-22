# Start Firestore emulator first (required for tests)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "gcloud beta emulators firestore start --project=studio-5606596663-2ca06 --host-port=localhost:8080"

# Wait for emulator to start
Start-Sleep -Seconds 8

# Start backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; `$env:FIRESTORE_EMULATOR_HOST='localhost:8080'; python -m uvicorn main:app --reload --port 8010"

# Start frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"
