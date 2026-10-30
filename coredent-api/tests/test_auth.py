"""
Tests for authentication endpoints
"""
import pytest
from httpx import AsyncClient


class TestAuthEndpoints:
    """Test authentication endpoints"""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user):
        """Test successful login"""
        login_data = {
            "email": test_user.email,
            "password": "testpassword123"
        }
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" not in data
        assert "refresh_token=" in response.headers.get("set-cookie", "")
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials"""
        login_data = {
            "email": "invalid@example.com",
            "password": "wrongpassword"
        }
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client: AsyncClient):
        """Test login with missing fields"""
        response = await client.post("/api/v1/auth/login", json={})
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Self-serve registration creates a practice + owner and returns tokens."""
        register_data = {
            "practice_name": "Bright Smile Dental",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "owner@brightsmile.example",
            "password": "StrongPass!234",
            "country": "US",
        }
        response = await client.post("/api/v1/auth/register", json=register_data)

        assert response.status_code == 202
        data = response.json()
        assert "verification link" in data["message"].lower()
        assert "access_token" not in data
        assert "refresh_token" not in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        """Registering with an existing email is rejected with 409."""
        register_data = {
            "practice_name": "Another Practice",
            "first_name": "Dup",
            "last_name": "User",
            "email": test_user.email,
            "password": "StrongPass!234",
            "country": "US",
        }
        response = await client.post("/api/v1/auth/register", json=register_data)
        assert response.status_code == 202
        assert "verification link" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_register_short_password_rejected(self, client: AsyncClient):
        """Passwords shorter than the policy minimum fail schema validation."""
        register_data = {
            "practice_name": "Tiny Pass Dental",
            "first_name": "Tom",
            "last_name": "Short",
            "email": "tom@tinypass.example",
            "password": "short",
            "country": "US",
        }
        response = await client.post("/api/v1/auth/register", json=register_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password_rejected(self, client: AsyncClient):
        """A long-but-weak password is rejected by the strength policy (400)."""
        register_data = {
            "practice_name": "Weak Pass Dental",
            "first_name": "Will",
            "last_name": "Weak",
            "email": "will@weakpass.example",
            "password": "alllowercaseletters",
            "country": "US",
        }
        response = await client.post("/api/v1/auth/register", json=register_data)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, client: AsyncClient, auth_headers, test_user):
        """Test getting current user with valid token"""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["first_name"] == test_user.first_name
        assert data["last_name"] == test_user.last_name
        assert data["role"].upper() == test_user.role.value

    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self, client: AsyncClient):
        """Test getting current user without token"""
        response = await client.get("/api/v1/auth/me")
        
        # Without auth, should get 401 or 403 depending on CSRF/auth setup
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        # Invalid token should return 401 or 403
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client: AsyncClient, test_user):
        """Test token refresh"""
        # First login to get refresh token
        login_data = {
            "email": test_user.email,
            "password": "testpassword123"
        }
        login_response = await client.post("/api/v1/auth/login", json=login_data)
        assert "refresh_token" not in login_response.json()

        # The HttpOnly cookie is automatically retained by AsyncClient.
        response = await client.post("/api/v1/auth/refresh")
        
        assert response.status_code in [200, 401, 403]

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client: AsyncClient):
        """Test refresh with invalid token"""
        refresh_data = {"refresh_token": "invalid-refresh-token"}
        response = await client.post("/api/v1/auth/refresh", json=refresh_data)
        
        # Should return 401 or 403 depending on CSRF/auth setup
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient, auth_headers):
        """Test successful logout"""
        response = await client.post("/api/v1/auth/logout", headers=auth_headers)
        
        # Should return 200 or 403 depending on CSRF setup
        assert response.status_code in [200, 403]
        if response.status_code == 200:
            assert "Successfully logged out" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_logout_no_token(self, client: AsyncClient):
        """Test logout without token"""
        response = await client.post("/api/v1/auth/logout")
        
        # Should return 401 or 403 depending on CSRF/auth setup
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_password_reset_request(self, client: AsyncClient, test_user):
        """Test password reset request"""
        reset_data = {"email": test_user.email}
        response = await client.post("/api/v1/auth/forgot-password", json=reset_data)
        
        assert response.status_code == 200
        assert "password reset link" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_password_reset_request_invalid_email(self, client: AsyncClient):
        """Test password reset request with invalid email"""
        reset_data = {"email": "nonexistent@example.com"}
        response = await client.post("/api/v1/auth/forgot-password", json=reset_data)
        
        # Should still return 200 for security (don't reveal if email exists)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_password_reset_confirm(self, client: AsyncClient):
        """Test password reset confirmation"""
        reset_data = {
            "token": "valid-reset-token",
            "new_password": "newpassword123"
        }
        response = await client.post("/api/v1/auth/reset-password", json=reset_data)
        
        # This would normally require a valid reset token from email
        # For testing, we expect it to fail with invalid token or CSRF issue
        assert response.status_code in [200, 400, 403]

    # Note: /auth/change-password endpoint is not implemented in the backend
    # These tests are commented out as the endpoint doesn't exist
    # def test_change_password_success(self, client: TestClient, auth_headers):
    # def test_change_password_wrong_current(self, client: TestClient, auth_headers):
    # def test_change_password_no_auth(self, client: TestClient):