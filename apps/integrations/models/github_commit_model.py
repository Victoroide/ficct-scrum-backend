import uuid

from django.db import models


class GitHubCommit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository = models.ForeignKey(
        "integrations.GitHubIntegration",
        on_delete=models.CASCADE,
        related_name="commits",
    )
    sha = models.CharField(max_length=40)
    message = models.TextField()
    author_name = models.CharField(max_length=255)
    author_email = models.EmailField()
    commit_date = models.DateTimeField()
    branch = models.CharField(max_length=255, default="main")
    url = models.URLField(max_length=500)
    linked_issues = models.ManyToManyField(
        "projects.Issue", related_name="commits", blank=True
    )
    synced_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "github_commits"
        verbose_name = "GitHub Commit"
        verbose_name_plural = "GitHub Commits"
        unique_together = ["repository", "sha"]
        ordering = ["-commit_date"]
        indexes = [
            models.Index(fields=["repository", "commit_date"]),
            models.Index(fields=["sha"]),
            models.Index(fields=["author_email"]),
        ]

    def __str__(self):
        return f"{self.short_sha} - {self.message[:50]}"

    @property
    def short_sha(self):
        return self.sha[:7]

    @property
    def formatted_message(self):
        lines = self.message.split("\n")
        return lines[0] if lines else self.message

    @property
    def issue_keys_mentioned(self):
        import re

        pattern = r"[A-Z]+-\d+"
        return re.findall(pattern, self.message)
