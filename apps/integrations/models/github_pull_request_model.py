import uuid

from django.db import models


class GitHubPullRequest(models.Model):
    STATE_CHOICES = [
        ("open", "Open"),
        ("closed", "Closed"),
        ("merged", "Merged"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository = models.ForeignKey(
        "integrations.GitHubIntegration",
        on_delete=models.CASCADE,
        related_name="pull_requests",
    )
    pr_number = models.IntegerField()
    title = models.CharField(max_length=500)
    state = models.CharField(max_length=20, choices=STATE_CHOICES)
    body = models.TextField(blank=True)
    base_branch = models.CharField(max_length=255)
    head_branch = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    linked_issues = models.ManyToManyField(
        "projects.Issue", related_name="pull_requests", blank=True
    )
    additions = models.IntegerField(default=0)
    deletions = models.IntegerField(default=0)
    changed_files = models.IntegerField(default=0)
    commits_count = models.IntegerField(default=0)
    merged_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "github_pull_requests"
        verbose_name = "GitHub Pull Request"
        verbose_name_plural = "GitHub Pull Requests"
        unique_together = ["repository", "pr_number"]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["repository", "state"]),
            models.Index(fields=["pr_number"]),
            models.Index(fields=["state"]),
        ]

    def __str__(self):
        return f"PR #{self.pr_number} - {self.title}"

    @property
    def is_open(self):
        return self.state == "open"

    @property
    def is_merged(self):
        return self.state == "merged"

    @property
    def status_label(self):
        if self.is_merged:
            return "Merged"
        elif self.is_open:
            return "Open"
        else:
            return "Closed"
