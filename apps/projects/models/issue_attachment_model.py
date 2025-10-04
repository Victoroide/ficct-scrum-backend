import uuid

from django.conf import settings
from django.db import models


def issue_attachment_path(instance, filename):
    return f"issues/issue_{instance.issue.id}/attachments/{filename}"


class IssueAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey(
        "projects.Issue", on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to=issue_attachment_path)
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_issue_attachments",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "issue_attachments"
        verbose_name = "Issue Attachment"
        verbose_name_plural = "Issue Attachments"
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["issue"]),
            models.Index(fields=["uploaded_by"]),
        ]

    def __str__(self):
        return f"{self.filename} on {self.issue.key}"

    @property
    def file_url(self):
        if self.file:
            return self.file.url
        return None

    @property
    def file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2)
