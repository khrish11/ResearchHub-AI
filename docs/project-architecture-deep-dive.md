# Soyog AI Project And Architecture Deep Dive

## Purpose Of This Document

This document explains what Soyog AI is, how the current codebase is organized, how requests move through the system, how data is stored, how AI is integrated, and where the main architectural boundaries are.

It is written against the current repository structure and runtime behavior, not as a generic target-state architecture.

## 1. What The Project Is

Soyog AI is an AI-native research workspace for scientific literature workflows. The product is built around a workspace model rather than a single chat box.

At a product level, the platform currently supports:

1. Scholarly paper discovery across many external data sources.
2. Saving papers into user-owned workspaces.
3. Workspace-aware chat and research assistance.
4. PDF upload, extraction, and AI summarization.
5. Long-form AI tools such as pipeline generation, mindmaps, and report-style outputs.
6. User analytics, developer/admin visibility, and compliance-related data export flows.

The central idea is that a user searches, imports, uploads, reads, chats, and synthesizes inside one persistent research environment.

## 2. High-Level System Architecture

At a high level, the system is a split frontend-backend application:

1. Frontend
   - React + Vite + TypeScript single-page app
   - hosted on Vercel
   - handles routing, UI state, auth bootstrap, and calls the backend API

2. Backend
   - FastAPI application
   - hosted on Google Cloud Run
   - owns auth/session issuance, Firestore persistence, storage-backed file handling, AI calls, and external scholarly API aggregation

3. Data and infra services
   - Firestore for primary request-path persistence
   - Firebase Storage for uploaded files and workspace documents
   - Firebase Authentication integration for managed sign-in flows
   - Groq for current LLM inference
   - Sentry and structured logging for observability

## 3. Architectural Shape In One Diagram

```text
Browser
  |
  |  React SPA (Vite)
  |  - routing
  |  - auth bootstrap
  |  - workspace UI
  |  - AI tools UI
  v
Vercel Frontend
  |
  | HTTPS API calls
  | Authorization header + cookies + optional Firebase App Check
  v
Cloud Run FastAPI
  |
  |-- Auth router
  |-- Papers router
  |-- Workspaces router
  |-- Upload router
  |-- Research agent router
  |-- AI router
  |-- Analytics / insights / developer / compliance / health
  |
  |-- Repository layer
  |     -> Firestore collections
  |
  |-- File storage helpers
  |     -> Firebase Storage
  |
  |-- AI service layer
  |     -> Groq chat completions
  |
  |-- External scholarly source adapters
        -> OpenAlex, Crossref, Europe PMC, NASA ADS, Springer, etc.
```

## 4. Repository Structure

The main project shape is:

```text
ResearchHub-AI/
  backend/
    main.py
    routers/
    repositories/
    services/
    utils/
    tests/
  frontend/
    src/
  docs/
  deploy/
  ops/
```

The repo is already divided in a way that reflects runtime boundaries:

1. `backend/main.py`
   - application bootstrap
   - middleware
   - router registration
   - health and metrics endpoints

2. `backend/routers/`
   - API surface grouped by domain

3. `backend/repositories/`
   - persistence abstraction
   - currently centered on Firestore

4. `backend/services/`
   - shared behavior that should not live in one router
   - especially AI orchestration and analytics

5. `backend/utils/`
   - provider clients, auth helpers, Firebase helpers, storage helpers, feature flags, caching

6. `frontend/src/pages/`
   - route-level views

7. `frontend/src/components/`
   - shared UI shells and feature components

8. `frontend/src/utils/`
   - API client, Firebase browser integration, auth session helpers, routing utilities

## 5. Frontend Architecture

## 5.1 SPA Entry And Routing

The frontend entry point is `frontend/src/main.tsx`, which mounts `App.tsx`.

`frontend/src/App.tsx` is the main shell for:

1. route definitions
2. auth bootstrap
3. route protection
4. lazy loading with retry behavior
5. global providers
6. footer and common app-level UI

The app uses `react-router-dom` and lazy-loads major pages. The route loader includes recovery behavior for stale chunk maps and long-loading routes.

Protected-route behavior is handled in `App.tsx` through small wrappers:

1. regular authenticated routes
2. analytics-admin-only routes
3. developer-only routes

This means frontend access control is role-aware, but it depends on backend claims returned by `/auth/me`.

## 5.2 Frontend Providers And Shared Shell

`App.tsx` wraps the UI with:

1. `ThemeProvider`
2. `ToastProvider`
3. `ErrorBoundary`

Shared app-shell elements include:

1. cookie consent banner
2. toast container
3. command palette for authenticated users

