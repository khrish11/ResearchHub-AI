# PHASE 7.1 PRODUCTION ENVIRONMENT CHECKLIST

**Date:** 2026-08-21  
**Phase:** PHASE 7 - Production Launch & Real-World Validation  
**Objective:** Validate production environment configuration

---

## Executive Summary

Production environment validation checklist covering Firebase, Firestore, authentication, CORS, security headers, API configuration, and build settings. All configurations are environment-variable driven with no hardcoded production values.

**Overall Assessment:** CONFIGURATION READY, VALUES TO BE SET

---

## 1. Firebase Production Configuration

### 1.1 Firebase Project Configuration

**Required Backend Variables:**
- [ ] `FIREBASE_PROJECT_ID` - Set to production Firebase project ID
- [ ] `FIREBASE_STORAGE_BUCKET` - Set to production storage bucket
- [ ] Firebase service account credentials (one of):
  - [ ] `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64` (recommended)
  - [ ] `FIREBASE_SERVICE_ACCOUNT_JSON`
  - [ ] Split fields (PROJECT_ID, CLIENT_EMAIL, PRIVATE_KEY, etc.)

**Required Frontend Variables:**
- [ ] `VITE_FIREBASE_API_KEY` - Firebase web API key
- [ ] `VITE_FIREBASE_AUTH_DOMAIN` - Firebase auth domain
- [ ] `VITE_FIREBASE_PROJECT_ID` - Firebase project ID
- [ ] `VITE_FIREBASE_STORAGE_BUCKET` - Firebase storage bucket
- [ ] `VITE_FIREBASE_MESSAGING_SENDER_ID` - Firebase messaging sender ID
- [ ] `VITE_FIREBASE_APP_ID` - Firebase app ID
- [ ] `VITE_FIREBASE_MEASUREMENT_ID` - Firebase measurement ID

**Status:** ⚠️ Variables documented, values to be set

### 1.2 Firebase AppCheck Configuration

**Required Variables:**
- [ ] `FIREBASE_APPCHECK_ENFORCED=1` - Enable AppCheck for production
- [ ] `FIREBASE_APPCHECK_ALLOW_LOCALHOST=0` - Disable localhost for production
- [ ] `VITE_FIREBASE_APPCHECK_SITE_KEY` - AppCheck site key (or ReCAPTCHA alternative)
- [ ] `VITE_FIREBASE_APPCHECK_PROVIDER` - Provider type (enterprise or recaptcha-v3)

**Status:** ⚠️ Should be enabled for production security

### 1.3 Firebase Configuration Validation

**Backend Validation:**
- [ ] Service account has Firestore admin permissions
- [ ] Service account has Storage admin permissions
- [ ] Service account has Authentication admin permissions
- [ ] Project has Authentication enabled
- [ ] Project has Firestore enabled
- [ ] Project has Storage enabled

**Frontend Validation:**
- [ ] Firebase web app configured in Firebase console
- [ ] Web app API key restricted to production domain
- [ ] Authorized domains configured in Firebase console
- [ ] AppCheck configured with reCAPTCHA Enterprise or reCAPTCHA V3

**Status:** ⚠️ Manual validation required in Firebase console

---

## 2. Firestore Configuration and Required Indexes

### 2.1 Existing Firestore Indexes

**Current Indexes (firestore.indexes.json):**
- ✅ paper_check_jobs (4 indexes)
- ✅ workspace_insight_jobs (3 indexes)
- ✅ workspace_feed_jobs (3 indexes)
- ✅ workspace_feed (2 indexes)
- ✅ workspace_insights (2 indexes)
- ✅ search_history (1 index)
- ✅ user_session_state (1 index)
- ✅ workspace_documents (2 indexes)
- ✅ workspace_files (2 indexes)
- ✅ paper_comparisons (1 index)
- ✅ research_reports (1 index)
- ✅ data_rights_requests (1 index)
- ✅ workspace_vectors (1 index)

**Total:** 24 composite indexes

### 2.2 Missing Firestore Indexes

**Potentially Missing Indexes:**
- ⚠️ research_intelligence_artifacts - No indexes defined
- ⚠️ saved_research_questions - No indexes defined
- ⚠️ research_plans - No indexes defined

