# Soyog AI Frontend

Frontend stack: React + TypeScript + Vite.

## Prerequisites

1. Node.js 20+
2. npm 10+
3. Backend API running (default `http://localhost:8010`)

## Environment

Create `frontend/.env` (or copy from repository `.env.example`) with at least:

```env
VITE_API_URL=http://localhost:8010
VITE_API_TIMEOUT_MS=120000
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_STORAGE_BUCKET=...
VITE_FIREBASE_APP_ID=...
```

Notes:

1. `VITE_API_URL` is preferred for local development.
2. `VITE_API_BASE` is also supported for deployment platforms.

## Local Development

Install and run:

```bash
npm ci
npm run dev
```

Default local URL:

1. `http://localhost:5173`

## Quality Gates

Commands used by CI:

```bash
npm run lint
npm run build
npm run test:e2e
npm run a11y:ci
```

## E2E Testing

Playwright configuration lives in `playwright.config.ts`.

Run smoke tests:

```bash
npm run test:e2e
```

Run headed locally:

```bash
npm run test:e2e:headed
```

## Troubleshooting

1. If login appears stuck, verify backend `/auth/me` works and cookies are enabled.
2. If CORS fails, verify backend `FRONTEND_URL` and `EXTRA_FRONTEND_URLS` values.
3. If Firebase auth fails, verify all `VITE_FIREBASE_*` values and authorized domains.
