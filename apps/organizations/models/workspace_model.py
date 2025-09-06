from django.db import models
from django.conf import settings
from .organization_model import Organization
import uuid


class Workspace(models.Model):
    WORKSPACE_TYPE_CHOICES = [
        ('development', 'Development'),
        ('design', 'Design'),
        ('marketing', 'Marketing'),
        ('sales', 'Sales'),
        ('support', 'Support'),
        ('hr', 'Human Resources'),
        ('finance', 'Finance'),
        ('general', 'General'),
    ]

    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
        ('restricted', 'Restricted'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='workspaces'
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    workspace_type = models.CharField(
        max_length=20,
        choices=WORKSPACE_TYPE_CHOICES,
        default='general'
    )
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='private'
    )
    workspace_settings = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_workspaces'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workspaces'
        verbose_name = 'Workspace'
        verbose_name_plural = 'Workspaces'
        unique_together = ['organization', 'slug']
        ordering = ['name']

    def __str__(self):
        return f"{self.organization.name} - {self.name}"

    @property
    def member_count(self) -> int:
        return self.members.filter(is_active=True).count()

    @property
    def project_count(self) -> int:
        return self.projects.filter(is_active=True).count()


