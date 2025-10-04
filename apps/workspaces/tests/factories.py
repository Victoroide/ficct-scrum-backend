"""
Factory classes for workspace models.
"""
import factory
from factory.django import DjangoModelFactory

from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import OrganizationFactory
from apps.workspaces.models import Workspace, WorkspaceMember


class WorkspaceFactory(DjangoModelFactory):
    """Factory for Workspace model."""

    class Meta:
        model = Workspace

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Workspace {n}")
    description = factory.Faker("text", max_nb_chars=200)
    created_by = factory.SubFactory(UserFactory)
    visibility = "private"
    is_active = True


class WorkspaceMemberFactory(DjangoModelFactory):
    """Factory for WorkspaceMember model."""

    class Meta:
        model = WorkspaceMember

    workspace = factory.SubFactory(WorkspaceFactory)
    user = factory.SubFactory(UserFactory)
    role = "member"
    is_active = True


class WorkspaceAdminMemberFactory(WorkspaceMemberFactory):
    """Factory for workspace admin membership."""

    role = "admin"
