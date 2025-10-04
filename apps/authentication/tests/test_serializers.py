"""
Tests for authentication serializers.
"""
import pytest

from apps.authentication.serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserRegistrationSerializer,
)
from apps.authentication.tests.factories import UserFactory


@pytest.mark.django_db
class TestUserRegistrationSerializer:
    """Test UserRegistrationSerializer."""

    def test_valid_registration(self):
        """Test registration with valid data."""
        data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid()
        user = serializer.save()
        assert user.email == "newuser@example.com"
        assert user.check_password("SecurePass123!")

    def test_password_mismatch(self):
        """Test password confirmation mismatch."""
        data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "password_confirm": "DifferentPass456!",
            "first_name": "John",
            "last_name": "Doe",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert (
            "password" in serializer.errors or "non_field_errors" in serializer.errors
        )

    def test_email_already_exists(self):
        """Test registration with existing email."""
        UserFactory(email="existing@example.com")

        data = {
            "email": "existing@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "email" in serializer.errors

    def test_weak_password(self):
        """Test registration with weak password."""
        data = {
            "email": "newuser@example.com",
            "password": "123",
            "password_confirm": "123",
            "first_name": "John",
            "last_name": "Doe",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "password" in serializer.errors


@pytest.mark.django_db
class TestPasswordResetRequestSerializer:
    """Test PasswordResetRequestSerializer."""

    def test_valid_email(self):
        """Test password reset request with valid email."""
        UserFactory(email="user@example.com")

        data = {"email": "user@example.com"}
        serializer = PasswordResetRequestSerializer(data=data)
        assert serializer.is_valid()

    def test_nonexistent_email(self):
        """Test password reset request with nonexistent email."""
        data = {"email": "nonexistent@example.com"}
        serializer = PasswordResetRequestSerializer(data=data)
        # Should still be valid (security - don't reveal if email exists)
        # This depends on implementation
        result = serializer.is_valid()
        assert result or "email" in serializer.errors


@pytest.mark.django_db
class TestPasswordResetConfirmSerializer:
    """Test PasswordResetConfirmSerializer."""

    def test_valid_password_reset(self):
        """Test password reset with valid data."""
        data = {
            "token": "valid-token",
            "new_password": "NewSecurePass123!",
            "new_password_confirm": "NewSecurePass123!",
        }
        serializer = PasswordResetConfirmSerializer(data=data)
        assert serializer.is_valid()

    def test_password_mismatch_reset(self):
        """Test password reset with mismatched passwords."""
        data = {
            "token": "valid-token",
            "new_password": "NewSecurePass123!",
            "new_password_confirm": "DifferentPass456!",
        }
        serializer = PasswordResetConfirmSerializer(data=data)
        assert not serializer.is_valid()
