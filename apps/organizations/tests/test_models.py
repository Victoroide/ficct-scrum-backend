"""
Tests for organization models.
"""
from django.db import IntegrityError

import pytest

from apps.authentication.tests.factories import UserFactory
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    OrganizationOwnerMembershipFactory,
)


@pytest.mark.django_db
class TestOrganizationModel:
    """Test Organization model."""

    def test_create_organization(self):
        """Test creating an organization."""
        org = OrganizationFactory(name="Test Org", slug="test-org")
        assert org.name == "Test Org"
        assert org.slug == "test-org"
        assert org.is_active is True

    def test_slug_unique(self):
        """Test organization slug must be unique."""
        OrganizationFactory(slug="test-org")
        with pytest.raises(IntegrityError):
            OrganizationFactory(slug="test-org")

    def test_organization_str(self):
        """Test organization string representation."""
        org = OrganizationFactory(name="Test Org")
        assert str(org) == "Test Org"

    def test_owner_relationship(self):
        """Test owner relationship."""
        user = UserFactory()
        org = OrganizationFactory(owner=user)
        assert org.owner == user


@pytest.mark.django_db
class TestOrganizationMembershipModel:
    """Test OrganizationMembership model."""

    def test_create_membership(self):
        """Test creating a membership."""
        membership = OrganizationMembershipFactory()
        assert membership.is_active is True
        assert membership.role == "member"

    def test_membership_roles(self):
        """Test different membership roles."""
        owner = OrganizationOwnerMembershipFactory()
        assert owner.role == "owner"

        member = OrganizationMembershipFactory(role="admin")
        assert member.role == "admin"

    def test_membership_str(self):
        """Test membership string representation."""
        user = UserFactory(email="test@example.com")
        org = OrganizationFactory(name="Test Org")
        membership = OrganizationMembershipFactory(user=user, organization=org)
        assert str(membership) == "test@example.com - Test Org (member)"

    def test_unique_together_constraint(self):
        """Test user can only have one membership per organization."""
        user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(user=user, organization=org)

        with pytest.raises(IntegrityError):
            OrganizationMembershipFactory(user=user, organization=org)

    def test_can_manage_members_property(self):
        """Test can_manage_members property for different roles."""
        org = OrganizationFactory()
        user = UserFactory()

        # Owner can manage
        owner_membership = OrganizationMembershipFactory(
            user=user, organization=org, role="owner"
        )
        assert owner_membership.can_manage_members is True

        # Admin can manage
        admin_membership = OrganizationMembershipFactory(organization=org, role="admin")
        assert admin_membership.can_manage_members is True

        # Manager can manage
        manager_membership = OrganizationMembershipFactory(
            organization=org, role="manager"
        )
        assert manager_membership.can_manage_members is True

        # Regular member cannot
        member = OrganizationMembershipFactory(organization=org, role="member")
        assert member.can_manage_members is False