**Recommended Indexes to Add:**
```json
{
  "collectionGroup": "research_intelligence_artifacts",
  "queryScope": "COLLECTION",
  "fields": [
    { "fieldPath": "workspace_id", "order": "ASCENDING" },
    { "fieldPath": "created_at", "order": "DESCENDING" }
  ]
},
{
  "collectionGroup": "research_intelligence_artifacts",
  "queryScope": "COLLECTION",
  "fields": [
    { "fieldPath": "user_id", "order": "ASCENDING" },
    { "fieldPath": "created_at", "order": "DESCENDING" }
  ]
},
{
  "collectionGroup": "saved_research_questions",
  "queryScope": "COLLECTION",
  "fields": [
    { "fieldPath": "workspace_id", "order": "ASCENDING" },
    { "fieldPath": "user_id", "order": "ASCENDING" },
    { "fieldPath": "created_at", "order": "DESCENDING" }
  ]
},
{
  "collectionGroup": "research_plans",
  "queryScope": "COLLECTION",
  "fields": [
    { "fieldPath": "workspace_id", "order": "ASCENDING" },
    { "fieldPath": "created_at", "order": "DESCENDING" }
  ]
},
{
  "collectionGroup": "research_plans",
  "queryScope": "COLLECTION",
  "fields": [
    { "fieldPath": "user_id", "order": "ASCENDING" },
    { "fieldPath": "created_at", "order": "DESCENDING" }
  ]
}
```

**Status:** ⚠️ Recommended to add missing indexes before production

### 2.3 Firestore Deployment

**Deployment Steps:**
- [ ] Deploy indexes to production Firebase project
- [ ] Command: `firebase deploy --only firestore:indexes`
- [ ] Verify indexes are created in Firebase console
- [ ] Monitor index creation status

**Status:** ⚠️ Manual deployment required

---

## 3. Authentication Configuration

### 3.1 Backend Authentication Configuration

**Required Variables:**
- [ ] `SECRET_KEY` - Strong random secret for JWT signing
- [ ] `AUTH_COOKIE_SAMESITE=none` - For cross-site HTTPS (Vercel + Render)
- [ ] `AUTH_COOKIE_SECURE=1` - Secure cookies for HTTPS
- [ ] `AUTH_COOKIE_DOMAIN=` - Empty for production (auto-detect)

**Google OAuth (Optional):**
- [ ] `GOOGLE_CLIENT_ID` - Google OAuth client ID
- [ ] `GOOGLE_CLIENT_SECRET` - Google OAuth client secret
- [ ] `GOOGLE_REDIRECT_URI` - Full backend URL + `/auth/google/callback`

**Email Verification:**
- [ ] `REQUIRE_EMAIL_VERIFICATION=1` - Require email verification for new users

**Status:** ✅ Configuration documented, values to be set

### 3.2 Frontend Authentication Configuration

**Firebase Auth:**
- [ ] `VITE_FIREBASE_AUTH_ENABLED=1` - Enable Firebase authentication
- [ ] Firebase Authentication enabled in Firebase console
- [ ] Google OAuth provider enabled in Firebase console
- [ ] Email/Password provider enabled in Firebase console

**Status:** ✅ Configuration documented, values to be set

### 3.3 Authentication Validation

**Backend Validation:**
- [ ] JWT token expiration configured (15 minutes access, 14 days refresh)
- [ ] Refresh token rotation implemented
- [ ] Session invalidation on password change
- [ ] Cookie security flags correct for HTTPS

**Frontend Validation:**
- [ ] Backend token stored in memory (not localStorage)
- [ ] Firebase auth session managed correctly
- [ ] Logout clears all tokens
- [ ] Token refresh on 401 responses

**Status:** ✅ Authentication properly implemented

---

## 4. CORS Configuration

### 4.1 Backend CORS Configuration

