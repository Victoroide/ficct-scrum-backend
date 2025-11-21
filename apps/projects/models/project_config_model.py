
from django.db import models


class ProjectConfiguration(models.Model):
    SPRINT_DURATION_CHOICES = [
        (1, "1 Week"),
        (2, "2 Weeks"),
        (3, "3 Weeks"),
        (4, "4 Weeks"),
    ]

    ESTIMATION_TYPE_CHOICES = [
        ("story_points", "Story Points"),
        ("hours", "Hours"),
        ("t_shirt", "T-Shirt Sizes"),
    ]

    project = models.OneToOneField(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="configuration",
        primary_key=True,
    )

    # Sprint Configuration
    sprint_duration = models.PositiveIntegerField(
        choices=SPRINT_DURATION_CHOICES, default=2, help_text="Sprint duration in weeks"
    )
    auto_close_sprints = models.BooleanField(default=True)

    # Estimation Configuration
    estimation_type = models.CharField(
        max_length=20, choices=ESTIMATION_TYPE_CHOICES, default="story_points"
    )
    story_point_scale = models.JSONField(
        default=list, help_text="Fibonacci sequence: [1, 2, 3, 5, 8, 13, 21]"
    )

    # Workflow Configuration
    enable_time_tracking = models.BooleanField(default=True)
    require_time_logging = models.BooleanField(default=False)
    enable_sub_tasks = models.BooleanField(default=True)

    # Notification Configuration
    email_notifications = models.BooleanField(default=True)
    slack_notifications = models.BooleanField(default=False)
    slack_webhook_url = models.URLField(
        blank=True,
        null=True,
        help_text="Slack webhook URL for notifications (optional)",
    )

    # Security Configuration
    restrict_issue_visibility = models.BooleanField(default=False)
    require_approval_for_changes = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_configurations"
        verbose_name = "Project Configuration"
        verbose_name_plural = "Project Configurations"

    def __str__(self):
        return f"Config for {self.project.name}"
