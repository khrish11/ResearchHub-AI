"""
Firebase Auth Emulator Test Fixtures

Provides reusable test authentication fixtures for end-to-end testing
with Firebase Authentication Emulator.
"""
import os
import pytest
import httpx
from typing import Dict, Optional
import json

# Firebase Auth emulator configuration
FIREBASE_AUTH_EMULATOR_HOST = os.getenv("FIREBASE_AUTH_EMULATOR_HOST", "http://localhost:9099")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "demo-test")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8010")


class FirebaseTestUser:
    """Represents a test user with Firebase authentication."""
    
    def __init__(self, email: str, password: str, name: str, user_id: str):
        self.email = email
        self.password = password
        self.name = name
        self.user_id = user_id
        self.firebase_uid: Optional[str] = None
        self.id_token: Optional[str] = None
        self.backend_token: Optional[str] = None
    
    async def create_firebase_user(self) -> bool:
        """Create user in Firebase Auth emulator."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Firebase Auth emulator signup endpoint
                url = f"{FIREBASE_AUTH_EMULATOR_HOST}/identitytoolkit.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/accounts:signUp"
                response = await client.post(
                    url,
                    json={
                        "email": self.email,
                        "password": self.password,
                        "returnSecureToken": True
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    self.firebase_uid = data.get("localId")
                    self.id_token = data.get("idToken")
                    return True
                return False
        except Exception as e:
            print(f"Failed to create Firebase user: {e}")
            return False
    
    async def sign_in_firebase(self) -> bool:
        """Sign in to Firebase Auth emulator."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{FIREBASE_AUTH_EMULATOR_HOST}/identitytoolkit.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/accounts:signInWithPassword"
                response = await client.post(
                    url,
                    json={
                        "email": self.email,
                        "password": self.password,
                        "returnSecureToken": True
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    self.firebase_uid = data.get("localId")
                    self.id_token = data.get("idToken")
                    return True
                return False
        except Exception as e:
            print(f"Failed to sign in Firebase user: {e}")
            return False
    
    async def exchange_firebase_session(self) -> bool:
        """Exchange Firebase ID token for backend session token."""
        if not self.id_token:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/auth/firebase/session",
                    json={"id_token": self.id_token},
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code == 200:
                    data = response.json()
                    self.backend_token = data.get("access_token")
                    return True
                print(f"Firebase session exchange failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Failed to exchange Firebase session: {e}")
            return False
    
    async def authenticate(self) -> bool:
        """Complete authentication flow: create user, sign in, exchange session."""
        # Try to create user first
        if not await self.create_firebase_user():
            # If creation fails, try sign in (user might already exist)
            if not await self.sign_in_firebase():
                return False
        
        # Exchange Firebase ID token for backend token
        return await self.exchange_firebase_session()
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        if not self.backend_token:
            return {}
        return {"Authorization": f"Bearer {self.backend_token}"}
    
    async def cleanup(self):
        """Clean up test user from Firebase Auth emulator."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{FIREBASE_AUTH_EMULATOR_HOST}/identitytoolkit.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/accounts:delete"
                if self.id_token:
                    await client.post(
                        url,
                        json={"idToken": self.id_token}
                    )
        except Exception as e:
            print(f"Failed to cleanup Firebase user: {e}")


@pytest.fixture
async def test_user_a():
    """Create and authenticate User A for testing."""
    user = FirebaseTestUser(
        email="testuserA@soyog.test",
        password="TestPassword123!",
        name="Test User A",
        user_id="test_user_a"
    )
    
    # Authenticate the user
    success = await user.authenticate()
    if not success:
        pytest.fail("Failed to authenticate test user A")
    
    yield user
    
    # Cleanup
    await user.cleanup()


@pytest.fixture
async def test_user_b():
    """Create and authenticate User B for testing."""
    user = FirebaseTestUser(
        email="testuserB@soyog.test",
        password="TestPassword123!",
        name="Test User B",
        user_id="test_user_b"
    )
    
    # Authenticate the user
    success = await user.authenticate()
    if not success:
        pytest.fail("Failed to authenticate test user B")
    
    yield user
    
    # Cleanup
    await user.cleanup()


@pytest.fixture
def authenticated_client(test_user_a):
    """Provide an HTTP client with authentication headers."""
    import httpx
    
    class AuthenticatedClient:
        def __init__(self, user: FirebaseTestUser):
            self.user = user
            self.base_url = BACKEND_URL
        
        async def get(self, path: str, **kwargs):
            headers = kwargs.pop('headers', {})
            headers.update(self.user.get_auth_headers())
            async with httpx.AsyncClient(timeout=30.0) as client:
                return await client.get(f"{self.base_url}{path}", headers=headers, **kwargs)
        
        async def post(self, path: str, **kwargs):
            headers = kwargs.pop('headers', {})
            headers.update(self.user.get_auth_headers())
            headers["Content-Type"] = "application/json"
            async with httpx.AsyncClient(timeout=30.0) as client:
                return await client.post(f"{self.base_url}{path}", headers=headers, **kwargs)
        
        async def put(self, path: str, **kwargs):
            headers = kwargs.pop('headers', {})
            headers.update(self.user.get_auth_headers())
            headers["Content-Type"] = "application/json"
            async with httpx.AsyncClient(timeout=30.0) as client:
                return await client.put(f"{self.base_url}{path}", headers=headers, **kwargs)
        
        async def delete(self, path: str, **kwargs):
            headers = kwargs.pop('headers', {})
            headers.update(self.user.get_auth_headers())
            async with httpx.AsyncClient(timeout=30.0) as client:
                return await client.delete(f"{self.base_url}{path}", headers=headers, **kwargs)
    
    return AuthenticatedClient(test_user_a)