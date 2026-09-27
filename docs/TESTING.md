# Testing

Soyog AI has comprehensive testing infrastructure across frontend and backend.

## Backend Testing

### Unit Tests
Backend unit tests are located in `backend/tests/`.

Run tests with the Firestore emulator:

```powershell
$env:FIRESTORE_EMULATOR_HOST='localhost:8081'
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

### Test Coverage
The backend includes tests for:
- Authentication and authorization
- Research intelligence services
- RAG system
- Paper analysis
- Repository operations
- API endpoints

## Frontend Testing

### E2E Tests
Frontend E2E tests use Playwright and are located in `frontend/e2e/`.

Run E2E tests:

```powershell
cd frontend
npm run test:e2e
```

### Type Checking
TypeScript type checking is included in the build process:

```powershell
cd frontend
npm run build
```

### Linting
ESLint is configured for the frontend:

```powershell
cd frontend
npm run lint
```

## Firebase Emulator Testing

The project uses Firebase emulators for local testing:

```powershell
gcloud beta emulators firestore start --project=studio-5606596663-2ca06 --host-port=localhost:8081
```

Emulator configuration is in `firebase.json`.

## Security Testing

Security testing resources are available in `docs/security/`:
- Penetration testing playbook
- OWASP scan operations

## CI/CD Testing

The project includes GitHub Actions workflows for automated testing during CI/CD processes.
