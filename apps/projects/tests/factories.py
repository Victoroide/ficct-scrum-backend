"""
Factory classes for project models.
"""
import factory
from factory.django import DjangoModelFactory

from apps.authentication.tests.factories import UserFactory
from apps.projects.models import Project, ProjectTeamMember, WorkflowStatus
from apps.workspaces.tests.factories import WorkspaceFactory


class ProjectFactory(DjangoModelFactory):
    """Factory for Project model."""

    class Meta:
        model = Project

    workspace = factory.SubFactory(WorkspaceFactory)
    name = factory.Sequence(lambda n: f"TestProject{n}")
    key = factory.Sequence(lambda n: f"TPRJ{n:04d}")
    description = factory.Faker("text", max_nb_chars=200)
    methodology = factory.Iterator(["scrum", "kanban", "waterfall"])
    status = "planning"
    priority = "medium"
    lead = factory.SubFactory(UserFactory)
    created_by = factory.SubFactory(UserFactory)
    is_active = True


class ProjectTeamMemberFactory(DjangoModelFactory):
    """Factory for ProjectTeamMember model."""

    class Meta:
        model = ProjectTeamMember

    project = factory.SubFactory(ProjectFactory)
    user = factory.SubFactory(UserFactory)
    role = "developer"
    is_active = True


class WorkflowStatusFactory(DjangoModelFactory):
    """Factory for WorkflowStatus model."""

    class Meta:
        model = WorkflowStatus

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"Status {n}")
    category = factory.Iterator(["to_do", "in_progress", "done"])
    description = factory.Faker("sentence")
    color = "#0052CC"
    order = factory.Sequence(lambda n: n)
    is_initial = False
    is_final = False
