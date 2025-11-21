import uuid

from django.conf import settings
from django.db import models


def report_csv_path(instance, filename):
    return f"reports/project_{instance.project.id}/{filename}"


class ReportSnapshot(models.Model):
    REPORT_TYPE_CHOICES = [
        ("velocity", "Velocity Chart"),
        ("sprint_summary", "Sprint Summary"),
        ("team_metrics", "Team Metrics"),
        ("cfd", "Cumulative Flow Diagram"),
        ("burndown", "Burndown Chart"),
        ("custom", "Custom Report"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="report_snapshots"
    )
    sprint = models.ForeignKey(
        "projects.Sprint",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="report_snapshots",
    )
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    report_data = models.JSONField()
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="generated_reports",
    )
    parameters = models.JSONField(default=dict, blank=True)
    csv_file = models.FileField(upload_to=report_csv_path, null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "report_snapshots"
        verbose_name = "Report Snapshot"
        verbose_name_plural = "Report Snapshots"
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["project", "report_type"]),
            models.Index(fields=["sprint"]),
            models.Index(fields=["generated_at"]),
        ]

    def __str__(self):
        return f"{self.project.key} - {self.get_report_type_display()} - {self.generated_at.date()}"  # noqa: E501

    @property
    def formatted_period(self):
        if self.start_date and self.end_date:
            return f"{self.start_date} to {self.end_date}"
        elif self.sprint:
            return f"Sprint: {self.sprint.name}"
        return "All time"

    @property
    def download_url(self):
        if self.csv_file:
            return self.csv_file.url
        return None
