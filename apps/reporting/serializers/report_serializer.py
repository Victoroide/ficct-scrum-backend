from rest_framework import serializers

from apps.reporting.models import ReportSnapshot


class ReportRequestSerializer(serializers.Serializer):
    REPORT_TYPE_CHOICES = [
        ("velocity", "Velocity"),
        ("sprint_summary", "Sprint Summary"),
        ("team_metrics", "Team Metrics"),
        ("cfd", "Cumulative Flow Diagram"),
    ]

    report_type = serializers.ChoiceField(choices=REPORT_TYPE_CHOICES, required=True)
    project = serializers.UUIDField(required=True)
    sprint = serializers.UUIDField(required=False, allow_null=True)
    period_days = serializers.IntegerField(required=False, default=30)
    num_sprints = serializers.IntegerField(required=False, default=5)


class ExportRequestSerializer(serializers.Serializer):
    """
    Serializer for data export requests.
    
    Supports exporting issues, sprints, commits, and activity logs to CSV format.
    Apply optional filters to narrow down results.
    """
    DATA_TYPE_CHOICES = [
        ("issues", "Issues"),
        ("sprints", "Sprints"),
        ("commits", "Commits"),
        ("activity", "Activity Log"),
    ]

    data_type = serializers.ChoiceField(
        choices=DATA_TYPE_CHOICES, 
        required=True,
        help_text="Type of data to export: issues, sprints, commits, or activity"
    )
    project = serializers.UUIDField(
        required=True,
        help_text="Project UUID to export data from"
    )
    
    # Date range filters
    start_date = serializers.DateField(
        required=False, 
        allow_null=True,
        help_text="Start date for filtering (YYYY-MM-DD). Example: 2024-01-01"
    )
    end_date = serializers.DateField(
        required=False, 
        allow_null=True,
        help_text="End date for filtering (YYYY-MM-DD). Example: 2024-12-31"
    )
    
    # Issue-specific filters
    sprint_id = serializers.UUIDField(
        required=False, 
        allow_null=True,
        help_text="Filter issues by sprint UUID"
    )
    status_id = serializers.UUIDField(
        required=False, 
        allow_null=True,
        help_text="Filter issues by status UUID"
    )
    assignee_id = serializers.UUIDField(
        required=False, 
        allow_null=True,
        help_text="Filter issues by assignee user UUID"
    )
    issue_type_id = serializers.UUIDField(
        required=False, 
        allow_null=True,
        help_text="Filter issues by issue type UUID"
    )
    priority = serializers.ChoiceField(
        choices=[("P1", "P1"), ("P2", "P2"), ("P3", "P3"), ("P4", "P4")],
        required=False,
        allow_null=True,
        help_text="Filter issues by priority (P1, P2, P3, P4)"
    )
    
    # Activity-specific filters
    user_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Filter activities by user UUID"
    )
    action_type = serializers.ChoiceField(
        choices=[
            ("created", "Created"),
            ("updated", "Updated"),
            ("deleted", "Deleted"),
            ("transitioned", "Transitioned"),
            ("commented", "Commented"),
        ],
        required=False,
        allow_null=True,
        help_text="Filter activities by action type"
    )
    
    # Legacy support
    filters = serializers.JSONField(
        required=False, 
        default=dict,
        help_text="(Deprecated) Use specific filter fields instead. Legacy JSON filter object."
    )


class ReportSnapshotSerializer(serializers.ModelSerializer):
    formatted_period = serializers.CharField(read_only=True)
    download_url = serializers.CharField(read_only=True)

    class Meta:
        model = ReportSnapshot
        fields = [
            "id",
            "project",
            "sprint",
            "report_type",
            "report_data",
            "start_date",
            "end_date",
            "formatted_period",
            "generated_by",
            "parameters",
            "csv_file",
            "download_url",
            "generated_at",
        ]
        read_only_fields = fields
