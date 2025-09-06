from django.db import models
from django.conf import settings
from apps.organizations.models import Workspace
import uuid


class Project(models.Model):
    METHODOLOGY_CHOICES = [
        ('scrum', 'Scrum'),
        ('kanban', 'Kanban'),
        ('waterfall', 'Waterfall'),
        ('hybrid', 'Hybrid'),
    ]

    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('archived', 'Archived'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='projects'
    )
    name = models.CharField(max_length=255)
    key = models.CharField(max_length=10)
    description = models.TextField(blank=True)
    methodology = models.CharField(
        max_length=20,
        choices=METHODOLOGY_CHOICES,
        default='scrum'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planning'
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='led_projects'
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    estimated_hours = models.PositiveIntegerField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    project_settings = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_projects'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'projects'
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'
        unique_together = ['workspace', 'key']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.key} - {self.name}"

    @property
    def team_member_count(self) -> int:
        return self.team_members.filter(is_active=True).count()

    @property
    def issue_count(self) -> int:
        return self.issues.filter(is_active=True).count()


