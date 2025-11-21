import csv
import logging
from datetime import timedelta
from typing import Dict, List

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self):
        pass

    def generate_velocity_chart(self, project, num_sprints: int = 5) -> Dict:
        from apps.projects.models import Sprint

        logger.info(
            f"[VELOCITY] Generating velocity chart for project {project.id} ({project.key})"  # noqa: E501
        )

        # Include active, completed, and closed sprints for better coverage
        sprints = Sprint.objects.filter(
            project=project, status__in=["active", "completed", "closed"]
        ).order_by("-end_date")[:num_sprints]

        logger.info(
            f"[VELOCITY] Found {sprints.count()} sprints with status active/completed/closed"  # noqa: E501
        )

        chart_data = {"labels": [], "velocities": [], "planned_points": []}

        # Handle empty sprint list early
        if not sprints.exists():
            logger.warning("[VELOCITY] No sprints found - returning empty chart")
            chart_data["average_velocity"] = 0.0
            return chart_data

        total_velocity = 0
        for sprint in reversed(list(sprints)):
            logger.debug(
                f"[VELOCITY] Processing sprint: {sprint.name} (status={sprint.status})"
            )

            # Count all issues in sprint
            all_sprint_issues = sprint.issues.filter(is_active=True)
            logger.debug(
                f"[VELOCITY]   Total active issues in sprint: {all_sprint_issues.count()}"  # noqa: E501
            )

            # Count done issues (support both 'done' and potential variants)
            done_issues = sprint.issues.filter(
                Q(status__category="done") | Q(status__category__iexact="done"),
                is_active=True,
            ).distinct()
            logger.debug(f"[VELOCITY]   Done issues: {done_issues.count()}")

            # Calculate points
            completed_points = done_issues.aggregate(
                total=Coalesce(Sum("story_points"), 0)
            )["total"]
            logger.debug(f"[VELOCITY]   Completed points: {completed_points}")

            planned_points = all_sprint_issues.aggregate(
                total=Coalesce(Sum("story_points"), 0)
            )["total"]
            logger.debug(f"[VELOCITY]   Planned points: {planned_points}")

            chart_data["labels"].append(sprint.name)
            chart_data["velocities"].append(completed_points)
            chart_data["planned_points"].append(planned_points)
            total_velocity += completed_points

        chart_data["average_velocity"] = (
            round(total_velocity / len(sprints), 2) if sprints else 0
        )

        logger.info(
            f"[VELOCITY] Chart generated: labels={chart_data['labels']}, "
            f"velocities={chart_data['velocities']}, "
            f"planned={chart_data['planned_points']}, "
            f"avg={chart_data['average_velocity']}"
        )

        return chart_data

    def generate_sprint_report(self, sprint) -> Dict:
        from apps.projects.models import Issue

        issues = Issue.objects.filter(sprint=sprint, is_active=True)

        completed_issues = issues.filter(status__category="done")
        incomplete_issues = issues.exclude(status__category="done")

        completed_points = completed_issues.aggregate(
            total=Coalesce(Sum("story_points"), 0)
        )["total"]
        planned_points = issues.aggregate(total=Coalesce(Sum("story_points"), 0))[
            "total"
        ]

        completion_rate = (
            round((completed_points / planned_points) * 100, 2) if planned_points else 0
        )

        report = {
            "sprint": {
                "id": str(sprint.id),
                "name": sprint.name,
                "status": sprint.status,
                "start_date": str(sprint.start_date) if sprint.start_date else None,
                "end_date": str(sprint.end_date) if sprint.end_date else None,
            },
            "metrics": {
                "planned_points": planned_points,
                "completed_points": completed_points,
                "completion_rate": completion_rate,
                "total_issues": issues.count(),
                "completed_issues": completed_issues.count(),
                "incomplete_issues": incomplete_issues.count(),
                "velocity": completed_points,
            },
            "issues_by_status": self._get_issues_by_status(issues),
            "issues_by_type": self._get_issues_by_type(issues),
            "defect_rate": self._calculate_defect_rate(issues),
        }

        return report

    def generate_team_metrics(self, project, period: int = 30) -> Dict:
        from collections import defaultdict

        from apps.projects.models import Issue

        start_date = timezone.now() - timedelta(days=period)

        # Load ALL issues ONCE with select_related to avoid N queries
        all_issues = list(
            Issue.objects.filter(
                project=project, is_active=True, created_at__gte=start_date
            ).select_related("status", "assignee")
        )

        # Load team members ONCE
        team_members = list(
            project.team_members.filter(is_active=True).select_related("user")
        )

        # Group issues by assignee in memory
        issues_by_user = defaultdict(list)
        for issue in all_issues:
            if issue.assignee:
                issues_by_user[issue.assignee.id].append(issue)

        user_metrics = []
        for member in team_members:
            user_issues = issues_by_user.get(member.user.id, [])
            completed_issues = [i for i in user_issues if i.status.category == "done"]

            # Calculate metrics from in-memory list
            avg_resolution_time = self._calculate_avg_resolution_time_from_list(
                completed_issues
            )
            story_points_total = sum(i.story_points or 0 for i in completed_issues)

            user_metrics.append(
                {
                    "user": {
                        "id": str(member.user.id),
                        "email": member.user.email,
                        "name": member.user.get_full_name() or member.user.email,
                    },
                    "issues_assigned": len(user_issues),
                    "issues_completed": len(completed_issues),
                    "avg_resolution_time_hours": avg_resolution_time,
                    "story_points_completed": story_points_total,
                }
            )

        # Calculate team aggregates from in-memory list
        completed_issues_total = [i for i in all_issues if i.status.category == "done"]
        in_progress_issues = [
            i for i in all_issues if i.status.category == "in_progress"
        ]

        team_aggregates = {
            "total_issues": len(all_issues),
            "total_completed": len(completed_issues_total),
            "throughput": self._calculate_throughput_from_list(all_issues, period),
            "avg_cycle_time": self._calculate_avg_cycle_time_from_list(all_issues),
            "work_in_progress": len(in_progress_issues),
        }

        return {"user_metrics": user_metrics, "team_aggregates": team_aggregates}

    def generate_cumulative_flow_diagram(self, project, days: int = 30) -> Dict:
        from collections import defaultdict

        from apps.projects.models import Issue

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # Load statuses from project workflow
        statuses = list(project.workflow_statuses.all().order_by('order'))

        # If no workflow statuses configured, get statuses from actual issues
        if not statuses:
            from apps.projects.models import WorkflowStatus

            issue_status_ids = (
                Issue.objects.filter(project=project, is_active=True)
                .values_list("status_id", flat=True)
                .distinct()
            )
            statuses = list(
                WorkflowStatus.objects.filter(id__in=issue_status_ids).order_by('order')
            )

        if not statuses:
            return {"dates": [], "status_counts": {}}

        # Load ALL relevant issues ONCE with select_related
        # Use __date__lte to properly compare datetime field with date object
        all_issues = (
            Issue.objects.filter(
                project=project,
                is_active=True,
                created_at__date__lte=end_date,
            )
            .select_related("status")
            .values("id", "status_id", "created_at")
        )

        # Build issue-to-status mapping and creation dates
        issue_data = {}
        for issue in all_issues:
            issue_data[issue["id"]] = {
                "status_id": issue["status_id"],
                "created_date": issue["created_at"].date(),
            }

        cfd_data = {"dates": [], "status_counts": {}}

        for status in statuses:
            cfd_data["status_counts"][status.name] = []

        # Calculate counts in Python (memory) instead of 150 DB queries
        current_date = start_date
        while current_date <= end_date:
            cfd_data["dates"].append(str(current_date))

            # Count issues per status for this date (in memory)
            status_counts = defaultdict(int)
            for issue_id, data in issue_data.items():
                if data["created_date"] <= current_date:
                    status_counts[data["status_id"]] += 1

            # Append counts to each status
            for status in statuses:
                count = status_counts.get(status.id, 0)
                cfd_data["status_counts"][status.name].append(count)

            current_date += timedelta(days=1)

        return cfd_data

    def export_to_csv(self, project, data_type: str, filters: Dict) -> str:
        import io

        from apps.projects.models import Issue, Sprint
        from apps.reporting.models import ActivityLog

        output = io.StringIO()
        writer = csv.writer(output)

        if data_type == "issues":
            issues = Issue.objects.filter(project=project, is_active=True)

            # Apply filters
            if filters.get("sprint"):
                issues = issues.filter(sprint_id=filters["sprint"])
            if filters.get("status"):
                issues = issues.filter(status_id=filters["status"])
            if filters.get("assignee"):
                issues = issues.filter(assignee_id=filters["assignee"])
            if filters.get("issue_type"):
                issues = issues.filter(issue_type_id=filters["issue_type"])
            if filters.get("priority"):
                issues = issues.filter(priority=filters["priority"])

            # Date range filters
            if filters.get("start_date"):
                issues = issues.filter(created_at__date__gte=filters["start_date"])
            if filters.get("end_date"):
                issues = issues.filter(created_at__date__lte=filters["end_date"])

            writer.writerow(
                [
                    "Key",
                    "Title",
                    "Type",
                    "Status",
                    "Priority",
                    "Assignee",
                    "Reporter",
                    "Story Points",
                    "Sprint",
                    "Created At",
                    "Resolved At",
                ]
            )

            for issue in issues:
                writer.writerow(
                    [
                        issue.key,
                        issue.title,
                        issue.issue_type.name,
                        issue.status.name,
                        issue.get_priority_display(),
                        issue.assignee.email if issue.assignee else "",
                        issue.reporter.email if issue.reporter else "",
                        issue.story_points or 0,
                        issue.sprint.name if issue.sprint else "",
                        issue.created_at.date(),
                        issue.resolved_at.date() if issue.resolved_at else "",
                    ]
                )

        elif data_type == "sprints":
            sprints = Sprint.objects.filter(project=project)

            # Date range filters
            if filters.get("start_date"):
                sprints = sprints.filter(start_date__gte=filters["start_date"])
            if filters.get("end_date"):
                sprints = sprints.filter(end_date__lte=filters["end_date"])

            writer.writerow(
                [
                    "Name",
                    "Status",
                    "Start Date",
                    "End Date",
                    "Goal",
                    "Planned Points",
                    "Completed Points",
                    "Completion Rate",
                ]
            )

            for sprint in sprints:
                total_points = sprint.issues.filter(is_active=True).aggregate(
                    total=Coalesce(Sum("story_points"), 0)
                )["total"]
                completed_points = sprint.issues.filter(
                    status__category="done", is_active=True
                ).aggregate(total=Coalesce(Sum("story_points"), 0))["total"]
                completion_rate = (
                    round((completed_points / total_points) * 100, 1)
                    if total_points
                    else 0
                )

                writer.writerow(
                    [
                        sprint.name,
                        sprint.status,
                        sprint.start_date or "",
                        sprint.end_date or "",
                        sprint.goal or "",
                        total_points,
                        completed_points,
                        f"{completion_rate}%",
                    ]
                )

        elif data_type == "activity":
            # Export activity logs
            activities = ActivityLog.objects.filter(project=project)

            # Apply filters
            if filters.get("user"):
                activities = activities.filter(user_id=filters["user"])
            if filters.get("action_type"):
                activities = activities.filter(action_type=filters["action_type"])

            # Date range filters
            if filters.get("start_date"):
                activities = activities.filter(
                    created_at__date__gte=filters["start_date"]
                )
            if filters.get("end_date"):
                activities = activities.filter(
                    created_at__date__lte=filters["end_date"]
                )

            # Order by most recent
            activities = activities.order_by("-created_at")

            writer.writerow(
                [
                    "Date",
                    "Time",
                    "User",
                    "Action",
                    "Object Type",
                    "Object",
                    "IP Address",
                ]
            )

            for activity in activities:
                writer.writerow(
                    [
                        activity.created_at.date(),
                        activity.created_at.time().strftime("%H:%M:%S"),
                        activity.user.email,
                        activity.get_action_type_display(),
                        activity.content_type.model if activity.content_type else "",
                        activity.object_repr,
                        activity.ip_address or "",
                    ]
                )

        return output.getvalue()

    def generate_project_dashboard(self, project) -> Dict:
        from apps.projects.models import Issue, Sprint

        active_sprint = Sprint.objects.filter(project=project, status="active").first()

        total_issues = Issue.objects.filter(project=project, is_active=True).count()
        completed_issues = Issue.objects.filter(
            project=project, is_active=True, status__category="done"
        ).count()

        completion_rate = (
            round((completed_issues / total_issues) * 100, 2) if total_issues else 0
        )

        recent_activity = self._get_recent_activity(project, limit=10)

        dashboard = {
            "project": {
                "id": str(project.id),
                "name": project.name,
                "key": project.key,
                "status": project.status,
            },
            "summary_stats": {
                "total_issues": total_issues,
                "completed_issues": completed_issues,
                "completion_rate": completion_rate,
                "active_sprint": active_sprint.name if active_sprint else None,
                "team_size": project.team_members.filter(is_active=True).count(),
            },
            "active_sprint_summary": (
                self._get_sprint_summary(active_sprint) if active_sprint else None
            ),
            "recent_activity": recent_activity,
            "issue_breakdown": self._get_issue_breakdown(project),
        }

        return dashboard

    def _get_issues_by_status(self, issues) -> Dict:
        status_counts = (
            issues.values("status__name").annotate(count=Count("id")).order_by("-count")
        )
        return {item["status__name"]: item["count"] for item in status_counts}

    def _get_issues_by_type(self, issues) -> Dict:
        type_counts = (
            issues.values("issue_type__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return {item["issue_type__name"]: item["count"] for item in type_counts}

    def _calculate_defect_rate(self, issues) -> float:
        total = issues.count()
        if total == 0:
            return 0.0
        bugs = issues.filter(issue_type__category="bug").count()
        return round((bugs / total) * 100, 2)

    def _calculate_avg_resolution_time(self, issues) -> float:
        resolved = issues.filter(resolved_at__isnull=False)
        if not resolved.exists():
            return 0.0

        total_hours = 0
        count = 0
        for issue in resolved:
            time_diff = (issue.resolved_at - issue.created_at).total_seconds()
            if time_diff >= 0:
                total_hours += time_diff / 3600
                count += 1

        return round(total_hours / count, 2) if count > 0 else 0.0

    def _calculate_avg_resolution_time_from_list(self, issues_list) -> float:
        """Calculate avg resolution time from in-memory list (optimized)."""
        resolved = [i for i in issues_list if i.resolved_at is not None]
        if not resolved:
            return 0.0

        total_hours = 0
        valid_count = 0
        for issue in resolved:
            time_diff = (issue.resolved_at - issue.created_at).total_seconds()
            if time_diff >= 0:
                total_hours += time_diff / 3600
                valid_count += 1

        return round(total_hours / valid_count, 2) if valid_count > 0 else 0.0

    def _calculate_throughput(self, issues, period: int) -> float:
        completed = issues.filter(status__category="done").count()
        return round(completed / period, 2)

    def _calculate_throughput_from_list(self, issues_list, period: int) -> float:
        """Calculate throughput from in-memory list (optimized)."""
        completed = sum(1 for i in issues_list if i.status.category == "done")
        return round(completed / period, 2)

    def _calculate_avg_cycle_time(self, issues) -> float:
        return self._calculate_avg_resolution_time(
            issues.filter(status__category="done")
        )

    def _calculate_avg_cycle_time_from_list(self, issues_list) -> float:
        """Calculate avg cycle time from in-memory list (optimized)."""
        completed = [i for i in issues_list if i.status.category == "done"]
        return self._calculate_avg_resolution_time_from_list(completed)

    def _get_recent_activity(self, project, limit: int = 10) -> List[Dict]:
        from apps.reporting.models import ActivityLog

        activities = ActivityLog.objects.filter(project=project).order_by(
            "-created_at"
        )[:limit]

        return [
            {
                "id": str(activity.id),
                "user": activity.user.email,
                "action": activity.formatted_action,
                "time_ago": activity.time_ago,
                "created_at": str(activity.created_at),
            }
            for activity in activities
        ]

    def _get_sprint_summary(self, sprint) -> Dict:
        from apps.projects.models import Issue

        issues = Issue.objects.filter(sprint=sprint, is_active=True)
        completed = issues.filter(status__category="done")

        return {
            "name": sprint.name,
            "total_issues": issues.count(),
            "completed_issues": completed.count(),
            "story_points": issues.aggregate(total=Coalesce(Sum("story_points"), 0))[
                "total"
            ],
            "completed_points": completed.aggregate(
                total=Coalesce(Sum("story_points"), 0)
            )["total"],
        }

    def _get_issue_breakdown(self, project) -> Dict:
        from apps.projects.models import Issue

        issues = Issue.objects.filter(project=project, is_active=True)

        return {
            "by_priority": {
                priority[0]: issues.filter(priority=priority[0]).count()
                for priority in Issue.PRIORITY_CHOICES
            },
            "by_type": dict(
                issues.values("issue_type__name")
                .annotate(count=Count("id"))
                .values_list("issue_type__name", "count")
            ),
        }