The main authenticated layout is driven through `frontend/src/components/Layout.tsx`, which delegates to mobile-aware layout components and passes:

1. user email
2. initials
3. analytics access flag
4. developer access flag

This keeps the navigation system role-aware and centralized.

## 5.3 Frontend API Client

`frontend/src/api.ts` is the main HTTP client layer.

It does several important things:

1. resolves the backend base URL from `VITE_API_URL` or `VITE_API_BASE`
2. sends credentials with requests
3. injects the backend JWT token into the `Authorization` header
4. attempts to attach Firebase App Check tokens
5. applies a global 30-second timeout
6. auto-refreshes the backend session on eligible `401` responses

This is an important architectural choice: the app uses both cookie-based refresh semantics and header-based access token semantics together.

That gives the system:

1. explicit API authorization headers for normal requests
2. HTTP-only cookies for refresh token rotation and backend session durability

## 5.4 Browser-Side Firebase Integration

The browser-side Firebase integration lives mainly in:

1. `frontend/src/utils/firebaseClient.ts`
2. `frontend/src/utils/firebaseAuth.ts`

These files are responsible for:

1. Firebase app bootstrapping
2. Firebase Auth client access
3. Google provider setup
4. App Check setup
5. Analytics and Performance bootstrapping
6. Remote Config bootstrapping
7. Web Messaging token handling

The browser does not trust Firebase Auth alone as the application session. Instead, it uses Firebase sign-in to obtain a Firebase ID token, then exchanges that token with the backend at `/auth/firebase/session`.

That backend exchange is the actual point where the application’s backend session is created.

## 5.5 Route-Level Product Pages

The main route-level pages map closely to product surfaces:

1. `Home`
2. `Dashboard`
3. `SearchPapers`
4. `Workspace`
5. `AITools`
6. `ResearchAgent`
7. `UploadPDF`
8. `DocSpace`
9. `WritingChat`
10. `Settings`
11. `AnalyticsDashboard`
12. `DeveloperConsole`

This route organization mirrors the backend router organization and is one of the cleaner architectural choices in the codebase.

## 6. Backend Architecture

## 6.1 Backend Entry Point

The backend entry point is `backend/main.py`.

It performs a large amount of bootstrap logic up front:

1. loads environment variables from `backend/.env`
2. bootstraps secret-manager-backed environment injection
3. enforces secure `SECRET_KEY` behavior outside development
4. initializes logging
5. optionally initializes Sentry
6. configures CORS
7. configures gzip compression
8. sets rate-limit and metrics state
9. registers middleware
10. includes all route modules

This file is acting as the operational control plane of the backend.

## 6.2 Middleware And Request Handling

`backend/main.py` contains an HTTP middleware that centralizes several concerns:

1. request timing
2. request ID generation
3. Firebase App Check enforcement
4. rate limiting
5. structured request logging
6. security response headers
7. in-process metrics collection

This is an important architectural strength because it means routers do not need to implement these concerns themselves.

### Request Protection Layers

A request can be blocked before it reaches the business router if:

1. App Check is enforced and the token is missing or invalid
2. rate limits are exceeded

After the request runs, the middleware adds:

1. `X-Process-Time-Ms`
2. `X-Request-ID`
3. security headers
4. logging payloads for Cloud Logging / observability

## 6.3 Global Exception Handling

`main.py` also standardizes error responses for:

1. unhandled exceptions
2. validation errors
3. `HTTPException`

This is why routers can raise `HTTPException` while still producing a consistent response shape.

## 6.4 Router Registration

The backend includes the following routers:

1. `auth`
2. `workspaces`
3. `papers`
4. `chat`
5. `ai`
6. `upload`
7. `research_agent`
8. `developer`
9. `compliance`
10. `analytics`
11. `insights`
12. `health`

These represent the platform’s domain boundaries.

## 7. Backend Domain Modules

## 7.1 Auth Router

`backend/routers/auth.py` is one of the most important modules in the system.

It handles:

1. local registration and password login
2. email verification and resend verification
3. password reset and change-password flows
4. Google OAuth login
5. Firebase ID-token exchange
6. session refresh and logout
7. profile retrieval and profile update
8. role/access flags for developer and analytics visibility

### Auth Model

The backend uses signed JWT access tokens plus refresh token rotation.

The access token includes:

1. `sub` for user email
2. `uid` for user ID

Refresh tokens are:

1. generated by the backend
2. hashed before persistence
3. stored in Firestore under `refresh_sessions` when Firebase admin is available
4. rotated on refresh
5. revoked on logout

### Dual-Mode Sign-In

The system supports multiple identity paths:

1. password sign-in
2. Google OAuth sign-in
3. Firebase Auth sign-in

