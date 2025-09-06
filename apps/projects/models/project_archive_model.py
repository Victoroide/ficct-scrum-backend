from django.db import models
from django.conf import settings
import uuid


class ProjectArchive(models.Model):
    ARCHIVE_REASON_CHOICES = [
        ('completed', 'Project Completed'),
        ('cancelled', 'Project Cancelled'),
        ('on_hold', 'Project On Hold'),
        ('merged', 'Merged with Another Project'),
        ('obsolete', 'Project Obsolete'),
        ('other', 'Other Reason'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='archive_info'
    )
    reason = models.CharField(
        max_length=20,
        choices=ARCHIVE_REASON_CHOICES,
        default='completed'
    )
    description = models.TextField(
        blank=True,
        help_text="Additional details about why the project was archived"
    )
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='archived_projects'
    )
    archived_at = models.DateTimeField(auto_now_add=True)
    
    # Backup data before archiving
    final_statistics = models.JSONField(
        default=dict,
        help_text="Final project statistics (issues, sprints, team members, etc.)"
    )
    backup_data = models.JSONField(
        default=dict,
        help_text="Backup of critical project data"
    )
    
    # Restoration settings
    can_be_restored = models.BooleanField(default=True)
    auto_delete_after_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Automatically delete after X days (null = never delete)"
    )

    class Meta:
        db_table = 'project_archives'
        verbose_name = 'Project Archive'
        verbose_name_plural = 'Project Archives'
        ordering = ['-archived_at']

    def __str__(self):
        return f"Archive: {self.project.name} ({self.reason})"

    @property
    def is_restorable(self):
        return self.can_be_restored and self.project.status == 'archived'
