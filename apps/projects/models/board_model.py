import uuid

from django.conf import settings
from django.db import models


class Board(models.Model):
    BOARD_TYPE_CHOICES = [
        ("kanban", "Kanban"),
        ("scrum", "Scrum"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="boards"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    board_type = models.CharField(
        max_length=20, choices=BOARD_TYPE_CHOICES, default="kanban"
    )
    saved_filter = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_boards",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "boards"
        verbose_name = "Board"
        verbose_name_plural = "Boards"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["project"]),
        ]

    def __str__(self):
        return f"{self.project.key} - {self.name}"

    @property
    def column_count(self):
        return self.columns.count()

    @property
    def issue_count(self):
        if hasattr(self, "project"):
            return self.project.issues.filter(is_active=True).count()
        return 0


class BoardColumn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.ForeignKey(
        "projects.Board", on_delete=models.CASCADE, related_name="columns"
    )
    workflow_status = models.ForeignKey(
        "projects.WorkflowStatus",
        on_delete=models.CASCADE,
        related_name="board_columns",
    )
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    min_wip = models.PositiveIntegerField(null=True, blank=True)
    max_wip = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "board_columns"
        verbose_name = "Board Column"
        verbose_name_plural = "Board Columns"
        unique_together = ["board", "order"]
        ordering = ["order"]
        indexes = [
            models.Index(fields=["board", "order"]),
        ]

    def __str__(self):
        return f"{self.board.name} - {self.name}"

    @property
    def issue_count(self):
        return self.workflow_status.issues.filter(
            project=self.board.project, is_active=True
        ).count()

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.workflow_status.project != self.board.project:
            raise ValidationError(
                "Workflow status must belong to the same project as the board"
            )
        if self.min_wip and self.max_wip and self.min_wip > self.max_wip:
            raise ValidationError("Minimum WIP cannot be greater than maximum WIP")
