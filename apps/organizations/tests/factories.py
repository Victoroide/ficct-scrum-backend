"""
Factory classes for organization models.
"""
import uuid

import factory
from factory.django import DjangoModelFactory

from apps.authentication.tests.factories import UserFactory
from apps.organizations.models import Organization, OrganizationMembership

{{...}}


class OrganizationFactory(DjangoModelFactory):
    """Factory for Organization model."""

    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Organization {n}")
    slug = factory.LazyAttribute(lambda o: f"org-{uuid.uuid4().hex[:8]}")
    description = factory.Faker("text", max_nb_chars=200)
    owner = factory.SubFactory(UserFactory)
    industry = factory.Iterator(
        ["technology", "healthcare", "finance", "education", "other"]
    )
    size = factory.Iterator(["1-10", "11-50", "51-200", "201-500", "501+"])
    is_active = True


class OrganizationMembershipFactory(DjangoModelFactory):
    """Factory for OrganizationMembership model."""

    class Meta:
        model = OrganizationMembership

    organization = factory.SubFactory(OrganizationFactory)
    user = factory.SubFactory(UserFactory)
    role = "member"
    is_active = True


class OrganizationOwnerMembershipFactory(OrganizationMembershipFactory):
    """Factory for organization owner membership."""

    role = "owner"


class OrganizationAdminMembershipFactory(OrganizationMembershipFactory):
    """Factory for organization admin membership."""

    role = "admin"
