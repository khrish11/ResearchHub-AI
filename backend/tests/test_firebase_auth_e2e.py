"""
Firebase Auth Emulator Integration Tests

Tests the Firebase Auth emulator configuration and Firebase Admin integration.

NOTE: Firebase Auth has been disabled in the frontend in favor of direct JWT authentication.
The frontend uses VITE_FIREBASE_AUTH_ENABLED=0 and direct application JWT authentication
via /auth/register and /auth/token endpoints. Firebase Auth emulator support is kept for
potential future use but is not currently active in the application architecture.
"""
import pytest
import httpx
import os

FIREBASE_AUTH_EMULATOR_HOST = os.getenv("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
if not FIREBASE_AUTH_EMULATOR_HOST.startswith("http://"):
    FIREBASE_AUTH_EMULATOR_HOST = f"http://{FIREBASE_AUTH_EMULATOR_HOST}"

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "studio-5606596663-2ca06")


@pytest.mark.skip(reason="Firebase Auth disabled in frontend - using direct JWT authentication")
@pytest.mark.asyncio
async def test_firebase_auth_emulator_available():
    """Test that Firebase Auth emulator is accessible."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{FIREBASE_AUTH_EMULATOR_HOST}")
        # Auth emulator should respond with status
        assert response.status_code == 200, f"Firebase Auth emulator not accessible: {response.status_code}"


def test_firebase_admin_token_verification():
    """Test that Firebase Admin token verification works with emulator."""
    # This tests the backend's Firebase Admin integration
    from utils.firebase_admin_client import verify_firebase_id_token, firebase_admin_is_configured
    
    # Verify Firebase Admin is configured for emulator
    assert firebase_admin_is_configured(), "Firebase Admin not configured for emulator"
    
    # Test token verification with emulator
    # In emulator mode, this should accept any token and return a mock structure
    mock_token = "test.emulator.token"
    try:
        result = verify_firebase_id_token(mock_token)
        # In emulator mode, this should return a dict with basic fields
        assert isinstance(result, dict), "Token verification should return dict"
        assert "uid" in result or "email" in result, "Result should contain user identifier"
    except Exception as e:
        pytest.fail(f"Firebase token verification failed: {e}")