All three end up converging into the same backend session model.

That is a key architectural decision: external identity providers do not replace the backend session layer. They feed into it.

### User Identity Normalization

The auth layer also contains duplicate-account merge logic based on normalized email. That is important because the same human can arrive through:

1. password auth
2. Firebase email/password auth
3. Google OAuth

The system attempts to merge those paths into one user record when possible.

## 7.2 Papers Router

`backend/routers/papers.py` is the scholarly aggregation layer.

This is one of the largest modules in the system and acts like a unified adapter over many scholarly sources.

It includes source-specific endpoints such as:

1. OpenAlex
2. Crossref
3. Europe PMC
4. PubMed
5. PMC
6. DOAJ
7. ERIC
8. OSTI
9. EconBiz
10. J-STAGE
11. ORKG
12. HAL
13. bioRxiv
14. medRxiv
15. PLOS
16. eLife
17. DataCite
18. DBLP
19. Zenodo
20. OpenAIRE
21. Figshare
22. OSF
23. Dryad
24. INSPIRE
25. Springer
26. NASA
27. Semantic and merged/global search endpoints

In practice, this router is responsible for:

1. federated paper discovery
2. health checks against upstream data sources
3. import flows into workspaces
4. access resolution
5. search history and search metrics

This module is effectively the ingestion and discovery boundary of the platform.

## 7.3 Workspaces Router

`backend/routers/workspaces.py` owns persistent user research context.

Responsibilities include:

1. listing and creating workspaces
2. session state tracking
3. docspace document read/write
4. file listing and file download
5. workspace export
6. research-report preview and generation

This router is what turns the platform from a search tool into a workspace product.

It keeps long-lived user context, not just transient request responses.

## 7.4 Upload Router

`backend/routers/upload.py` handles PDF uploads.

Current behavior:

1. validates that the file is a PDF
2. checks MIME type and file size
3. verifies PDF magic bytes
4. extracts text using `pdfplumber`
5. optionally generates an AI summary
6. optionally saves the uploaded paper into a workspace
7. optionally uploads the original PDF into Firebase Storage
8. creates a `workspace_file` record for the uploaded asset

This flow bridges unstructured user-provided content into the structured workspace model.

## 7.5 Chat Router

`backend/routers/chat.py` is the workspace chat boundary.

It supports user-driven AI conversation anchored to workspace context. This is separate from the research-agent router because it represents ongoing interactive conversation, not large orchestrated analysis flows.

## 7.6 AI Router

`backend/routers/ai.py` is the model-routing and direct-analysis boundary.

It currently exposes:

1. AI service status
2. available models
3. active model selection
4. direct analyze endpoint

This router matters because it makes the model layer configurable at runtime. That is the current extension point for future multi-provider support.

## 7.7 Research Agent Router

`backend/routers/research_agent.py` is the most advanced orchestration layer.

It contains higher-level research workflows such as:

1. autonomous research
2. full pipeline
3. gap detection
4. knowledge graph
5. multi-agent analysis
6. trend prediction
7. experiment design
8. paper draft generation
9. writing chat
10. writing suggestions
11. smart read
12. fault detection
13. compare papers
14. personalized feed
15. citation verification

Architecturally, this router is where feature logic becomes workflow logic.

It is not just calling an LLM once. It is building product-level AI behaviors from:

1. prompts
2. paper context
3. reusable AI service calls
4. workspace state
5. result post-processing

## 7.8 Developer, Analytics, Insights, Compliance, Health

These routers are the operational and administrative side of the platform.

### Developer router

Provides:

1. access checks
2. system overview
3. user listing
4. user detail inspection

### Analytics router

Provides user/global analytics surfaces and cache invalidation hooks.

### Insights router

Provides summaries around:

1. performance
2. slow queries
3. cache behavior
4. errors
5. heavy users
6. recommendations

### Compliance router

Supports:

1. privacy summary
2. data rights requests
3. user-specific request retrieval
4. data export flows

### Health router

Provides health endpoints in addition to the root-level health endpoints from `main.py`.

## 8. Persistence And Data Architecture

## 8.1 Storage Model

The request-path database is Firestore-first.

This is important because the codebase still contains compatibility language around legacy SQL paths, but the active runtime persistence is Firestore-centric.

The central repository implementation is `FirebaseResearchRepository` in `backend/repositories/research.py`.

## 8.2 Repository Layer

`FirebaseResearchRepository` is the data-access layer between routers and Firestore.

Its job is to:

1. expose business-oriented methods
2. hide Firestore query details from routers
3. convert Firestore documents into dataclass objects
4. own ID generation and save behavior

