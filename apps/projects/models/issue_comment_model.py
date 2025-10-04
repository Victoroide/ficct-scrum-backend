import uuid

from django.conf import settings
from django.db import models


class IssueComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey(
        "projects.Issue", on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="issue_comments",
    )
    content = models.TextField()
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "issue_comments"
        verbose_name = "Issue Comment"
        verbose_name_plural = "Issue Comments"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["issue", "created_at"]),
            models.Index(fields=["author"]),
        ]

    def __str__(self):
        return f"Comment on {self.issue.key} by {self.author.full_name}"

    def can_edit(self, user):
        return self.author == user

    def can_delete(self, user):
        if self.author == user:
            return True
        if hasattr(self.issue.project, 'team_members'):
            team_member = self.issue.project.team_members.filter(
                user=user, is_active=True
            ).first()
            if team_member and team_member.can_manage_project:
                return True
        if self.issue.project.lead == user:
            return True
        return False
