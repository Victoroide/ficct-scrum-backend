import uuid

from django.conf import settings
from django.db import models


class Issue(models.Model):
    PRIORITY_CHOICES = [
        ("P1", "Critical"),
        ("P2", "High"),
        ("P3", "Medium"),
        ("P4", "Low"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="issues"
    )
    issue_type = models.ForeignKey(
        "projects.IssueType", on_delete=models.PROTECT, related_name="issues"
    )
    status = models.ForeignKey(
        "projects.WorkflowStatus", on_delete=models.PROTECT, related_name="issues"
    )
    parent_issue = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sub_issues",
    )
    sprint = models.ForeignKey(
        "projects.Sprint",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issues",
    )
    key = models.CharField(max_length=20)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=2, choices=PRIORITY_CHOICES, default="P3")
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_issues",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reported_issues",
    )
    estimated_hours = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    actual_hours = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    story_points = models.PositiveIntegerField(null=True, blank=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "issues"
        verbose_name = "Issue"
        verbose_name_plural = "Issues"
        unique_together = ["project", "key"]
        ordering = ["order", "-created_at"]
        indexes = [
            models.Index(fields=["project", "key"]),
            models.Index(fields=["assignee"]),
            models.Index(fields=["sprint"]),
            models.Index(fields=["status"]),
            models.Index(fields=["priority"]),
        ]

    def __str__(self):
        return f"{self.key} - {self.title}"

    @property
    def full_key(self):
        return f"{self.project.key}-{self.key}"

    @property
    def is_epic(self):
        return self.issue_type.category == "epic"

    @property
    def is_story(self):
        return self.issue_type.category == "story"

    @property
    def is_task(self):
        return self.issue_type.category == "task"

    @property
    def is_bug(self):
        return self.issue_type.category == "bug"

    @property
    def comment_count(self):
        return self.comments.count()

    @property
    def attachment_count(self):
        return self.attachments.count()

    @property
    def link_count(self):
        return self.source_links.count() + self.target_links.count()
