"""
Management command to detect anomalies in projects.

Usage:
    python manage.py detect_anomalies --project=<uuid>
    python manage.py detect_anomalies --all
    python manage.py detect_anomalies --sprint=<uuid>
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from apps.ml.services import AnomalyDetectionService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Detect anomalies in projects or sprints"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--project",
            type=str,
            default=None,
            help="Project UUID to analyze",
        )
        parser.add_argument(
            "--sprint",
            type=str,
            default=None,
            help="Sprint UUID to analyze for risks",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Analyze all active projects",
        )

    def handle(self, *args, **options):
        """Execute command."""
        project_id = options.get("project")
        sprint_id = options.get("sprint")
        analyze_all = options.get("all", False)

        if not any([project_id, sprint_id, analyze_all]):
            raise CommandError("Please specify --project, --sprint, or --all")

        anomaly_service = AnomalyDetectionService()

        try:
            if sprint_id:
                self._analyze_sprint(anomaly_service, sprint_id)
            elif project_id:
                self._analyze_project(anomaly_service, project_id)
            elif analyze_all:
                self._analyze_all_projects(anomaly_service)

        except Exception as e:
            logger.exception(f"Error detecting anomalies: {str(e)}")
            raise CommandError(f"Analysis failed: {str(e)}")

    def _analyze_sprint(self, service, sprint_id):
        """Analyze a specific sprint."""
        from apps.projects.models import Sprint

        try:
            sprint = Sprint.objects.get(id=sprint_id)
        except Sprint.DoesNotExist:
            raise CommandError(f"Sprint {sprint_id} not found")

        self.stdout.write(self.style.WARNING(f"\nAnalyzing Sprint: {sprint.name}\n"))

        risks = service.detect_sprint_risks(sprint_id)

        if not risks:
            self.stdout.write(self.style.SUCCESS("  ✓ No risks detected"))
            return

        self.stdout.write(self.style.WARNING(f"  Found {len(risks)} risk(s):\n"))

        for i, risk in enumerate(risks, 1):
            severity = risk["severity"].upper()
            if severity == "HIGH":
                severity_style = self.style.ERROR
            elif severity == "MEDIUM":
                severity_style = self.style.WARNING
            else:
                severity_style = self.style.NOTICE

            self.stdout.write(
                f"\n  {i}. {risk['risk_type']} " f"[{severity_style(severity)}]"
            )
            self.stdout.write(f"     {risk['description']}")

            if risk.get("mitigation_suggestions"):
                self.stdout.write("     Mitigation:")
                for suggestion in risk["mitigation_suggestions"]:
                    self.stdout.write(f"     - {suggestion}")

    def _analyze_project(self, service, project_id):
        """Analyze a specific project."""
        from apps.projects.models import Project

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise CommandError(f"Project {project_id} not found")

        self.stdout.write(
            self.style.WARNING(f"\nAnalyzing Project: {project.name} ({project.key})\n")
        )

        anomalies = service.detect_project_anomalies(project_id)

        if not anomalies:
            self.stdout.write(self.style.SUCCESS("  ✓ No anomalies detected"))
            return

        self.stdout.write(
            self.style.WARNING(f"  Found {len(anomalies)} anomaly/anomalies:\n")
        )

        for i, anomaly in enumerate(anomalies, 1):
            severity = anomaly["severity"].upper()
            if severity == "HIGH" or severity == "CRITICAL":
                severity_style = self.style.ERROR
            elif severity == "MEDIUM":
                severity_style = self.style.WARNING
            else:
                severity_style = self.style.NOTICE

            self.stdout.write(
                f"\n  {i}. {anomaly['anomaly_type']} " f"[{severity_style(severity)}]"
            )
            self.stdout.write(f"     {anomaly['description']}")

            if anomaly.get("possible_causes"):
                self.stdout.write("     Possible causes:")
                for cause in anomaly["possible_causes"]:
                    self.stdout.write(f"     - {cause}")

            if anomaly.get("mitigation_suggestions"):
                self.stdout.write("     Mitigation:")
                for suggestion in anomaly["mitigation_suggestions"]:
                    self.stdout.write(f"     - {suggestion}")

    def _analyze_all_projects(self, service):
        """Analyze all active projects."""
        from django.utils import timezone
        from datetime import timedelta
        from apps.projects.models import Project

        thirty_days_ago = timezone.now() - timedelta(days=30)
        projects = Project.objects.filter(
            is_active=True,
            updated_at__gte=thirty_days_ago,
        )

        self.stdout.write(
            self.style.WARNING(f"\nAnalyzing {projects.count()} active project(s)...\n")
        )

        total_anomalies = 0

        for project in projects:
            self.stdout.write(f"\n{project.name} ({project.key}):")

            try:
                anomalies = service.detect_project_anomalies(str(project.id))

                if not anomalies:
                    self.stdout.write(self.style.SUCCESS("  ✓ No anomalies"))
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚠ {len(anomalies)} anomaly/anomalies detected"
                        )
                    )
                    for anomaly in anomalies:
                        self.stdout.write(
                            f"    - {anomaly['anomaly_type']}: {anomaly['description']}"
                        )
                    total_anomalies += len(anomalies)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Error: {str(e)}"))

        self.stdout.write(f"\n{'-' * 60}\n")
        self.stdout.write(
            self.style.WARNING(f"Total anomalies detected: {total_anomalies}")
        )
