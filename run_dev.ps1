Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; python -m uvicorn main:app --reload --port 8010"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"
