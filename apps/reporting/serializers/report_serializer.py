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
    DATA_TYPE_CHOICES = [
        ("issues", "Issues"),
        ("sprints", "Sprints"),
        ("commits", "Commits"),
    ]

    data_type = serializers.ChoiceField(choices=DATA_TYPE_CHOICES, required=True)
    project = serializers.UUIDField(required=True)
    filters = serializers.JSONField(required=False, default=dict)


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
