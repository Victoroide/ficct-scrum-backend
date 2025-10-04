import pytest
from django.core.exceptions import ValidationError

from apps.projects.models import Issue, IssueLink
from apps.projects.tests.factories import (
    IssueFactory,
    IssueLinkFactory,
    IssueTypeFactory,
    ProjectFactory,
    WorkflowStatusFactory,
)


@pytest.mark.django_db
class TestIssueModel:
    def test_issue_creation(self):
        issue = IssueFactory()
        assert issue.id is not None
        assert issue.key is not None
        assert issue.title is not None
        assert issue.is_active is True

    def test_issue_unique_key_per_project(self):
        project = ProjectFactory()
        IssueFactory(project=project, key="1")

        with pytest.raises(Exception):
            IssueFactory(project=project, key="1")

    def test_issue_same_key_different_projects(self):
        project1 = ProjectFactory()
        project2 = ProjectFactory()

        issue1 = IssueFactory(project=project1, key="100")
        issue2 = IssueFactory(project=project2, key="100")

        assert issue1.key == issue2.key
        assert issue1.project != issue2.project

    def test_issue_full_key_property(self):
        project = ProjectFactory(key="PROJ")
        issue = IssueFactory(project=project, key="123")
        assert issue.full_key == "PROJ-123"

    def test_issue_type_properties(self):
        project = ProjectFactory()
        epic_type = IssueTypeFactory(project=project, category="epic")
        story_type = IssueTypeFactory(project=project, category="story")
        task_type = IssueTypeFactory(project=project, category="task")
        bug_type = IssueTypeFactory(project=project, category="bug")

        epic = IssueFactory(project=project, issue_type=epic_type)
        story = IssueFactory(project=project, issue_type=story_type)
        task = IssueFactory(project=project, issue_type=task_type)
        bug = IssueFactory(project=project, issue_type=bug_type)

        assert epic.is_epic is True
        assert story.is_story is True
        assert task.is_task is True
        assert bug.is_bug is True

    def test_issue_comment_count(self):
        from apps.projects.tests.factories import IssueCommentFactory

        issue = IssueFactory()
        IssueCommentFactory(issue=issue)
        IssueCommentFactory(issue=issue)

        assert issue.comment_count == 2

    def test_issue_attachment_count(self):
        from apps.projects.tests.factories import IssueAttachmentFactory

        issue = IssueFactory()
        IssueAttachmentFactory(issue=issue)

        assert issue.attachment_count == 1

    def test_issue_link_count(self):
        issue1 = IssueFactory()
        issue2 = IssueFactory(project=issue1.project)

        IssueLinkFactory(source_issue=issue1, target_issue=issue2)

        assert issue1.link_count >= 1


@pytest.mark.django_db
class TestIssueLinkModel:
    def test_issue_link_creation(self):
        link = IssueLinkFactory()
        assert link.id is not None
        assert link.source_issue != link.target_issue

    def test_issue_link_prevents_self_linking(self):
        issue = IssueFactory()

        link = IssueLink(
            source_issue=issue,
            target_issue=issue,
            link_type="relates_to",
            created_by=issue.reporter
        )

        with pytest.raises(ValidationError):
            link.full_clean()

    def test_issue_link_same_project_validation(self):
        issue1 = IssueFactory()
        issue2 = IssueFactory()

        link = IssueLink(
            source_issue=issue1,
            target_issue=issue2,
            link_type="relates_to",
            created_by=issue1.reporter
        )

        with pytest.raises(ValidationError):
            link.full_clean()

    def test_issue_link_reciprocal_types(self):
        assert IssueLink.get_reciprocal_link_type("blocks") == "blocked_by"
        assert IssueLink.get_reciprocal_link_type("blocked_by") == "blocks"
        assert IssueLink.get_reciprocal_link_type("duplicates") == "duplicated_by"
        assert IssueLink.get_reciprocal_link_type("duplicated_by") == "duplicates"
        assert IssueLink.get_reciprocal_link_type("depends_on") == "dependency_of"
        assert IssueLink.get_reciprocal_link_type("dependency_of") == "depends_on"
        assert IssueLink.get_reciprocal_link_type("relates_to") == "relates_to"
