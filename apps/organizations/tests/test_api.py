"""
Tests for organization API endpoints.
"""
from django.urls import reverse

import pytest
from rest_framework import status

from apps.authentication.tests.factories import UserFactory
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
)


@pytest.mark.django_db
class TestOrganizationAPI:
    """Test Organization CRUD endpoints."""

    def test_create_organization(self, authenticated_client):
        """Test creating an organization."""
        url = reverse("organization-list")
        data = {
            "name": "New Organization",
            "slug": "new-org",
            "description": "Test description",
            "industry": "technology",
            "size": "11-50",
        }
        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Organization.objects.filter(slug="new-org").exists()

        # Creator should be owner
        org = Organization.objects.get(slug="new-org")
        assert OrganizationMembership.objects.filter(
            organization=org, role="owner"
        ).exists()

    def test_list_organizations_only_member_orgs(self, api_client):
        """Test listing only organizations user is member of."""
        user = UserFactory(password="testpass123")
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        # User is only member of org1
        OrganizationMembershipFactory(organization=org1, user=user)

        # Authenticate
        api_client.force_authenticate(user=user)

        url = reverse("organization-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["id"] == str(org1.id)

    def test_retrieve_organization_as_member(self, api_client):
        """Test retrieving organization as a member."""
        user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=user)

        api_client.force_authenticate(user=user)

        url = reverse("organization-detail", args=[org.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(org.id)

    def test_retrieve_organization_as_non_member(self, api_client):
        """Test retrieving organization as non-member fails."""
        user = UserFactory()
        org = OrganizationFactory()
        # User is NOT a member

        api_client.force_authenticate(user=user)

        url = reverse("organization-detail", args=[org.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_organization_as_owner(self, api_client):
        """Test updating organization as owner."""
        user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=user, role="owner")

        api_client.force_authenticate(user=user)

        url = reverse("organization-detail", args=[org.id])
        data = {"name": "Updated Name"}
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Name"

    def test_update_organization_as_member_fails(self, api_client):
        """Test updating organization as regular member fails."""
        user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=user, role="member")

        api_client.force_authenticate(user=user)

        url = reverse("organization-detail", args=[org.id])
        data = {"name": "Updated Name"}
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_organization_as_owner(self, api_client):
        """Test deleting organization as owner."""
        user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=user, role="owner")

        api_client.force_authenticate(user=user)

        url = reverse("organization-detail", args=[org.id])
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_organization_as_member_fails(self, api_client):
        """Test deleting organization as regular member fails."""
        user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=user, role="member")

        api_client.force_authenticate(user=user)

        url = reverse("organization-detail", args=[org.id])
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestOrganizationMemberAPI:
    """Test Organization Member endpoints."""

    def test_invite_member_as_admin(self, api_client):
        """Test inviting member as admin."""
        admin_user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=admin_user, role="admin")

        new_user = UserFactory()

        api_client.force_authenticate(user=admin_user)

        url = reverse("organizationmembership-list")
        data = {
            "organization": str(org.id),
            "user_id": str(new_user.id),
            "role": "member",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_invite_member_as_regular_member_fails(self, api_client):
        """Test inviting member as regular member fails."""
        member = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=member, role="member")

        new_user = UserFactory()

        api_client.force_authenticate(user=member)

        url = reverse("organizationmembership-list")
        data = {
            "organization": str(org.id),
            "user_id": str(new_user.id),
            "role": "member",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
