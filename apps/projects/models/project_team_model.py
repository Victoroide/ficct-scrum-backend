from django.db import models
from django.conf import settings
import uuid


class ProjectTeamMember(models.Model):
    ROLE_CHOICES = [
        ('project_manager', 'Project Manager'),
        ('tech_lead', 'Tech Lead'),
        ('developer', 'Developer'),
        ('designer', 'Designer'),
        ('qa_engineer', 'QA Engineer'),
        ('business_analyst', 'Business Analyst'),
        ('stakeholder', 'Stakeholder'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='team_members'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_memberships'
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='developer')
    permissions = models.JSONField(default=dict)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'project_team_members'
        verbose_name = 'Project Team Member'
        verbose_name_plural = 'Project Team Members'
        unique_together = ['project', 'user']
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.project.name} ({self.role})"

    @property
    def can_manage_project(self):
        return self.role in ['project_manager', 'tech_lead']

    @property
    def can_create_issues(self):
        return self.role in ['project_manager', 'tech_lead', 'developer', 'business_analyst']
