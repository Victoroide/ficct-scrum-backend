from django.db import models
import uuid


class WorkflowStatus(models.Model):
    STATUS_CATEGORY_CHOICES = [
        ('to_do', 'To Do'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='workflow_statuses'
    )
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=STATUS_CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#DFE1E6')
    order = models.PositiveIntegerField(default=0)
    is_initial = models.BooleanField(default=False)
    is_final = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workflow_statuses'
        verbose_name = 'Workflow Status'
        verbose_name_plural = 'Workflow Statuses'
        unique_together = ['project', 'name']
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.project.key} - {self.name}"


class WorkflowTransition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='workflow_transitions'
    )
    name = models.CharField(max_length=100)
    from_status = models.ForeignKey(
        'projects.WorkflowStatus',
        on_delete=models.CASCADE,
        related_name='outgoing_transitions'
    )
    to_status = models.ForeignKey(
        'projects.WorkflowStatus',
        on_delete=models.CASCADE,
        related_name='incoming_transitions'
    )
    conditions = models.JSONField(default=dict)
    validators = models.JSONField(default=dict)
    post_functions = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workflow_transitions'
        verbose_name = 'Workflow Transition'
        verbose_name_plural = 'Workflow Transitions'
        unique_together = ['project', 'from_status', 'to_status']
        ordering = ['name']

    def __str__(self):
        return f"{self.project.key} - {self.from_status.name} → {self.to_status.name}"
