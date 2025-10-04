"""
Tests for authentication models.
"""
from django.db import IntegrityError

import pytest

from apps.authentication.models import User, UserProfile
from apps.authentication.tests.factories import UserFactory, UserProfileFactory


@pytest.mark.django_db
class TestUserModel:
    """Test User model."""

    def test_create_user(self):
        """Test creating a user."""
        user = UserFactory(email="test@example.com")
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.check_password("testpass123")

    def test_email_unique(self):
        """Test email must be unique."""
        UserFactory(email="test@example.com")
        with pytest.raises(IntegrityError):
            UserFactory(email="test@example.com")

    def test_full_name_property(self):
        """Test full_name property."""
        user = UserFactory(first_name="John", last_name="Doe")
        assert user.full_name == "John Doe"

    def test_full_name_with_only_first_name(self):
        """Test full_name with only first name."""
        user = UserFactory(first_name="John", last_name="")
        assert user.full_name == "John"

    def test_full_name_with_only_email(self):
        """Test full_name fallback to email."""
        user = UserFactory(first_name="", last_name="")
        assert user.full_name == user.email

    def test_user_str(self):
        """Test user string representation."""
        user = UserFactory(email="test@example.com")
        assert str(user) == "test@example.com"


@pytest.mark.django_db
class TestUserProfileModel:
    """Test UserProfile model."""

    def test_create_profile_with_signal(self):
        """Test profile is auto-created via signal."""
        user = UserFactory()
        assert hasattr(user, "profile")
        assert isinstance(user.profile, UserProfile)

    def test_profile_one_to_one_relationship(self):
        """Test one-to-one relationship with User."""
        user = UserFactory()
        profile = user.profile
        assert profile.user == user

    def test_profile_str(self):
        """Test profile string representation."""
        user = UserFactory(first_name="John", last_name="Doe")
        assert str(user.profile) == "John Doe's Profile"

    def test_profile_timezone_default(self):
        """Test profile timezone default value."""
        profile = UserProfileFactory()
        assert profile.timezone == "UTC"
