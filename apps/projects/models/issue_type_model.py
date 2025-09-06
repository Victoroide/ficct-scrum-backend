from django.db import models
import uuid


class IssueType(models.Model):
    TYPE_CATEGORY_CHOICES = [
        ('epic', 'Epic'),
        ('story', 'Story'),
        ('task', 'Task'),
        ('bug', 'Bug'),
        ('improvement', 'Improvement'),
        ('sub_task', 'Sub-task'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='issue_types'
    )
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=TYPE_CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default='#0052CC')
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'issue_types'
        verbose_name = 'Issue Type'
        verbose_name_plural = 'Issue Types'
        unique_together = ['project', 'name']
        ordering = ['name']

    def __str__(self):
        return f"{self.project.key} - {self.name}"
