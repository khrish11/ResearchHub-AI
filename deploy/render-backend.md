# Render Backend Deployment (FastAPI)

This guide deploys only the backend (`/backend`) to Render while keeping frontend on Vercel.

## 1) Render Service

- Use the repository root `render.yaml`.
- Service type: `web`
- Runtime: `docker`
- Root directory: `backend`
- Health check path: `/health/live`

## 2) Firebase Credentials Outside GCP

The backend now supports these env strategies (first valid wins):

1. `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64` (recommended)
2. `FIREBASE_SERVICE_ACCOUNT_JSON`
3. split variables:
   - `FIREBASE_SERVICE_ACCOUNT_PROJECT_ID`
   - `FIREBASE_SERVICE_ACCOUNT_CLIENT_EMAIL`
   - `FIREBASE_SERVICE_ACCOUNT_PRIVATE_KEY`
   - optional: `FIREBASE_SERVICE_ACCOUNT_PRIVATE_KEY_ID`, `FIREBASE_SERVICE_ACCOUNT_CLIENT_ID`, `FIREBASE_SERVICE_ACCOUNT_TOKEN_URI`

### PowerShell helper to create Base64 from JSON file

```powershell
$jsonPath = "C:\path\to\firebase-service-account.json"
$bytes = [System.Text.Encoding]::UTF8.GetBytes((Get-Content $jsonPath -Raw))
[Convert]::ToBase64String($bytes)
```

Paste the output into Render env var `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64`.

## 3) Required Backend Env Vars

- `APP_ENV=production`
- `BACKEND_URL=https://<render-service>.onrender.com`
- `FRONTEND_URL=https://research-hub-ai-lime.vercel.app`
- `SECRET_KEY=<strong-random-secret>`
- `GROQ_API_KEY=<key>`
- `FIREBASE_PROJECT_ID=<project-id>`
- `FIREBASE_STORAGE_BUCKET=<bucket>`
- `AUTH_COOKIE_SAMESITE=none`
- `AUTH_COOKIE_SECURE=1`
- `GOOGLE_REDIRECT_URI=https://<render-service>.onrender.com/auth/google/callback`

## 4) Frontend API URL Update

Frontend API base is resolved in:

- `frontend/src/api.ts` (`VITE_API_URL` then `VITE_API_BASE`)

Set Vercel project env vars:

- `VITE_API_URL=https://<render-service>.onrender.com`
- `VITE_API_BASE=https://<render-service>.onrender.com`

Then redeploy frontend.

