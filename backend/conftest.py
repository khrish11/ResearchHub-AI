"""
Root conftest.py — sets the FIRESTORE_EMULATOR_HOST env var BEFORE
any application module is imported.  The Firebase Admin SDK picks this
up automatically and routes all Firestore calls to the local emulator.

Usage:
    # Start emulator first (separate terminal):
    firebase emulators:start --only firestore --project demo-test

    # Run tests:
    pytest
"""

import os

# ── Must be set BEFORE firebase_admin / google.cloud.firestore imports ──
os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "localhost:8080")
os.environ.setdefault("FIREBASE_PROJECT_ID", "demo-test")          # demo-* = local only
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("USE_BCRYPT", "0")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("BACKEND_URL", "http://localhost:8010")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("SECURITY_HEADERS_ENABLED", "0")
