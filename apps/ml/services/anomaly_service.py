"""
Anomaly detection service for identifying unusual project patterns.

Detects velocity drops, excessive reassignments, and other risk indicators.
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from django.db import models
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from apps.ml.models import AnomalyDetection
from apps.projects.models import Issue, Sprint

logger = logging.getLogger(__name__)


class AnomalyDetectionService:
    """Service for detecting anomalous patterns in projects."""

    def detect_sprint_risks(self, sprint_id: str) -> List[Dict[str, Any]]:
        """
        Detect if a sprint is at risk of missing deadlines.

        Args:
            sprint_id: Sprint UUID

        Returns:
            List of detected risks with severity and mitigation suggestions
        """
        try:
            sprint = Sprint.objects.get(id=sprint_id)
            risks = []
            
            # 1. Check burndown velocity
            velocity_risk = self._check_burndown_velocity(sprint)
            if velocity_risk:
                risks.append(velocity_risk)
            
            # 2. Check blocked issues
            blocked_risk = self._check_blocked_issues(sprint)
            if blocked_risk:
                risks.append(blocked_risk)
            
            # 3. Check unestimated work
            estimation_risk = self._check_unestimated_work(sprint)
            if estimation_risk:
                risks.append(estimation_risk)
            
            # 4. Check scope changes
            scope_risk = self._check_scope_changes(sprint)
            if scope_risk:
                risks.append(scope_risk)
            
            # 5. Check team capacity
            capacity_risk = self._check_team_capacity(sprint)
            if capacity_risk:
                risks.append(capacity_risk)
            
            return risks
            
        except Exception as e:
            logger.exception(f"Error detecting sprint risks: {str(e)}")
            raise

    def detect_project_anomalies(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Detect anomalous patterns in a project.

        Args:
            project_id: Project UUID

        Returns:
            List of detected anomalies with analysis
        """
        try:
            anomalies = []
            
            # 1. Velocity trend analysis
            velocity_anomaly = self._detect_velocity_anomaly(project_id)
            if velocity_anomaly:
                anomalies.append(velocity_anomaly)
            
            # 2. Issue reassignment frequency
            reassignment_anomaly = self._detect_excessive_reassignments(project_id)
            if reassignment_anomaly:
                anomalies.append(reassignment_anomaly)
            
            # 3. Long-standing issues
            stale_issues_anomaly = self._detect_stale_issues(project_id)
            if stale_issues_anomaly:
                anomalies.append(stale_issues_anomaly)
            
            # 4. Unusual issue creation rate
            creation_anomaly = self._detect_unusual_creation_rate(project_id)
            if creation_anomaly:
                anomalies.append(creation_anomaly)
            
            # 5. Status transition bottlenecks
            bottleneck_anomaly = self._detect_status_bottlenecks(project_id)
            if bottleneck_anomaly:
                anomalies.append(bottleneck_anomaly)
            
            # Store detected anomalies in database
            for anomaly_data in anomalies:
                if anomaly_data["severity"] in ["high", "critical"]:
                    self._store_anomaly(project_id, anomaly_data)
            
            return anomalies
            
        except Exception as e:
            logger.exception(f"Error detecting project anomalies: {str(e)}")
            raise

    def _check_burndown_velocity(self, sprint: Sprint) -> Optional[Dict[str, Any]]:
        """Check if burndown velocity is below expected rate."""
        if sprint.status != "active" or not sprint.start_date:
            return None
        
        # Calculate days elapsed
        days_elapsed = (timezone.now().date() - sprint.start_date).days
        total_days = sprint.get_duration_days()
        
        if days_elapsed <= 0 or total_days <= 0:
            return None
        
        # Expected completion percentage
        expected_completion = days_elapsed / total_days
        
        # Actual completion (completed story points / total)
        total_points = sprint.issues.aggregate(
            total=Sum("story_points")
        )["total"] or 0
        
        completed_points = sprint.issues.filter(
            status__is_final=True
        ).aggregate(total=Sum("story_points"))["total"] or 0
        
        if total_points == 0:
            return None
        
        actual_completion = completed_points / total_points
        
        # Check if significantly behind
        if actual_completion < expected_completion - 0.2:  # 20% behind
            return {
                "risk_type": "burndown_velocity",
                "severity": "high" if actual_completion < expected_completion - 0.3 else "medium",
                "description": f"Sprint is {int((expected_completion - actual_completion) * 100)}% behind expected progress",
                "expected_completion": round(expected_completion * 100, 1),
                "actual_completion": round(actual_completion * 100, 1),
                "mitigation_suggestions": [
                    "Consider reducing sprint scope",
                    "Identify and remove blockers",
                    "Reassign work to available team members",
                ],
            }
        
        return None

    def _check_blocked_issues(self, sprint: Sprint) -> Optional[Dict[str, Any]]:
        """Check for excessive blocked issues."""
        total_issues = sprint.issues.count()
        if total_issues == 0:
            return None
        
        blocked_count = sprint.issues.filter(is_blocked=True).count()
        blocked_ratio = blocked_count / total_issues
        
        if blocked_ratio > 0.3:  # More than 30% blocked
            return {
                "risk_type": "blocked_issues",
                "severity": "high" if blocked_ratio > 0.5 else "medium",
                "description": f"{blocked_count} out of {total_issues} issues are blocked",
                "blocked_count": blocked_count,
                "total_count": total_issues,
                "mitigation_suggestions": [
                    "Review and resolve blockers immediately",
                    "Escalate external dependencies",
                    "Consider removing blocked items from sprint",
                ],
            }
        
        return None

    def _check_unestimated_work(self, sprint: Sprint) -> Optional[Dict[str, Any]]:
        """Check for unestimated issues in sprint."""
        total_issues = sprint.issues.count()
        if total_issues == 0:
            return None
        
        unestimated = sprint.issues.filter(
            Q(story_points__isnull=True) | Q(story_points=0)
        ).count()
        
        if unestimated > 0:
            return {
                "risk_type": "unestimated_work",
                "severity": "medium" if unestimated <= 3 else "high",
                "description": f"{unestimated} issues lack story point estimates",
                "unestimated_count": unestimated,
                "mitigation_suggestions": [
                    "Estimate all issues before sprint planning",
                    "Use planning poker for team consensus",
                ],
            }
        
        return None

    def _check_scope_changes(self, sprint: Sprint) -> Optional[Dict[str, Any]]:
        """Check for excessive scope changes during sprint."""
        if not sprint.start_date:
            return None
        
        # Count issues added after sprint start
        issues_added_after_start = sprint.issues.filter(
            created_at__gt=sprint.start_date
        ).count()
        
        total_issues = sprint.issues.count()
        
        if total_issues > 0 and issues_added_after_start / total_issues > 0.25:
            return {
                "risk_type": "scope_creep",
                "severity": "medium",
                "description": f"{issues_added_after_start} issues added after sprint started",
                "added_count": issues_added_after_start,
                "mitigation_suggestions": [
                    "Limit mid-sprint additions",
                    "Move new items to backlog",
                    "Discuss scope management in retrospective",
                ],
            }
        
        return None

    def _check_team_capacity(self, sprint: Sprint) -> Optional[Dict[str, Any]]:
        """Check if team capacity matches sprint workload."""
        # Get unique assignees
        assigned_users = sprint.issues.values("assignee").distinct().count()
        
        # Get team size
        team_size = sprint.project.team_members.filter(is_active=True).count()
        
        # Check if too many issues per person
        total_issues = sprint.issues.count()
        if assigned_users > 0:
            issues_per_person = total_issues / assigned_users
            
            if issues_per_person > 10:
                return {
                    "risk_type": "capacity_overload",
                    "severity": "high",
                    "description": f"Average of {int(issues_per_person)} issues per team member",
                    "issues_per_person": int(issues_per_person),
                    "mitigation_suggestions": [
                        "Reduce sprint scope",
                        "Add team members if possible",
                        "Identify and defer low-priority items",
                    ],
                }
        
        return None

    def _detect_velocity_anomaly(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Detect sudden velocity drops across sprints."""
        # Get last 5 completed sprints
        sprints = Sprint.objects.filter(
            project_id=project_id, status="completed"
        ).order_by("-created_at")[:5]
        
        if len(sprints) < 3:
            return None  # Need at least 3 sprints for trend
        
        # Calculate velocity for each sprint
        velocities = []
        for sprint in sprints:
            completed_points = sprint.issues.filter(
                status__is_final=True
            ).aggregate(total=Sum("story_points"))["total"] or 0
            velocities.append(completed_points)
        
        # Calculate statistics
        avg_velocity = np.mean(velocities)
        std_velocity = np.std(velocities)
        latest_velocity = velocities[0]
        
        # Detect if latest is significantly below average
        if std_velocity > 0:
            z_score = (latest_velocity - avg_velocity) / std_velocity
            
            if z_score < -1.5:  # More than 1.5 std deviations below
                return {
                    "anomaly_type": "velocity_drop",
                    "severity": "high" if z_score < -2 else "medium",
                    "description": f"Sprint velocity dropped to {latest_velocity} (avg: {avg_velocity:.1f})",
                    "current_velocity": latest_velocity,
                    "average_velocity": round(avg_velocity, 1),
                    "deviation_score": round(abs(z_score), 2),
                    "possible_causes": [
                        "Team capacity reduced",
                        "Increased issue complexity",
                        "External blockers or dependencies",
                    ],
                    "mitigation_suggestions": [
                        "Review sprint retrospectives for patterns",
                        "Check team availability and workload",
                        "Identify and address recurring blockers",
                    ],
                }
        
        return None

    def _detect_excessive_reassignments(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Detect if issues are being reassigned too frequently."""
        # This would require tracking assignment history
        # For now, placeholder implementation
        return None

    def _detect_stale_issues(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Detect issues that haven't been updated in a long time."""
        cutoff_date = timezone.now() - timedelta(days=30)
        
        stale_issues = Issue.objects.filter(
            project_id=project_id,
            status__is_final=False,
            is_active=True,
            updated_at__lt=cutoff_date,
        ).count()
        
        if stale_issues > 5:
            return {
                "anomaly_type": "stale_issues",
                "severity": "medium",
                "description": f"{stale_issues} issues haven't been updated in over 30 days",
                "stale_count": stale_issues,
                "possible_causes": [
                    "Issues abandoned or forgotten",
                    "Lack of clear ownership",
                    "Blocked without resolution",
                ],
                "mitigation_suggestions": [
                    "Review and close completed work",
                    "Reassign or re-prioritize stale issues",
                    "Update issue statuses",
                ],
            }
        
        return None

    def _detect_unusual_creation_rate(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Detect sudden spikes in issue creation."""
        # Compare last week to historical average
        last_week = timezone.now() - timedelta(days=7)
        last_month = timezone.now() - timedelta(days=30)
        
        recent_count = Issue.objects.filter(
            project_id=project_id, created_at__gte=last_week
        ).count()
        
        historical_count = Issue.objects.filter(
            project_id=project_id,
            created_at__gte=last_month,
            created_at__lt=last_week,
        ).count()
        
        avg_weekly = historical_count / 3  # Avg over 3 weeks
        
        if avg_weekly > 0 and recent_count > avg_weekly * 2:
            return {
                "anomaly_type": "creation_spike",
                "severity": "medium",
                "description": f"Issue creation rate doubled: {recent_count} this week vs {avg_weekly:.0f} avg",
                "recent_count": recent_count,
                "average_count": round(avg_weekly, 1),
                "possible_causes": [
                    "New feature development started",
                    "Bug discovery after release",
                    "Scope expansion",
                ],
                "mitigation_suggestions": [
                    "Review and prioritize new issues",
                    "Ensure adequate team capacity",
                    "Consider impact on current sprint",
                ],
            }
        
        return None

    def _detect_status_bottlenecks(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Detect if too many issues are stuck in one status."""
        # Get all non-final statuses
        from apps.projects.models import WorkflowStatus
        
        statuses = WorkflowStatus.objects.filter(
            project_id=project_id, is_final=False
        )
        
        total_open = Issue.objects.filter(
            project_id=project_id, status__is_final=False, is_active=True
        ).count()
        
        if total_open == 0:
            return None
        
        # Check each status for concentration
        for status in statuses:
            count_in_status = Issue.objects.filter(
                project_id=project_id, status=status, is_active=True
            ).count()
            
            ratio = count_in_status / total_open
            
            if ratio > 0.5:  # More than 50% in one status
                return {
                    "anomaly_type": "status_bottleneck",
                    "severity": "medium",
                    "description": f"{count_in_status} issues stuck in '{status.name}' status",
                    "status_name": status.name,
                    "count_in_status": count_in_status,
                    "total_open": total_open,
                    "possible_causes": [
                        "Process bottleneck",
                        "Resource constraint",
                        "Dependencies or blockers",
                    ],
                    "mitigation_suggestions": [
                        "Review workflow efficiency",
                        "Identify blockers in this stage",
                        "Consider adding resources",
                    ],
                }
        
        return None

    def _store_anomaly(self, project_id: str, anomaly_data: Dict[str, Any]):
        """Store anomaly detection in database."""
        try:
            AnomalyDetection.objects.create(
                project_id=project_id,
                anomaly_type=anomaly_data["anomaly_type"],
                severity=anomaly_data["severity"],
                affected_metric=anomaly_data.get("description", ""),
                actual_value=anomaly_data.get("current_velocity", 0),
                deviation_score=anomaly_data.get("deviation_score", 0),
                description=anomaly_data["description"],
                possible_causes=anomaly_data.get("possible_causes", []),
                mitigation_suggestions=anomaly_data.get("mitigation_suggestions", []),
            )
            logger.info(f"Stored {anomaly_data['severity']} anomaly for project {project_id}")
        except Exception as e:
            logger.exception(f"Error storing anomaly: {str(e)}")
