# -----------------------------------------------------------------------------
# Soyog AI - Production Deployment Guide
# -----------------------------------------------------------------------------

## 1. System Architecture
- **Backend**: FastAPI with Python 3.12, containerized via Docker.
- **Frontend**: React + Vite + TypeScript (Static Build).
- **Database/Auth**: Firebase Firestore & Firebase Auth (Serverless).
- **AI**: Groq API integration for low latency LLM inference.
- **No external payments or SQL dependencies.**

## 2. Dockerfile (Backend)
The backend is packaged using a multi-worker ASGI setup (`gunicorn` + `uvicorn`) optimized for production. See `backend/Dockerfile`.

## 3. Deployment Steps

### Backend Deployment (e.g., Google Cloud Run, AWS AppRunner, Render)
1. Ensure all environment variables (see below) are configured in the cloud provider's secrets manager.
2. Build the Docker image:
   ```bash
   cd backend
   docker build -t soyog-ai-backend .
   ```
3. Run or deploy the image exposing port `8080`:
   ```bash
   docker run -p 8080:8080 --env-file .env.prod soyog-ai-backend
   ```
4. Set HTTPS: Ensure your cloud provider (like Cloud Run) handles SSL termination natively. Do not expose the internal port 8080 directly to the internet without an HTTPS proxy/load balancer.

### Frontend Deployment (e.g., Vercel, Netlify)
1. Add environment variables to your Vercel/Netlify dashboard:
   - `VITE_API_BASE=https://your-production-backend-url.com`
2. Build commands:
   - Build Command: `npm run build`
   - Install Command: `npm install`
   - Output Directory: `dist`
3. Push to `main` to trigger the build.

## 4. Required Environment Variables

### Backend (`backend/.env` or Secrets Manager)
```env
APP_ENV=production
FRONTEND_URL=https://your-frontend-domain.com
SECRET_KEY=your-secure-random-secret-key-at-least-32-chars
GROQ_API_KEY=gsk_your_groq_api_key_here
FIREBASE_PROJECT_ID=your-firebase-project-id

# Analytics Access
ADMIN_USER_IDS=firebase_uid_1,firebase_uid_2

# Security & Performance Limits
RATE_LIMIT_ENABLED=1
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_API_PER_WINDOW=300
AI_RATE_LIMIT_PER_MINUTE=20
```

### Frontend (`frontend/.env`)
```env
VITE_API_BASE=https://your-production-backend-url.com
# Use HTTPS explicitly for cookies
```

## 5. CORS Configuration
The backend is already configured to enforce strict CORS in production. 
In `backend/main.py`:
- Checks `APP_ENV`. If `production`, it only allows origins defined by `FRONTEND_URL`.
- Allows credentials (cookies) for Firebase JWT token passthrough.
- It strips localhost anomalies out of origin lists when in production.

## 6. Security Checklist
- [x] **Protect Admin Endpoints**: The `/analytics/*` endpoints enforce checking against `ADMIN_USER_IDS`.
- [x] **Input Validation**: FastAPI `pydantic` schemas strongly type API boundaries.
- [x] **CORS Locking**: Only `FRONTEND_URL` is permitted to make requests.
- [ ] **Service Account Security**: DO NOT commit Firebase Service Account JSON payload. Inject it via the Cloud Provider's environment variable (`FIREBASE_CREDENTIALS` or native GCP SA attachments).
- [ ] **HTTPS Enforced**: Ensure the backend host drops all HTTP traffic or redirects to HTTPS.
- [x] **Rate Limiting**: Rate limiting configured to prevent abuse of the expensive Groq AI routes.
- [x] **Sanitize Logs**: Ensure PII and bearer tokens are not logged. `cloud_logging.py` handles structuring without payload leaks.

## 7. Production Checklist (Pre-Flight)
- [ ] Set `APP_ENV=production` on the Backend server.
- [ ] Override `SECRET_KEY` with a cryptographically secure 64-character hex string.
- [ ] Define `FRONTEND_URL` pointing strictly to the production frontend domain (no trailing slashes).
- [ ] In Firebase console -> Authentication -> Settings -> Authorized Domains: Add your Vercel/Netlify frontend domain.
- [ ] Check Firebase Rules: Firestore rules should rely on App Check and/or Auth token validation.
- [ ] Test Analytics endpoint locally with a non-admin account to verify `403 Forbidden` triggers correctly.
- [ ] Monitor Groq API limits to ensure sufficient tier rate limits for concurrent production users.
