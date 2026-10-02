# Soyog AI - Comprehensive Project Documentation

**Version:** 1.0  
**Last Updated:** 2026-10-02  
**Project Type:** AI-Native Research Workspace for Scientific Literature

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Features](#features)
5. [Development Setup](#development-setup)
6. [Deployment](#deployment)
7. [Issues Encountered & Solutions](#issues-encountered--solutions)
8. [Dos and Don'ts](#dos-and-donts)
9. [CLI Tools](#cli-tools)
10. [Approaches & Methodologies](#approaches--methodologies)
11. [Security Best Practices](#security-best-practices)
12. [Testing](#testing)
13. [Monitoring & Observability](#monitoring--observability)
14. [Troubleshooting](#troubleshooting)

---

## Project Overview

Soyog AI (formerly ResearchHub-AI) is an AI-native research workspace designed for scientific literature workflows. It provides a complete research operating surface that integrates paper discovery, workspace curation, AI synthesis, and exportable research deliverables.

### Core Value Proposition

Instead of fragmented tools (Google Scholar, Zotero, chatbots, etc.), Soyog AI provides:
- **Multi-source discovery:** 28+ connected research rails
- **Workspace memory:** Persistent project context across papers, chat, and exports
- **AI synthesis:** Grounded AI analysis within workspace context
- **Exportable output:** BibTeX, CSV, PDF, DOCX with proper structure

### Target Users

- Academic researchers
- PhD students
- Literature review teams
- Research lab coordinators
- Anyone conducting systematic literature reviews

---

## Architecture

### High-Level System Architecture

```
Browser (Vercel)
  ↓
React SPA (TypeScript + Vite)
  ↓
FastAPI Backend (Render)
  ↓
├─ Firebase Firestore (primary database)
├─ Firebase Storage (file storage)
├─ Groq (LLM inference)
├─ Redis (distributed rate limiting)
└─ External APIs (OpenAlex, Crossref, Europe PMC, etc.)
```

### Repository Structure

```
ResearchHub-AI/
├── backend/              # FastAPI backend
│   ├── main.py          # Application entry point, middleware
│   ├── routers/          # API route handlers
│   ├── repositories/    # Data access layer
│   ├── services/         # Business logic
│   ├── utils/            # Utilities (Firebase, storage, etc.)
│   ├── tests/            # Backend tests
│   └── requirements.txt # Python dependencies
├── frontend/            # React frontend
│   ├── src/
│   │   ├── pages/       # Page components
│   │   ├── components/  # Reusable components
│   │   ├── features/    # Feature-specific components
│   │   ├── utils/       # Utilities (API, auth, Firebase)
│   │   └── api.ts       # API client
│   ├── package.json
│   └── vite.config.ts
├── docs/                # Documentation
├── deploy/              # Deployment configurations
└── ops/                 # Operational runbooks
```

### Key Architectural Decisions

1. **Firestore-First Persistence:** Primary database is Firestore for scalability and real-time capabilities
2. **JWT + Refresh Token Rotation:** Secure session management with HTTP-only cookies
3. **Firebase AppCheck:** Protects against unauthorized client access
4. **Redis Distributed Rate Limiting:** Prevents abuse across multiple instances
5. **Separate Auth Layer:** External identity providers (Google, Firebase) feed into backend session layer
6. **Repository Pattern:** Clean separation between data access and business logic

---

## Tech Stack

### Backend
- **Framework:** FastAPI 0.142.0+
- **Python:** 3.13.5
- **Database:** Firebase Firestore
- **Storage:** Firebase Storage
- **AI/LLM:** Groq (LLaMA models)
- **Caching:** Redis 8.1.0
- **Authentication:** JWT (HS256), Firebase Auth integration
- **Email:** aiosmtplib
- **Vector Storage:** SentenceTransformers (local)
- **PDF Processing:** PyMuPDF, pdfplumber
- **Testing:** pytest

### Frontend
- **Framework:** React 19.2.7
- **Build Tool:** Vite 7.3.1
- **Language:** TypeScript 5.9.3
- **Styling:** Tailwind CSS 3.4.19
- **State Management:** React Context, hooks
- **Routing:** React Router 7.18.1
- **HTTP Client:** Axios 1.18.1
- **Firebase:** Firebase SDK 10.14.1, AppCheck SDK
- **Deployment:** Vercel

### Infrastructure
- **Backend Hosting:** Render
- **Frontend Hosting:** Vercel
- **Database:** Firebase Firestore
- **Storage:** Firebase Storage
- **Caching:** Render Redis (Key Value)
- **Monitoring:** Sentry
- **CI/CD:** GitHub Actions

---

## Features

### 1. Multi-Source Paper Discovery
- **Sources:** OpenAlex, Crossref, Europe PMC, PubMed, PMC, DOAJ, ERIC, OSTI, EconBiz, J-STAGE, ORKG, HAL, bioRxiv, medRxiv, PLOS, eLife
- **Unified Search:** Single search across all sources
- **Advanced Filters:** Year, source, access type, field of study
- **Real-time Results:** Fast aggregation from multiple APIs

### 2. Workspace Management
- **Create Workspaces:** Organize papers by research project
- **Workspace Context:** All AI operations respect workspace boundaries
- **Paper Organization:** Import papers into specific workspaces
- **Collaboration:** Workspace-level access control
- **Session Persistence:** Resume where you left off

### 3. AI-Powered Analysis
- **Paper Summarization:** AI-generated summaries from PDF uploads
- **Evidence Intelligence:** Extract and analyze claims from papers
- **Gap Detection:** Identify research gaps and opportunities
- **Research Questions:** Generate research questions from gaps
- **Hypothesis Challenger:** Test hypotheses against evidence
- **Citation Verification:** Verify citation integrity
- **Knowledge Graph Enhancement:** Build knowledge relationships

### 4. Research Intelligence Pipeline
- **End-to-End Workflow:** Discovery → Curation → Synthesis → Export
- **Stage-by-Stage Execution:** Control each analysis step
- **Artifact Management:** Save and revisit intelligence artifacts
- **Provenance Tracking:** Trace evidence back to source papers

### 5. Chat & Q&A
- **Workspace-Aware Chat:** AI context limited to workspace papers
- **Question-Answer:** Ask questions about imported papers
- **Evidence-Based Responses:** Answers grounded in actual content
- **Conversation History:** Maintain research dialogue

### 6. Export & Documentation
- **BibTeX Export:** Standard citation format
- **CSV Export:** Spreadsheet-compatible data
- **PDF Reports:** Formatted research reports
- **DOCX Export:** Word document compatibility
- **Metadata Preservation:** DOI, authors, publication info

### 7. User Management
- **Email/Password Authentication:** Traditional auth
- **Google OAuth:** Google account sign-in
- **Firebase Auth Integration:** Firebase identity provider
- **Email Verification:** Required for production
- **Password Reset:** Secure password recovery
- **Profile Management:** Update user information

### 8. Analytics & Insights
- **Workspace Analytics:** Activity metrics and trends
- **Feed Generation:** AI-powered activity summaries
- **Usage Tracking:** Monitor research throughput
- **Developer Console:** Operational diagnostics

### 9. Security Features
- **JWT Authentication:** Secure token-based auth
- **Refresh Token Rotation:** Automatic token refresh
- **HTTP-Only Cookies:** Prevents XSS token theft
- **Firebase AppCheck:** Protects against unauthorized clients
- **Rate Limiting:** Redis-backed distributed rate limiting
- **Metrics Protection:** Token-based operational endpoint access
- **CORS Control:** Strict origin whitelisting
- **Security Headers:** HSTS, CSP, X-Frame-Options, etc.

### 10. Developer Features
- **Health Endpoints:** `/health/live`, `/health/ready`
- **Metrics Endpoints:** `/ops/metrics`, `/ops/slo`
- **Structured Logging:** JSON logs with request IDs
- **Error Tracking:** Sentry integration
- **Feature Flags:** Runtime feature toggles

---

## Development Setup

### Prerequisites

- Python 3.13+
- Node.js 18+
- Render CLI (for deployment)
- Firebase project (for Firestore/Storage)
- Groq API key (for AI features)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values

# Run backend
uvicorn main:app --host 0.0.0.0 --port 8010 --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with your values

# Run dev server
npm run dev
```

### Firebase Configuration

1. Create Firebase project
2. Enable Firestore and Storage
3. Download service account credentials
4. Set environment variables:
   - `FIREBASE_PROJECT_ID`
   - `FIREBASE_STORAGE_BUCKET`
   - `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64` (recommended)

### Google OAuth Configuration

1. Create OAuth 2.0 credentials in Google Cloud Console
2. Add `https://researchhub-ai-r8j3.onrender.com/auth/google/callback` to authorized redirect URIs
3. Set environment variables:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`

---

## Deployment

### Backend Deployment (Render)

```bash
# Install Render CLI
# (Follow instructions at https://render.com/docs/cli)

# Login
render login

# Deploy backend
cd ResearchHub-AI
render deploy backend --region oregon --confirm
```

**Required Environment Variables:**
- `APP_ENV=production`
- `SECRET_KEY` (strong random value)
- `FIREBASE_PROJECT_ID`
- `FIREBASE_STORAGE_BUCKET`
- `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64`
- `GROQ_API_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `FRONTEND_URL=https://research-hub-ai-lime.vercel.app`
- `BACKEND_URL=https://researchhub-ai-r8j3.onrender.com`
- `AUTH_COOKIE_SAMESITE=none`
- `AUTH_COOKIE_SECURE=1`
- `RATE_LIMIT_STORE=redis`
- `REDIS_URL=<your-redis-url>`
- `ENFORCE_DISTRIBUTED_RATE_LIMIT=1`
- `FIREBASE_APPCHECK_ENFORCED=1`
- `METRICS_AUTH_TOKEN=<random-token>`

### Frontend Deployment (Vercel)

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy frontend
cd frontend
vercel --prod
```

**Required Environment Variables:**
- `VITE_API_URL=https://researchhub-ai-r8j3.onrender.com`
- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_STORAGE_BUCKET`
- `VITE_FIREBASE_MESSAGING_SENDER_ID`
- `VITE_FIREBASE_APP_ID`
- `VITE_FIREBASE_MEASUREMENT_ID`
- `VITE_FIREBASE_APPCHECK_PROVIDER=enterprise`
- `VITE_FIREBASE_RECAPTCHA_ENTERPRISE_SITE_KEY`

### Redis Setup (Render)

1. Go to Render dashboard → New → Key Value
2. Create Redis instance
3. Get connection URL: `redis://red-xxxxx:6379`
4. Add to backend environment variables

---

## Issues Encountered & Solutions

### 1. Render CLI Path Issues

**Problem:** Render CLI not found on PATH  
**Solution:** Use full executable path:  
```powershell
& "C:\Users\Girish P\AppData\Local\Microsoft\WinGet\Packages\Render.CLI_Microsoft.Winget.Source_8wekyb3bbwe\render.exe"
```

### 2. Redis Command Not Found

**Problem:** `render redis` command doesn't exist  
**Solution:** Use Key Value instead:  
```bash
render keyvalues
```

### 3. Python Dependency Conflicts

**Problem:** Multiple packages requiring different versions of dependencies  
**Solution:** Updated to latest compatible versions:
- FastAPI: 0.104.1 → 0.142.2
- Pydantic: 2.9.2 → 2.13.5
- Uvicorn: 0.24.0 → 0.54.0
- aiohttp: 3.13.3 → 3.13.4
- grpcio: 1.78.0 → 1.84.0
- urllib3: 2.6.3 → 2.8.0
- httpx: 0.25.2 → 0.28.1

### 4. Bcrypt Compatibility

**Problem:** Passlib 1.7.4 looks for `bcrypt.__about__.__version__` removed in bcrypt 4.x  
**Solution:** Added compatibility patch in `main.py`:
```python
import bcrypt as _bcrypt
if not hasattr(_bcrypt, "__about__"):
    class _About:
        __version__ = getattr(_bcrypt, "__version__", "4.0.1")
    _bcrypt.__about__ = _About()
```

### 5. Firebase AppCheck Blocking Auth

**Problem:** Firebase AppCheck enforced on backend blocked all auth requests  
**Solution:** Modified backend to exclude `/auth/` paths from AppCheck enforcement:
```python
if FIREBASE_APPCHECK_ENFORCED:
    if not request.url.path.startswith(("/health/", "/docs", "/redoc", "/openapi.json", "/auth/")):
        # Check AppCheck token
```

### 6. Frontend Axios Relative URLs in Production

**Problem:** Axios used relative URLs causing 404s in production  
**Solution:** Set full API URL in Axios client:
```typescript
const api = axios.create({
  baseURL: API_URL, // Full URL in production
  withCredentials: true,
});
```

### 7. npm Update Syntax Errors

**Problem:** `npm update package@version` doesn't accept version specifiers  
**Solution:** Use `npm install package@version` instead

### 8. GitLab Render Deployment Sync Issues

**Problem:** Render deploying old commits from GitLab instead of latest GitHub commits  
**Solution:** Ensure both GitHub and GitLab are in sync, use `git push gitlab main --force` when needed

### 9. Environment Variables Not Applied

**Problem:** Render warnings about Redis/AppCheck/Metrics not configured  
**Solution:** Save environment variables BEFORE triggering deploy, then redeploy

### 10. Duplicate Environment Variables

**Problem:** Duplicate entries in Render Environment tab  
**Solution:** Delete duplicates, keep one of each, save, then redeploy

### 11. Vercel Variable Naming Mismatch

**Problem:** User created `VITE_RECAPTCHA_ENTERPRISE_SITE_KEY` but code expects `VITE_FIREBASE_RECAPTCHA_ENTERPRISE_SITE_KEY`  
**Solution:** Created correct variable name in Vercel

### 12. Research Question TODO Implementation

**Problem:** TODO comment for "add to workspace" functionality  
**Solution:** Implemented using `saveResearchQuestion` API with proper error handling

### 13. Test Import Error for grpcio

**Problem:** `import grpcio` failed (module is `grpc`)  
**Solution:** Changed test to use correct import: `import grpc`

### 14. CORS Issues with Vercel Previews

**Problem:** CORS blocking Vercel preview origins  
**Solution:** Added `ALLOW_VERCEL_PREVIEW_CORS=1` and regex pattern for preview origins

### 15. Cookie SameSite Configuration

**Problem:** Cookies not working with Vercel+Render HTTPS setup  
**Solution:** Set `AUTH_COOKIE_SAMESITE=none` and `AUTH_COOKIE_SECURE=1`

### 16. Firebase Service Account Loading

**Problem:** Multiple ways to load service account credentials causing confusion  
**Solution:** Created `firebase_service_account.py` with fallback chain:
1. Base64-encoded JSON
2. Raw JSON
3. Split environment variables

### 17. Production SECRET_KEY Enforcement

**Problem:** Startup failing if SECRET_KEY not set in production  
**Solution:** Added runtime check in `main.py`:
```python
if APP_ENV != "development" and (not SECRET_KEY or SECRET_KEY == "secret"):
    raise RuntimeError("SECRET_KEY must be set and not 'secret' in production")
```

### 18. Rate Limiting Without Redis

**Problem:** Per-instance rate limiting in production  
**Solution:** Configured Redis and set `RATE_LIMIT_STORE=redis`, `ENFORCE_DISTRIBUTED_RATE_LIMIT=1`

### 19. Metrics Endpoint Unprotected

**Problem:** `/ops/metrics` publicly accessible  
**Solution:** Added `METRICS_AUTH_TOKEN` and header check

### 20. Frontend 404 Page Missing

**Problem:** Invalid URLs showed React Router 404  
**Solution:** Created custom `NotFound.tsx` component with catch-all route

### 21. Logo Not Clickable

**Problem:** Users expected logo to navigate to home  
**Solution:** Wrapped logo in Link component

### 22. Frontend Build TypeScript Errors

**Problem:** Type mismatches in research question save  
**Solution:** Fixed API call to match `SaveResearchQuestionRequest` interface

---

## Dos and Don'ts

### Dos

#### Development
- ✅ Use virtual environments for Python
- ✅ Use `.env.example` for template environment variables
- ✅ Run tests before committing
- ✅ Use type checking (TypeScript)
- ✅ Follow existing code patterns
- ✅ Write tests for new features
- ✅ Update documentation when changing architecture
- ✅ Use feature flags for experimental features
- ✅ Validate inputs server-side
- ✅ Sanitize user content
- ✅ Use structured logging
- ✅ Add request IDs for debugging
- ✅ Implement graceful degradation for optional features

#### Security
- ✅ Use environment variables for secrets
- ✅ Never commit secrets to git
- ✅ Use HTTPS in production
- ✅ Set secure cookie flags
- ✅ Implement rate limiting
- ✅ Validate all inputs
- ✅ Use parameterized queries
- ✅ Implement proper error handling
- ✅ Use security headers
- ✅ Regularly update dependencies
- ✅ Run security audits
- ✅ Use AppCheck for mobile apps
- ✅ Implement CORS properly
- ✅ Use strong password policies
- ✅ Hash passwords (bcrypt/PBKDF2)

#### Deployment
- ✅ Use different configs for dev/prod
- ✅ Use environment-specific feature flags
- ✅ Monitor deployment logs
- ✅ Use proper health checks
- ✅ Implement graceful shutdowns
- ✅ Use build caches
- ✅ Separate secrets from code
- ✅ Use CI/CD for deployments
- ✅ Test in staging first
- ✅ Monitor error rates

#### Code Quality
- ✅ Follow consistent naming conventions
- ✅ Write self-documenting code
- ✅ Add comments for complex logic
- ✅ Keep functions small and focused
- ✅ Use type hints
- ✅ Add docstrings for public APIs
- ✅ Run linters
- ✅ Format code consistently
- ✅ Review code before merging

### Don'ts

#### Development
- ❌ Don't commit `.env` files
- ❌ Don't hardcode secrets
- ❌ Don't skip tests
- ❌ Don't ignore type errors
- ❌ Don't use deprecated APIs
- ❌ Don't block the event loop
- ❌ Don't create memory leaks
- ❌ Don't ignore warnings
- ❌ Don't duplicate code
- ❌ Don't over-engineer
- ❌ Don't skip documentation

#### Security
- ❌ Don't expose stack traces to users
- ❌ Don't trust frontend input
- ❌ Don't use eval() or exec()
- ❌ Don't use weak encryption
- ❌ Don't store plain text passwords
- ❌ Don't ignore CVEs
- ❌ Don't use wildcard CORS
- ❌ Don't disable security headers
- ❌ Don't log sensitive data
- ❌ Don't ignore error handling
- ❌ Don't use GET for mutations
- ❌ Don't implement your own crypto

#### Deployment
- ❌ Don't use development configs in production
- ❌ Don't skip health checks
- ❌ Don't ignore deployment errors
- ❌ Don't deploy without testing
- ❌ Don't use latest tag blindly
- ❌ Don't ignore rollback plans
- ❌ Don't disable monitoring
- ❌ Don't skip environment validation
- ❌ Don't deploy broken builds

#### Code Quality
- ❌ Don't write spaghetti code
- ❌ Don't copy-paste without understanding
- ❌ Don't ignore performance
- ❌ Don't skip error handling
- ❌ Don't use magic numbers
- ❌ Don't create circular dependencies
- ❌ Don't write God classes
- ❌ Don't ignore accessibility
- ❌ Don't break existing functionality

---

## CLI Tools

### Development Tools

#### Render CLI
```bash
# Install
winget install Render.CLI

# Usage
render login
render deploys list <service-id>
render deploys create <service-id> --confirm --wait
render logs <service-id>
```

#### Vercel CLI
```bash
# Install
npm i -g vercel

# Usage
vercel login
vercel --prod
vercel logs
```

#### Firebase CLI
```bash
# Install
npm install -g firebase-tools

# Usage
firebase login
firebase init
firebase deploy
firebase firestore:rules
firebase storage:rules
```

#### Git
```bash
# Standard workflow
git add .
git commit -m "message"
git push origin main
git push gitlab main
```

#### Python Tools
```bash
# Virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Package management
pip install -r requirements.txt
pip freeze > requirements.txt
pip audit

# Testing
pytest
pytest -v
pytest --cov
```

#### Node.js Tools
```bash
# Package management
npm install
npm install <package>
npm update

# Scripts
npm run dev
npm run build
npm run lint
npm test
```

### Production Tools

#### Sentry (Error Tracking)
```bash
# Configuration via environment variables
SENTRY_DSN=<your-dsn>
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=1.0
```

#### Google Cloud Logging
```bash
# Enabled via environment variables
GOOGLE_CLOUD_PROJECT=<project-id>
GOOGLE_CLOUD_LOGGING_ENABLED=1
```

---

## Approaches & Methodologies

### 1. Architecture Decisions

#### Firestore-First Persistence
**Rationale:** Scalability, real-time capabilities, serverless pricing  
**Approach:** Used Firestore as primary database with repository pattern  
**Benefits:** Automatic scaling, real-time listeners, built-in security rules

#### JWT + Refresh Token Rotation
**Rationale:** Stateless auth, security, user experience  
**Approach:** Short-lived access tokens (15min) with rotating refresh tokens (14 days)  
**Benefits:** Compromise between security and UX, token revocation capability

#### Separate Auth Layer
**Rationale:** Multiple identity providers need unified session management  
**Approach:** External providers (Google, Firebase) feed into backend JWT sessions  
**Benefits:** Consistent auth experience, provider independence, easier migration

#### Repository Pattern
**Rationale:** Clean separation of concerns, testability  
**Approach:** Repository classes abstract data access from business logic  
**Benefits:** Easy to swap databases, mock for testing, consistent data access

### 2. Security Approach

#### Defense in Depth
- Network: HTTPS, HSTS
- Application: CORS, rate limiting, AppCheck
- Data: Firestore rules, encryption
- Secrets: Environment variables, secret manager

#### Principle of Least Privilege
- Firestore rules enforce ownership
- Admin endpoints require email whitelist
- Developer endpoints require header key or email
- API rate limiting by endpoint type

#### Fail Secure
- Production SECRET_KEY enforcement
- Graceful degradation for optional features
- Structured error responses (no stack traces)
- Request IDs for debugging

### 3. Performance Optimization

#### Code Splitting
- React lazy loading for routes
- Dynamic imports for large components
- Vite automatic chunking

#### Caching Strategy
- Firestore query results
- AI response caching (configurable)
- Redis for distributed rate limiting
- Browser cache for static assets

#### Database Optimization
- Firestore indexes on query fields
- Pagination for large datasets
- Selective field retrieval

### 4. Testing Strategy

#### Test Pyramid
- Unit tests: Services, repositories, utilities
- Integration tests: API endpoints, auth flows
- E2E tests: Critical user journeys
- Golden path tests: Registration → login → workspace → research

#### Test Environment
- In-memory repository for fast tests
- Firebase emulator for auth tests
- Mock external APIs (scholarly sources)

#### CI/CD Integration
- GitHub Actions for automated testing
- Pre-push hooks for quick validation
- Security scanning for secrets

### 5. Deployment Strategy

#### Infrastructure as Code
- Render blueprint for reproducible deployments
- Environment variable management
- Docker for consistent runtime

#### Blue-Green Deployment
- Render auto-deploys on push
- Health checks before routing traffic
- Rollback via previous commit

#### Monitoring
- Sentry for error tracking
- Google Cloud Logging for structured logs
- Custom metrics endpoint for SLO tracking

### 6. Error Handling Approach

#### Structured Errors
- Custom error codes (`UNAUTHORIZED`, `VALIDATION_ERROR`, etc.)
- Request IDs for traceability
- User-friendly messages, technical details in logs

#### Graceful Degradation
- Optional features fail silently (AI, Firebase AppCheck)
- Fallback to basic functionality
- Clear error messages to users

#### Retry Logic
- Refresh token auto-retry with mutex lock
- AI request timeout and retry
- Database operation retry with exponential backoff

### 7. Firebase Integration Approach

#### Service Account Management
- Base64 encoding for Render compatibility
- Fallback chain: base64 → raw JSON → split fields
- Environment variable parsing with quote handling

#### Firestore Security Rules
- Ownership-based access control
- Write operations via backend only
- Recursive workspace ownership checks

#### Storage Security Rules
- File size validation (20MB limit)
- MIME type validation
- Path-based ownership (user/workspace IDs)

### 8. External API Integration

#### Scholarly Source Adapters
- Unified adapter pattern for 28+ sources
- Rate limiting per source
- Error handling and fallback
- Response normalization

#### Groq AI Integration
- Model routing for different tasks
- Timeout handling for long operations
- Streaming vs non-streaming selection
- Error degradation strategies

### 9. Frontend State Management

#### React Context API
- Auth context for session state
- Toast context for notifications
- Theme context for dark mode
- Avoided Redux for simplicity

#### Data Fetching
- Axios interceptors for auth tokens
- AppCheck token inclusion
- Automatic retry on 401 (refresh token)
- Request/response error normalization

### 10. Performance Monitoring

#### Custom Metrics
- Request counting by path
- Latency percentiles (p50, p95, p99)
- Rate limit tracking
- Failure spike detection

#### SLO Tracking
- Availability percentage
- Response time targets
- Automatic alerting on degradation

---

## Security Best Practices

### 1. Secrets Management
- **Rule:** Never commit secrets to git
- **Implementation:** `.gitignore` excludes `.env`, service account files
- **Check:** `git log --all --full-history -- .env service-account credentials`

### 2. Authentication
- **Rule:** Always use server-side validation
- **Implementation:** JWT tokens, refresh rotation, HTTP-only cookies
- **Check:** Verify all protected routes use `get_current_user`

### 3. Authorization
- **Rule:** Never trust frontend user IDs
- **Implementation:** Derive user ID from JWT token
- **Check:** Ensure repository methods use authenticated user ID

### 4. Data Isolation
- **Rule:** Enforce ownership at database level
- **Implementation:** Firestore rules with `isOwner`, `isWorkspaceOwner`
- **Check:** Test user A cannot access user B's data

### 5. Input Validation
- **Rule:** Validate all inputs server-side
- **Implementation:** Pydantic models, type checking, length limits
- **Check:** Test with malformed/malicious inputs

### 6. Rate Limiting
- **Rule:** Protect against abuse
- **Implementation:** Redis-backed distributed rate limiting
- **Check:** Verify limits enforced across instances

### 7. CORS
- **Rule:** Restrict to trusted origins
- **Implementation:** Whitelist production origin, preview regex
- **Check:** Test CORS preflight requests

### 8. Security Headers
- **Rule:** Apply security headers in production
- **Implementation:** HSTS, CSP, X-Frame-Options, etc.
- **Check:** Verify headers in response

### 9. Error Handling
- **Rule:** Never expose stack traces
- **Implementation:** Generic error messages, detailed logs
- **Check:** Test error responses don't leak details

### 10. Dependency Management
- **Rule:** Keep dependencies updated
- **Implementation:** Regular `pip audit`, `npm audit`
- **Check:** Review and fix high-severity CVEs

---

## Testing

### Backend Tests

```bash
cd backend
pytest
pytest -v                    # Verbose output
pytest --cov              # Coverage report
pytest tests/test_additional.py  # Specific test file
```

### Frontend Tests

```bash
cd frontend
npm run lint              # ESLint
npm run build             # TypeScript + Vite build
npm run test:e2e          # Playwright E2E tests
```

### Test Coverage

- **Backend:** 352 tests covering:
  - Authentication flows
  - Workspace isolation
  - Paper operations
  - AI services
  - Research intelligence
  - Citation verification
  - Gap detection
  - Knowledge graph
  - Saved questions
  - System validation

- **Frontend:** E2E tests for:
  - User registration
  - Login/logout
  - Workspace creation
  - Paper import
  - Research workflows

---

## Monitoring & Observability

### Health Endpoints

```bash
# Liveness check
curl https://researchhub-ai-r8j3.onrender.com/health/live

# Readiness check (includes database)
curl https://researchhub-ai-r8j3.onrender.com/health/ready
```

### Metrics Endpoints

```bash
# SLO metrics (requires METRICS_AUTH_TOKEN)
curl -H "X-Metrics-Token: <token>" https://researchhub-ai-r8j3.onrender.com/ops/slo

# Detailed metrics (requires METRICS_AUTH_TOKEN)
curl -H "X-Metrics-Token: <token>" https://researchhub-ai-r8j3.onrender.com/ops/metrics
```

### Google Cloud Logging

Structured JSON logs with:
- `event`: Log event type
- `request_id`: Unique request identifier
- `user_id`: Authenticated user ID
- `path`: Request path
- `method`: HTTP method
- `status_code`: Response status
- `duration_ms`: Request duration
- `logging.googleapis.com/trace`: Cloud Trace context

### Sentry Error Tracking

Enabled via environment variables:
- `SENTRY_DSN`: Sentry project DSN
- `SENTRY_ENVIRONMENT`: Environment name
- `SENTRY_TRACES_SAMPLE_RATE`: Sample rate for traces
- `SENTRY_PROFILES_SAMPLE_RATE`: Sample rate for profiles

---

## Troubleshooting

### Backend Won't Start

**Check:**
1. Environment variables loaded correctly
2. SECRET_KEY set (production)
3. Firebase credentials valid
4. Redis connection (if configured)

**Command:**
```bash
# Check logs
render logs <service-id>

# Check health
curl https://researchhub-ai-r8j3.onrender.com/health/live
```

### Frontend Can't Reach Backend

**Check:**
1. API_URL environment variable correct
2. Backend service healthy
3. CORS configuration
4. Network connectivity

**Command:**
```bash
# Test backend directly
curl https://researchhub-ai-r8j3.onrender.com/health/live

# Check frontend API URL
console.log(import.meta.env.VITE_API_URL)
```

### Google OAuth Fails

**Check:**
1. OAuth credentials configured
2. Redirect URI matches exactly
3. OAuth state cookie not corrupted

**Command:**
```bash
# Check OAuth status
curl https://researchhub-ai-r8j3.onrender.com/auth/google/status
```

### Firebase AppCheck Errors

**Check:**
1. AppCheck enforced in backend
2. Site key configured in frontend
3. Token generation working

**Solution:**
- Disable AppCheck in development: `FIREBASE_APPCHECK_ALLOW_LOCALHOST=1`
- Skip auth endpoints from AppCheck enforcement

### Rate Limiting Too Aggressive

**Check:**
1. Rate limit configuration
2. Redis connection
3. User behavior patterns

**Solution:**
- Adjust `RATE_LIMIT_AUTH_PER_WINDOW`
- Adjust `RATE_LIMIT_API_PER_WINDOW`
- Adjust `RATE_LIMIT_WINDOW_SECONDS`

### Tests Failing

**Check:**
1. Environment variables set for tests
2. Firebase emulator running (if needed)
3. Dependencies installed

**Command:**
```bash
# Run with verbose output
pytest -v

# Run specific test with output
pytest tests/test_auth.py::test_login -v -s
```

### Deployment Fails

**Check:**
1. Git history matches deploy trigger
2. Environment variables configured
3. Build logs for errors
4. Health checks passing

**Solution:**
- Check Render/GitLab sync
- Verify environment variables saved
- Review build logs
- Test locally with production config

---

## Performance Considerations

### Database Queries
- Use Firestore indexes on frequently queried fields
- Limit result sets with pagination
- Select only needed fields
- Avoid N+1 queries

### AI Operations
- Stream responses when possible
- Set appropriate timeouts
- Cache frequently asked questions
- Use shorter models for simple tasks

### Frontend Bundle Size
- Code splitting for routes
- Lazy load heavy components
- Tree-shake unused code
- Optimize images

### Network Requests
- Batch API calls when possible
- Use HTTP/2 multiplexing
- Implement request deduplication
- Cache static assets

---

## Known Limitations

1. **Vector Storage:** Currently uses local SentenceTransformers, not cloud vector DB
2. **Search Refresh:** External source data may be slightly stale
3. **AI Model:** Limited to Groq-hosted models
4. **File Upload:** Limited to PDF files, 20MB max
5. **Workspace Size:** No hard limit, but Firestore document size limits apply
6. **Concurrent Users:** Rate limiting may affect heavy users

---

## Future Enhancements

1. **Cloud Vector Database:** Pinecone or Weaviate for scalable vector storage
2. **Advanced AI Models:** Support for more LLM providers
3. **Real-time Collaboration:** WebSocket-based collaborative editing
4. **Advanced Analytics:** Deeper usage insights and recommendations
5. **Mobile Apps:** Native iOS and Android applications
6. **API Rate Limiting:** Per-user API quotas for power users
7. **Custom Integrations:** Zapier-style integrations with other tools
8. **Advanced Export:** More export formats (LaTeX, Markdown, JSON)

---

## Contributing

### Development Workflow

1. Create feature branch from `main`
2. Make changes with tests
3. Run tests locally
4. Submit pull request
5. Code review
6. Merge to main
7. Auto-deploy to staging
8. Manual deploy to production

### Code Style

- Follow existing patterns
- Use type hints
- Add docstrings for public APIs
- Keep functions small
- Write self-documenting code

### Commit Messages

- Use conventional commits
- Explain "why" not "what"
- Reference related issues
- Keep messages concise

---

## Support

### Documentation
- `SECURITY_AUDIT_REPORT.md` - Security audit findings
- `DEPENDENCY_UPDATE_REPORT.md` - Dependency update details
- `DEPLOYMENT_SUMMARY.md` - Deployment status
- `PRODUCTION_READINESS_AUDIT_REPORT.md` - Complete audit report

### Runbooks
- `ops/runbooks/` - Operational procedures
- `docs/` - Architecture and feature documentation

### Issues
- GitHub Issues: https://github.com/khrish11/ResearchHub-AI/issues
- Email: girish122006@gmail.com

---

## License

Proprietary - All rights reserved

---

## Acknowledgments

- Firebase: Authentication, Firestore, Storage
- Groq: AI model hosting
- Render: Backend hosting
- Vercel: Frontend hosting
- OpenAlex, Crossref, Europe PMC: Research source APIs
- Open-source community: Python and JavaScript ecosystems

---

**This documentation is a living document and will be updated as the project evolves.**