**Required Variables:**
- [ ] `FRONTEND_URL` - Production frontend URL (e.g., https://your-domain.vercel.app)
- [ ] `EXTRA_FRONTEND_URLS` - Additional allowed origins (comma-separated)
- [ ] `ALLOW_VERCEL_PREVIEW_CORS=0` - Disable preview CORS for production

**CORS Behavior:**
- [ ] FRONTEND_URL added to allowed origins
- [ ] Vercel preview URLs handled if ALLOW_VERCEL_PREVIEW_CORS=1
- [ ] Extra URLs parsed and added to allowed origins
- [ ] Credentials (cookies) allowed for CORS requests

**Status:** ✅ CORS properly configured via environment variables

### 4.2 CORS Validation

**Validation Steps:**
- [ ] Test CORS from production frontend to production backend
- [ ] Verify preflight OPTIONS requests succeed
- [ ] Verify credentials (cookies) sent with requests
- [ ] Verify no wildcard origins in production

**Status:** ⚠️ Manual validation required after deployment

---

## 5. Security Headers/CSP

### 5.1 Backend Security Headers Configuration

**Required Variables:**
- [ ] `SECURITY_HEADERS_ENABLED=1` - Enable security headers

**Headers Applied:**
- [ ] `X-Content-Type-Options: nosniff`
- [ ] `X-Frame-Options: DENY`
- [ ] `Referrer-Policy: strict-origin-when-cross-origin`
- [ ] `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- [ ] `Content-Security-Policy` - Configured via environment

**CSP Configuration:**
- [ ] CSP allows Firebase domains
- [ ] CSP allows production frontend domain
- [ ] CSP allows production backend domain
- [ ] CSP blocks inline scripts (except Firebase)
- [ ] CSP blocks eval()

**Status:** ✅ Security headers properly configured

### 5.2 Security Headers Validation

**Validation Steps:**
- [ ] Test security headers on production backend
- [ ] Verify CSP doesn't break Firebase
- [ ] Verify CSP doesn't break frontend
- [ ] Test CSP in staging environment first

**Status:** ⚠️ Manual validation required after deployment

---

## 6. API Base URLs

### 6.1 Backend API URL Configuration

**Required Variables:**
- [ ] `BACKEND_URL` - Production backend URL (e.g., https://your-service.onrender.com)
- [ ] Backend URL used for:
  - [ ] OAuth redirect URIs
  - [ ] CORS configuration
  - [ ] Internal references

**Status:** ✅ Configuration documented, value to be set

### 6.2 Frontend API URL Configuration

**Required Variables:**
- [ ] `VITE_API_URL` - Production backend URL (e.g., https://your-service.onrender.com)
- [ ] `VITE_API_BASE` - Alternative to VITE_API_URL
- [ ] `VITE_API_TIMEOUT_MS` - API timeout in milliseconds (default: 120000)

**API Resolution Priority:**
1. VITE_API_URL
2. VITE_API_BASE
3. http://localhost:8010 (development default)

**Status:** ⚠️ Must be set in production (defaults to localhost)

### 6.3 API URL Validation

**Validation Steps:**
- [ ] Verify VITE_API_URL set in Vercel environment
- [ ] Test API calls from frontend to backend
- [ ] Verify timeout configuration appropriate
- [ ] Verify long-running routes have extended timeouts

**Status:** ⚠️ Manual validation required after deployment

---

## 7. Frontend Production Build Configuration

### 7.1 Vite Build Configuration

**vite.config.ts:**
```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',      // Development-only
    port: 5173,             // Development-only
    strictPort: true        // Development-only
  },
  build: {
    chunkSizeWarningLimit: 2000,
  },
})
```

**Status:** ✅ Build configuration appropriate for production

### 7.2 TypeScript Configuration

**tsconfig.json:**
- [ ] Strict mode enabled
- [ ] No implicit any
- [ ] Strict null checks
- [ ] Module resolution: bundler

**Status:** ✅ TypeScript properly configured

### 7.3 Production Build Validation

**Build Steps:**
- [ ] Run `npm run build` - Production build
- [ ] Run `npm run lint` - Lint check
- [ ] Verify build output in `dist/` directory
- [ ] Verify no build errors
- [ ] Verify no TypeScript errors
- [ ] Verify chunk sizes reasonable

**Status:** ⚠️ Build validation required

---

## 8. Backend Production Startup Configuration

### 8.1 Docker Configuration

**Dockerfile:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV APP_ENV=production
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

**Status:** ✅ Docker configuration appropriate for production

### 8.2 Uvicorn Configuration

**Startup Command:**
- [ ] Host: 0.0.0.0 (bind to all interfaces)
- [ ] Port: ${PORT:-8000} (use PORT environment variable)
- [ ] Workers: Not specified (use Render default)
- [ ] Log level: INFO (default)

**Status:** ✅ Uvicorn configuration appropriate

### 8.3 Health Checks

**Health Check Endpoints:**
- [ ] `/health/live` - Liveness probe
- [ ] `/health/ready` - Readiness probe
- [ ] Render configured with `/health/live`

**Status:** ✅ Health checks configured

### 8.4 Production Startup Validation

**Validation Steps:**
- [ ] Verify Docker image builds successfully
- [ ] Verify container starts without errors
- [ ] Verify health check responds
- [ ] Verify environment variables loaded
- [ ] Verify Firebase connection established
- [ ] Verify no startup errors in logs

**Status:** ⚠️ Manual validation required after deployment

---

## 9. Rate Limiting Configuration

### 9.1 Rate Limiting Variables

**Required Variables:**
- [ ] `RATE_LIMIT_ENABLED=1` - Enable rate limiting
- [ ] `RATE_LIMIT_WINDOW_SECONDS=60` - Time window
- [ ] `RATE_LIMIT_AUTH_PER_WINDOW=90` - Authenticated requests per window
- [ ] `RATE_LIMIT_API_PER_WINDOW=300` - General API requests per window
- [ ] `RATE_LIMIT_STORE=memory` - Storage backend (should be redis for production)
- [ ] `REDIS_URL` - Redis URL if using redis store
- [ ] `ENFORCE_DISTRIBUTED_RATE_LIMIT=0` - Enforce redis requirement

**Status:** ⚠️ Should use redis for production

### 9.2 Rate Limiting Validation

**Validation Steps:**
- [ ] Test rate limiting on production
- [ ] Verify rate limit headers returned
- [ ] Verify 429 responses on limit exceeded
- [ ] Verify distributed rate limiting if using redis

**Status:** ⚠️ Manual validation required after deployment

---

## 10. Observability Configuration

### 10.1 Sentry Configuration

**Required Variables:**
- [ ] `SENTRY_DSN` - Sentry DSN for error tracking
- [ ] `SENTRY_ENVIRONMENT=production` - Environment name
- [ ] `SENTRY_RELEASE` - Release version
- [ ] `SENTRY_TRACES_SAMPLE_RATE=0.1` - Performance tracing sample rate
- [ ] `SENTRY_PROFILES_SAMPLE_RATE=0.0` - Profiling sample rate

**Status:** ⚠️ Should be configured for production

### 10.2 OpenTelemetry Configuration

**Optional Variables:**
- [ ] `OTEL_ENABLED=0` - Enable OpenTelemetry (optional)
- [ ] `OTEL_SERVICE_NAME=researchhub-backend` - Service name
- [ ] `OTEL_SERVICE_VERSION=1.0.0` - Service version
- [ ] `OTEL_ENVIRONMENT=production` - Environment
- [ ] `OTEL_EXPORTER_OTLP_ENDPOINT` - OTLP endpoint
- [ ] `OTEL_EXPORTER_OTLP_HEADERS` - OTLP headers
- [ ] `OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS=10` - Timeout

**Status:** ℹ️ Optional configuration

---

## 11. Summary Checklist

### Must Complete Before Production

**Firebase Configuration:**
- [ ] Set FIREBASE_PROJECT_ID
- [ ] Set FIREBASE_STORAGE_BUCKET
- [ ] Configure Firebase service account credentials
- [ ] Set all VITE_FIREBASE_* variables
- [ ] Enable FIREBASE_APPCHECK_ENFORCED=1
- [ ] Configure AppCheck site key

**Firestore Configuration:**
- [ ] Deploy existing indexes to production
- [ ] Add missing indexes for research collections
- [ ] Deploy new indexes to production

**Authentication Configuration:**
- [ ] Set SECRET_KEY
- [ ] Set AUTH_COOKIE_SAMESITE=none
- [ ] Set AUTH_COOKIE_SECURE=1
- [ ] Configure Google OAuth (if using)
- [ ] Set REQUIRE_EMAIL_VERIFICATION=1

**CORS Configuration:**
- [ ] Set FRONTEND_URL to production domain
- [ ] Set ALLOW_VERCEL_PREVIEW_CORS=0
- [ ] Set EXTRA_FRONTEND_URLS if needed

**Security Headers:**
- [ ] Set SECURITY_HEADERS_ENABLED=1
- [ ] Test CSP in staging environment

**API Configuration:**
- [ ] Set BACKEND_URL
- [ ] Set VITE_API_URL in Vercel
- [ ] Set VITE_API_TIMEOUT_MS if needed

**Rate Limiting:**
- [ ] Set RATE_LIMIT_ENABLED=1
- [ ] Consider setting RATE_LIMIT_STORE=redis
- [ ] Configure REDIS_URL if using redis

**Observability:**
- [ ] Set SENTRY_DSN
- [ ] Set SENTRY_RELEASE
- [ ] Configure OpenTelemetry if desired

### Should Complete Before Production

- [ ] Remove or document emulator configuration in firebase.json
- [ ] Create frontend .env.example file
- [ ] Update FRONTEND_URL to placeholder in example file
- [ ] Test CSP in staging environment
- [ ] Test CORS in staging environment
- [ ] Test rate limiting in staging environment

---

## 12. Production Environment Status

**Configuration Status:** READY ✅
- All required configurations documented
- All configurations environment-variable driven
- No hardcoded production values
- No secrets in code

**Action Required:** SET VALUES ⚠️
- All environment variables must be set with real values
- Firestore indexes must be deployed
- Firebase console configuration must be completed
- Manual validation required after deployment

**Overall Assessment:** Production environment configuration is properly structured and documented. All required variables are identified with clear documentation. The main remaining work is setting actual values and deploying Firestore indexes.

---

**Checklist Date:** 2026-08-21  
**Status:** COMPLETE
