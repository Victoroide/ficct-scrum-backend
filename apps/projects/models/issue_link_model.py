import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class IssueLink(models.Model):
    LINK_TYPE_CHOICES = [
        ("blocks", "Blocks"),
        ("blocked_by", "Blocked By"),
        ("relates_to", "Relates To"),
        ("duplicates", "Duplicates"),
        ("duplicated_by", "Duplicated By"),
        ("depends_on", "Depends On"),
        ("dependency_of", "Dependency Of"),
    ]

    RECIPROCAL_LINKS = {
        "blocks": "blocked_by",
        "blocked_by": "blocks",
        "duplicates": "duplicated_by",
        "duplicated_by": "duplicates",
        "depends_on": "dependency_of",
        "dependency_of": "depends_on",
        "relates_to": "relates_to",
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_issue = models.ForeignKey(
        "projects.Issue", on_delete=models.CASCADE, related_name="source_links"
    )
    target_issue = models.ForeignKey(
        "projects.Issue", on_delete=models.CASCADE, related_name="target_links"
    )
    link_type = models.CharField(max_length=20, choices=LINK_TYPE_CHOICES)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_issue_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "issue_links"
        verbose_name = "Issue Link"
        verbose_name_plural = "Issue Links"
        unique_together = ["source_issue", "target_issue", "link_type"]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source_issue"]),
            models.Index(fields=["target_issue"]),
        ]

    def __str__(self):
        return f"{self.source_issue.key} {self.link_type} {self.target_issue.key}"

    def clean(self):
        if self.source_issue == self.target_issue:
            raise ValidationError("Cannot link an issue to itself")
        if self.source_issue.project != self.target_issue.project:
            raise ValidationError("Both issues must belong to the same project")

    @classmethod
    def get_reciprocal_link_type(cls, link_type):
        return cls.RECIPROCAL_LINKS.get(link_type, link_type)
