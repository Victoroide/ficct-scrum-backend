import uuid

from django.conf import settings
from django.db import models


class GitHubIntegration(models.Model):
    SYNC_STATUS_CHOICES = [
        ("idle", "Idle"),
        ("syncing", "Syncing"),
        ("error", "Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="github_integration",
    )
    repository_url = models.URLField(max_length=500)
    repository_owner = models.CharField(max_length=255)
    repository_name = models.CharField(max_length=255)
    access_token = models.BinaryField()
    installation_id = models.CharField(max_length=100, blank=True, null=True)
    webhook_secret = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(
        max_length=20, choices=SYNC_STATUS_CHOICES, default="idle"
    )
    auto_link_commits = models.BooleanField(default=True)
    smart_commits_enabled = models.BooleanField(default=True)
    sync_pull_requests = models.BooleanField(default=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "github_integrations"
        verbose_name = "GitHub Integration"
        verbose_name_plural = "GitHub Integrations"
        ordering = ["-connected_at"]

    def __str__(self):
        return f"{self.project.key} - {self.repository_full_name}"

    @property
    def repository_full_name(self):
        return f"{self.repository_owner}/{self.repository_name}"

    @property
    def github_url(self):
        return f"https://github.com/{self.repository_full_name}"

    @property
    def is_connected(self):
        return self.is_active and bool(self.access_token)

    def set_access_token(self, token: str):
        import base64

        from cryptography.fernet import Fernet

        secret = (
            settings.SECRET_KEY.encode()
            if isinstance(settings.SECRET_KEY, str)
            else settings.SECRET_KEY
        )
        key = base64.urlsafe_b64encode(secret[:32].ljust(32, b"\0"))
        f = Fernet(key)
        token_bytes = token.encode() if isinstance(token, str) else token
        self.access_token = f.encrypt(token_bytes)

    def get_access_token(self) -> str:
        import base64

        from cryptography.fernet import Fernet

        if not self.access_token:
            return ""

        secret = (
            settings.SECRET_KEY.encode()
            if isinstance(settings.SECRET_KEY, str)
            else settings.SECRET_KEY
        )
        key = base64.urlsafe_b64encode(secret[:32].ljust(32, b"\0"))
        f = Fernet(key)

        # Handle memoryview, bytes, or string
        if isinstance(self.access_token, memoryview):
            access_token_bytes = bytes(self.access_token)
        elif isinstance(self.access_token, bytes):
            access_token_bytes = self.access_token
        else:
            access_token_bytes = self.access_token.encode()

        decrypted = f.decrypt(access_token_bytes)
        return decrypted.decode()
