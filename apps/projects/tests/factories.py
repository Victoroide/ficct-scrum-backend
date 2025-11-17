"""
Factory classes for project models.
"""
import factory
from factory.django import DjangoModelFactory

from apps.authentication.tests.factories import UserFactory
from apps.projects.models import (
    Board,
    BoardColumn,
    Issue,
    IssueAttachment,
    IssueComment,
    IssueLink,
    IssueType,
    Project,
    ProjectTeamMember,
    Sprint,
    WorkflowStatus,
)
from apps.workspaces.tests.factories import WorkspaceFactory


class ProjectFactory(DjangoModelFactory):
    """Factory for Project model."""

    class Meta:
        model = Project

    workspace = factory.SubFactory(WorkspaceFactory)
    name = factory.Sequence(lambda n: f"TestProject{n}")
    key = factory.Sequence(lambda n: f"TPRJ{n:04d}")
    description = factory.Faker("text", max_nb_chars=200)
    methodology = factory.Iterator(("scrum", "kanban", "waterfall"))
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
    category = factory.Iterator(("to_do", "in_progress", "done"))
    description = factory.Faker("sentence")
    color = "#0052CC"
    order = factory.Sequence(lambda n: n)
    is_initial = False
    is_final = False


class IssueTypeFactory(DjangoModelFactory):
    """Factory for IssueType model."""

    class Meta:
        model = IssueType

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"Issue Type {n}")
    category = factory.Iterator(("epic", "story", "task", "bug"))
    description = factory.Faker("sentence")
    icon = "issue-icon"
    color = "#0052CC"
    is_default = False
    is_active = True


class IssueFactory(DjangoModelFactory):
    """Factory for Issue model."""

    class Meta:
        model = Issue

    project = factory.SubFactory(ProjectFactory)
    issue_type = factory.SubFactory(
        IssueTypeFactory, project=factory.SelfAttribute("..project")
    )
    status = factory.SubFactory(
        WorkflowStatusFactory, project=factory.SelfAttribute("..project")
    )
    key = factory.Sequence(lambda n: str(n))
    title = factory.Faker("sentence", nb_words=6)
    description = factory.Faker("text", max_nb_chars=200)
    priority = factory.Iterator(("P1", "P2", "P3", "P4"))
    reporter = factory.SubFactory(UserFactory)
    assignee = factory.SubFactory(UserFactory)
    estimated_hours = factory.Faker(
        "pydecimal", left_digits=3, right_digits=2, positive=True
    )
    story_points = factory.Faker("random_int", min=1, max=13)
    order = factory.Sequence(lambda n: n)
    is_active = True


class SprintFactory(DjangoModelFactory):
    """Factory for Sprint model."""

    class Meta:
        model = Sprint

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"Sprint {n}")
    goal = factory.Faker("sentence")
    status = "planning"
    start_date = factory.Faker("date_this_month")
    end_date = factory.Faker("date_this_month")
    committed_points = 0
    completed_points = 0
    created_by = factory.SubFactory(UserFactory)


class BoardFactory(DjangoModelFactory):
    """Factory for Board model."""

    class Meta:
        model = Board

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"Board {n}")
    description = factory.Faker("sentence")
    board_type = factory.Iterator(("kanban", "scrum"))
    created_by = factory.SubFactory(UserFactory)


class BoardColumnFactory(DjangoModelFactory):
    """Factory for BoardColumn model."""

    class Meta:
        model = BoardColumn

    board = factory.SubFactory(BoardFactory)
    workflow_status = factory.SubFactory(
        WorkflowStatusFactory, project=factory.SelfAttribute("..board.project")
    )
    name = factory.Sequence(lambda n: f"Column {n}")
    order = factory.Sequence(lambda n: n)


class IssueCommentFactory(DjangoModelFactory):
    """Factory for IssueComment model."""

    class Meta:
        model = IssueComment

    issue = factory.SubFactory(IssueFactory)
    author = factory.SubFactory(UserFactory)
    content = factory.Faker("text", max_nb_chars=500)
    is_edited = False


class IssueAttachmentFactory(DjangoModelFactory):
    """Factory for IssueAttachment model."""

    class Meta:
        model = IssueAttachment

    issue = factory.SubFactory(IssueFactory)
    file = factory.django.FileField(filename="test_file.pdf")
    filename = "test_file.pdf"
    file_size = 1024
    content_type = "application/pdf"
    uploaded_by = factory.SubFactory(UserFactory)


class IssueLinkFactory(DjangoModelFactory):
    """Factory for IssueLink model."""

    class Meta:
        model = IssueLink

    source_issue = factory.SubFactory(IssueFactory)
    target_issue = factory.SubFactory(
        IssueFactory, project=factory.SelfAttribute("..source_issue.project")
    )
    link_type = factory.Iterator(("blocks", "relates_to", "duplicates"))
    created_by = factory.SubFactory(UserFactory)
