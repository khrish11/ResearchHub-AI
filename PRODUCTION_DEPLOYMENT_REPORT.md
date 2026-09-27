# Soyog AI — Production Deployment Report

## 1. Deployment Date
2026-09-26

## 2. Release Version / Commit
`main` (local modifications to `render.yaml`)

## 3. Frontend URL
- **Configured Production Domain**: `https://research-hub-ai-lime.vercel.app` (to be managed in Vercel dashboard)
- **Development / Verification URL**: `http://localhost:5173`

## 4. Backend Configuration (Render)
- **Target Platform**: Render
- **Blueprint File**: `render.yaml`
- **Web Service Configuration**:
  - `type`: `web`
  - `name`: `soyog-ai-backend`
  - `runtime`: `docker`
  - `rootDir`: `backend`
  - `dockerfilePath`: `./Dockerfile`
  - `healthCheckPath`: `/health/live`
- **Background Worker Configuration**:
  - `type`: `worker`
  - `name`: `soyog-ai-worker`
  - `runtime`: `docker`
  - `rootDir`: `backend`
  - `dockerfilePath`: `./Dockerfile`
  - `dockerCommand`: `python workers/paper_check_worker.py`

## 5. Firebase Project
- **Project Name**: Soyog AI
- **Project ID**: `studio-5606596663-2ca06`
- **Project Number**: `568566718388`

## 6. Environment Variables Verified
The `render.yaml` specifies necessary variables for both the backend and worker to run on Render:
- `APP_ENV`
- `BACKEND_URL`
- `FRONTEND_URL`
- `SECRET_KEY`
- `GROQ_API_KEY`
- `FIREBASE_PROJECT_ID`
- `FIREBASE_STORAGE_BUCKET`
- `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64`
- `AUTH_COOKIE_SAMESITE`
- `AUTH_COOKIE_SECURE`
- `GOOGLE_REDIRECT_URI`

Firebase Admin SDK will correctly initialize using the injected `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64` via the established fallback logic in `backend/utils/firebase_service_account.py`.

## 7. Security and Hygiene
- **Secret Scan**: No secrets (Service Account JSONs, Private Keys, `GROQ_API_KEY` values, or `SECRET_KEY` values) were found committed in the Git history or checked-in files.
- **Cookies**: Properly configured for cross-origin authentication (`AUTH_COOKIE_SAMESITE=none` and `AUTH_COOKIE_SECURE="1"`).
- **CORS**: Correctly configured to include the `FRONTEND_URL`.

## 8. Pub/Sub Configuration
- **Topic**: `projects/studio-5606596663-2ca06/topics/paper-check-jobs` (ACTIVE)
- **Subscription**: `projects/studio-5606596663-2ca06/subscriptions/paper-check-jobs-sub` (ACTIVE)
- The Paper Check background worker is designed to pull messages from this subscription. This remains unchanged from the GCP deployment architecture.

## 9. Firestore & Storage
- **Firestore Database**: Cloud Firestore (default database)
- **Firestore Security Rules**: Deployed (`firestore.rules`)
- **Firestore Indexes**: Deployed (`firestore.indexes.json`)
- **Storage Bucket**: `studio-5606596663-2ca06.firebasestorage.app`
- **Storage Security Rules**: Deployed (`storage.rules`)

## 10. Health Checks
- **Liveness**: `/health/live` mapped to the Render health check path.
- **Readiness**: `/health/ready` implemented.

## 11. Deployment Prerequisites
- The Render Web Service and Render Background Worker must be connected via the Render Dashboard using the `render.yaml` blueprint.
- Environment variables (especially `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64`, `GROQ_API_KEY`, and `SECRET_KEY`) must be manually entered into the Render Environment Groups or individual service settings since `sync: false` is properly set.
- Vercel Frontend must be deployed pointing `VITE_API_BASE` to the Render Web Service URL.

## 12. Remaining Blockers
- Actual production deployment cannot proceed until the repository is connected to Render and environment secrets are provided in the Render dashboard.

## 13. Final Status
**RENDER PRODUCTION DEPLOYMENT READY**
