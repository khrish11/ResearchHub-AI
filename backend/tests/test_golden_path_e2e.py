"""
Golden Path E2E Tests

Real authenticated end-to-end workflow testing for Priority 4 validation.
Tests the complete user journey from registration through research intelligence.
"""
import pytest
import httpx
import os
import asyncio
import time
from typing import Dict, Optional

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8010")
FIREBASE_AUTH_EMULATOR_HOST = os.getenv("FIREBASE_AUTH_EMULATOR_HOST", "http://localhost:9099")


class GoldenPathTestUser:
    """Represents a user for golden path E2E testing."""
    
    def __init__(self, email: str, password: str, name: str):
        self.email = email
        self.password = password
        self.name = name
        self.jwt_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.workspace_id: Optional[str] = None
        self.paper_id: Optional[str] = None
    
    async def register(self, client: httpx.AsyncClient) -> bool:
        """Register user via JWT endpoint."""
        response = await client.post(
            f"{BACKEND_URL}/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "name": self.name
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            self.jwt_token = data.get("access_token")
            self.user_id = data.get("user_id")
            return True
        return False
    
    async def login(self, client: httpx.AsyncClient) -> bool:
        """Login user via JWT endpoint."""
        response = await client.post(
            f"{BACKEND_URL}/auth/token",
            data={
                "username": self.email,
                "password": self.password
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            self.jwt_token = data.get("access_token")
            return True
        return False
    
    async def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        if not self.jwt_token:
            return {}
        return {"Authorization": f"Bearer {self.jwt_token}"}


@pytest.mark.asyncio
async def test_user_a_registration_and_login():
    """Test User A registration and login."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        timestamp = int(time.time())
        user = GoldenPathTestUser(
            email=f"golden_path_user_a_{timestamp}@soyog.test",
            password="GoldenPath123!",
            name="Golden Path User A"
        )
        
        # Register
        register_success = await user.register(client)
        assert register_success, f"Registration failed"
        assert user.jwt_token is not None, "JWT token not generated"
        
        # Verify /auth/me works
        headers = await user.get_auth_headers()
        me_response = await client.get(
            f"{BACKEND_URL}/auth/me",
            headers=headers
        )
        assert me_response.status_code == 200, f"Auth me failed: {me_response.status_code}"
        
        me_data = me_response.json()
        assert me_data.get("email") == user.email, "Email mismatch in /auth/me"
        
        # Logout
        logout_response = await client.post(
            f"{BACKEND_URL}/auth/logout",
            headers=headers
        )
        assert logout_response.status_code == 200, f"Logout failed: {logout_response.status_code}"
        
        # Note: JWT tokens are stateless, so logout doesn't invalidate them server-side
        # The application may use other mechanisms (like refresh token invalidation)
        # This is documented behavior, not a failure
        
        # Login again
        login_success = await user.login(client)
        assert login_success, f"Login failed"
        assert user.jwt_token is not None, "JWT token not generated after login"
        
        # Verify protected endpoint works after login
        headers = await user.get_auth_headers()
        me_after_login = await client.get(
            f"{BACKEND_URL}/auth/me",
            headers=headers
        )
        assert me_after_login.status_code == 200, f"Auth me should work after login: {me_after_login.status_code}"


@pytest.mark.asyncio
async def test_user_a_workspace_creation():
    """Test User A workspace creation and persistence."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        timestamp = int(time.time())
        user = GoldenPathTestUser(
            email=f"workspace_user_a_{timestamp}@soyog.test",
            password="Workspace123!",
            name="Workspace User A"
        )
        
        # Register and login
        await user.register(client)
        headers = await user.get_auth_headers()
        
        # Create workspace
        workspace_response = await client.post(
            f"{BACKEND_URL}/workspaces",
            json={
                "name": "Golden Path Test Workspace",
                "description": "Workspace created during Priority 4 golden path testing"
            },
            headers={"Content-Type": "application/json", **headers}
        )
        
        assert workspace_response.status_code == 200, f"Workspace creation failed: {workspace_response.status_code} - {workspace_response.text}"
        
        workspace_data = workspace_response.json()
        user.workspace_id = workspace_data.get("id")
        assert user.workspace_id is not None, "Workspace ID not returned"
        
        # List workspaces
        list_response = await client.get(
            f"{BACKEND_URL}/workspaces",
            headers=headers
        )
        
        assert list_response.status_code == 200, f"List workspaces failed: {list_response.status_code}"
        
        workspaces = list_response.json()
        assert isinstance(workspaces, list), f"Workspaces should be a list, got {type(workspaces)}"
        assert len(workspaces) > 0, "No workspaces returned"
        
        # Verify our workspace is in the list
        found_workspace = next((w for w in workspaces if w.get("id") == user.workspace_id), None)
        assert found_workspace is not None, "Created workspace not found in list"
        
        # Get specific workspace
        get_response = await client.get(
            f"{BACKEND_URL}/workspaces/{user.workspace_id}",
            headers=headers
        )
        
        assert get_response.status_code == 200, f"Get workspace failed: {get_response.status_code}"
        
        workspace_detail = get_response.json()
        assert workspace_detail.get("id") == user.workspace_id, "Workspace ID mismatch"
        assert workspace_detail.get("name") == "Golden Path Test Workspace", "Workspace name mismatch"


@pytest.mark.asyncio
async def test_user_b_isolation():
    """Test User B cannot access User A's resources."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        timestamp = int(time.time())
        
        # Create User A
        user_a = GoldenPathTestUser(
            email=f"isolation_user_a_{timestamp}@soyog.test",
            password="Isolation123!",
            name="Isolation User A"
        )
        await user_a.register(client)
        headers_a = await user_a.get_auth_headers()
        
        # Create User A's workspace
        workspace_response = await client.post(
            f"{BACKEND_URL}/workspaces",
            json={"name": "User A Private Workspace"},
            headers={"Content-Type": "application/json", **headers_a}
        )
        assert workspace_response.status_code == 200, f"User A workspace creation failed: {workspace_response.status_code}"
        user_a.workspace_id = workspace_response.json().get("id")
        
        # Create User B
        user_b = GoldenPathTestUser(
            email=f"isolation_user_b_{timestamp}@soyog.test",
            password="Isolation123!",
            name="Isolation User B"
        )
        await user_b.register(client)
        headers_b = await user_b.get_auth_headers()
        
        # User B tries to access User A's workspace
        access_response = await client.get(
            f"{BACKEND_URL}/workspaces/{user_a.workspace_id}",
            headers=headers_b
        )
        
        # Should be denied (404 or 403 depending on implementation)
        assert access_response.status_code in [403, 404], f"User B should not access User A's workspace, got {access_response.status_code}"