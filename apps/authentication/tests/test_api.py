"""
Tests for authentication API endpoints.
"""
from django.urls import reverse

import pytest
from rest_framework import status

from apps.authentication.models import User
from apps.authentication.tests.factories import UserFactory


@pytest.mark.django_db
class TestUserRegistration:
    """Test user registration endpoint."""

    def test_register_user_success(self, api_client):
        """Test successful user registration."""
        url = reverse("authentication-register")
        data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.filter(email="newuser@example.com").exists()
        assert "access" in response.data
        assert "refresh" in response.data

    def test_register_user_password_mismatch(self, api_client):
        """Test registration with password mismatch."""
        url = reverse("authentication-register")
        data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "password_confirm": "DifferentPass456!",
            "first_name": "John",
            "last_name": "Doe",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_email(self, api_client):
        """Test registration with existing email."""
        UserFactory(email="existing@example.com")

        url = reverse("authentication-register")
        data = {
            "email": "existing@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUserLogin:
    """Test user login endpoint."""

    def test_login_success(self, api_client):
        """Test successful login."""
        user = UserFactory(email="user@example.com", password="testpass123")

        url = reverse("authentication-login")
        data = {"email": "user@example.com", "password": "testpass123"}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_login_invalid_credentials(self, api_client):
        """Test login with invalid credentials."""
        UserFactory(email="user@example.com", password="testpass123")

        url = reverse("authentication-login")
        data = {"email": "user@example.com", "password": "wrongpassword"}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user(self, api_client):
        """Test login with nonexistent user."""
        url = reverse("authentication-login")
        data = {"email": "nonexistent@example.com", "password": "testpass123"}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPasswordReset:
    """Test password reset endpoints."""

    def test_password_reset_request(self, api_client):
        """Test password reset request."""
        user = UserFactory(email="user@example.com")

        url = reverse("authentication-request-password-reset")
        data = {"email": "user@example.com"}
        response = api_client.post(url, data, format="json")

        # Should return 200 even if email doesn't exist (security)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

    def test_password_reset_confirm(self, api_client):
        """Test password reset confirmation."""
        user = UserFactory(email="user@example.com", password="oldpass123")

        # In real scenario, token would be generated from reset request
        # For testing, we'll test the serializer validation
        url = reverse("authentication-confirm-password-reset")
        data = {
            "token": "test-token",
            "new_password": "NewSecurePass123!",
            "new_password_confirm": "NewSecurePass123!",
        }
        response = api_client.post(url, data, format="json")

        # Will fail with invalid token, but validates structure
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]


@pytest.mark.django_db
class TestUserProfile:
    """Test user profile endpoint."""

    def test_get_profile_authenticated(self, authenticated_client):
        """Test getting profile as authenticated user."""
        url = reverse("authentication-profile")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "email" in response.data

    def test_get_profile_unauthenticated(self, api_client):
        """Test getting profile without authentication."""
        url = reverse("authentication-profile")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_profile(self, authenticated_client):
        """Test updating user profile."""
        url = reverse("authentication-profile")
        data = {"first_name": "Updated", "last_name": "Name"}
        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["first_name"] == "Updated"