This is a strong architectural boundary. Routers mostly interact with repository methods such as:

1. `get_user_by_email`
2. `create_user`
3. `list_workspaces_for_user`
4. `create_workspace`
5. `create_paper`
6. `list_papers_for_workspace`
7. `create_chat`
8. `create_workspace_file`
9. `get_docspace_document`
10. `save`

## 8.3 Domain Data Models

The repository defines dataclasses for the major platform objects:

1. `User`
2. `Workspace`
3. `Paper`
4. `Chat`
5. `SearchHistory`
6. `UserSessionState`
7. `WorkspaceDocument`
8. `WorkspaceFile`
9. `DataRightsRequest`

These dataclasses are the internal domain model of the backend.

## 8.4 Firestore Collections

The current documented schema includes collections such as:

1. `users`
2. `workspaces`
3. `papers`
4. `chats`
5. `search_history`
6. `user_session_state`
7. `workspace_documents`
8. `workspace_files`
9. `data_rights_requests`
10. `_counters`

Operationally, the repository initializes these collection handles in its constructor and uses `_counters` to generate monotonic integer IDs.

### Important Design Choice

The system uses integer IDs stored inside Firestore documents instead of relying only on Firestore document auto IDs.

That makes the data model feel more relational and easier to expose to the frontend, but it also introduces a bottleneck risk around counter increments if write volume grows heavily.

## 8.5 Session State

The platform stores session-state-like data in Firestore through `user_session_state`.

This is used for resume behavior, such as:

1. last page path
2. active workspace
3. last query
4. draft text

That is one of the features that helps the app feel like a workspace, not just a stateless tool.

## 8.6 File Storage

Uploaded files and workspace assets are stored in Firebase Storage, while metadata about those files is stored in Firestore.

This split is standard and correct:

1. binary files go to object storage
2. searchable metadata goes to the database

The file-handling helpers live mainly in:

1. `backend/utils/firebase_storage.py`
2. `backend/utils/firebase_admin_client.py`

## 9. AI Architecture

## 9.1 Current AI Provider Model

The current AI provider is Groq.

Provider setup and model configuration live in `backend/utils/groq_client.py`.

That module is responsible for:

1. Groq client initialization
2. environment-driven model configuration
3. longform versus base-model settings
4. task-specific model slots
5. allowed-model list enforcement
6. decommissioned-model fallback behavior
7. runtime model status reporting
8. runtime model switching

### Task-Based Routing

The code already supports task-specific model routing for:

1. chat
2. upload summary
3. mindmap / report
4. pipeline / agent

This is one of the most important architectural decisions in the repo because it prevents the app from being tied to one single prompt-model pairing.

## 9.2 Central AI Service Layer

`backend/services/ai_service.py` centralizes AI call orchestration.

This service handles:

1. query normalization
2. two-tier cache strategy
3. timeout control
4. Groq invocation
5. fallback handling for decommissioned models
6. analytics logging

The cache architecture is:

1. L1 in-memory cache
2. L2 Firestore-backed cache

This is important because AI responses are expensive compared to normal API requests. The caching layer is a cost and latency optimization boundary.

## 9.3 AI Analytics

AI usage analytics are tracked through service-layer logging rather than relying only on frontend analytics.

That is the correct design for:

1. cost analysis
2. latency tracking
3. cache hit analysis
4. route-level AI usage visibility

## 9.4 AI Feature Assembly

There is not one monolithic AI system in the repo. Instead, the product assembles AI behavior in layers:

1. provider client and model config
2. central run/query function
3. router-specific prompts and orchestration
4. frontend feature-specific rendering

That layered design is what will let the app adopt a self-hosted provider later without rewriting every feature page.

## 10. Security Model

## 10.1 Backend Security Controls

Security controls currently visible in the architecture include:

1. strict `SECRET_KEY` enforcement outside development
2. CORS allowlist plus Vercel preview regex support
3. HTTP security headers
4. App Check enforcement support
5. request-level rate limiting
6. refresh token rotation and revocation
7. HTTP-only auth cookies
8. standardized exception handling
9. role-aware route protection for analytics and developer areas

## 10.2 Frontend Security Behavior

The frontend uses:

1. local access token storage for request headers
2. backend refresh cookies for session continuity
3. optional App Check token attachment
4. auth/session event handling across tabs and route transitions

## 10.3 Access Control Model

The system exposes two important higher-level access flags through `/auth/me`:

1. `is_developer`
2. `can_access_analytics`

This means feature access is role-aware without requiring the entire frontend to know backend internals.

## 11. Operational Architecture

## 11.1 Health And Readiness

The backend exposes:

