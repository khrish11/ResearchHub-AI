Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; venv/Scripts/activate; uvicorn main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"