1. `/health/live`
2. `/health/ready`

The readiness endpoint checks Firestore availability by initializing the repository and attempting a minimal read.

## 11.2 Metrics

The backend exposes Prometheus-style metrics from `/ops/metrics` and SLO windows from `/ops/slo`.

Internally it tracks:

1. total requests
2. rate-limited requests
3. status counts
4. path counts
5. latency buckets
6. recent request windows for SLO calculation

## 11.3 Logging

The backend writes structured JSON-like logs with:

1. request IDs
2. user IDs when known
3. path
4. method
5. duration
6. trace linkage

This is appropriate for Cloud Run and Google Cloud Logging.

## 11.4 Error Monitoring

Sentry is initialized when `SENTRY_DSN` is configured.

That gives the system runtime exception visibility beyond plain logs.

## 12. Deployment Architecture

The deployment model is intentionally split:

1. frontend on Vercel
2. backend on Cloud Run
3. Firebase services for auth, database, and storage

This provides:

1. simple static/frontend deployment
2. autoscaling API backend
3. managed persistence and identity integrations

The backend also supports local development with the Firestore emulator and a local Vite dev server.

## 13. How A Few Core Flows Work End To End

## 13.1 Login Flow

Password or Firebase login roughly works like this:

1. user signs in from frontend
2. frontend gets either credentials or a Firebase ID token
3. frontend exchanges credentials/token with backend
4. backend finds or creates the user
5. backend issues JWT access token
6. backend issues refresh token and stores its hash
7. backend sets auth cookies
8. frontend stores access token for API headers
9. frontend calls `/auth/me` to hydrate session state

## 13.2 Paper Search Flow

The search flow is roughly:

1. frontend calls one of the search endpoints or merged search endpoint
2. backend adapter hits external scholarly APIs
3. backend normalizes results into app-friendly paper objects
4. frontend renders result cards
5. user can import/save papers to workspace
6. backend persists the selected paper into Firestore

## 13.3 Upload Flow

The upload flow is roughly:

1. user uploads a PDF from `UploadPDF`
2. frontend sends multipart form data to `/papers/upload`
3. backend validates PDF and extracts text
4. backend optionally runs AI summary
5. backend optionally saves a paper record
6. backend optionally uploads the file to Firebase Storage
7. backend creates workspace file metadata in Firestore
8. frontend renders extracted text and AI summary

## 13.4 Research-Agent Flow

The research-agent flow is roughly:

1. user triggers a workflow
2. frontend packages prompt and context
3. backend route builds system prompts and context
4. backend calls AI service with task-based model selection
5. AI service handles cache, timeout, and logging
6. backend post-processes output
7. frontend renders the workflow result

## 14. Architectural Strengths

The current architecture has several real strengths:

1. clear separation between UI, API, repository, and provider integrations
2. Firestore-first persistence that matches the current hosted stack
3. route-level modular backend organization
4. role-aware access control already in place
5. AI routing already supports task-level model choices
6. middleware centralizes rate limits, App Check, and logging
7. file storage is correctly split from metadata persistence
8. the product is already organized around durable workspace context

## 15. Architectural Constraints And Current Tradeoffs

There are also real constraints:

1. `papers.py` is very large and acts as a broad adapter layer; that can become hard to evolve safely
2. `research_agent.py` is also very large and contains a lot of workflow logic in one file
3. Firestore integer counter generation can become a hotspot if write volume scales sharply
4. the codebase is Firebase-first in runtime, but some compatibility and migration traces still exist, which can confuse maintainers
5. current AI integration is provider-specific at the client layer even though the routing layer is promising
6. role and feature visibility currently depend heavily on environment configuration

These are not failures. They are the current scale-stage tradeoffs of the product.

## 16. Best Mental Model For The Project

The best way to think about Soyog AI is this:

1. It is not primarily a chatbot.
2. It is not only a paper search engine.
3. It is a workspace-centric research operating layer.

The architecture reflects that:

1. discovery comes from `papers.py`
2. persistence comes from the repository layer
3. user continuity comes from workspaces and session state
4. intelligence comes from AI routing plus research-agent orchestration
5. trust and operations come from analytics, developer, compliance, and health surfaces

## 17. What This Architecture Is Ready For Next

Based on the current design, the codebase is especially well-positioned for:

1. citations as a shared metadata and formatting layer
2. AI Checker as an upload/workspace analysis layer
3. metadata enrichment and source trust scoring
4. provider abstraction beyond Groq
5. RAG or vector-backed retrieval additions
6. stronger evidence-grounded writing workflows

The architecture already contains the right extension points for those directions. The work required is mostly controlled extension, not reinvention.
