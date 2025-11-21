"""
Recommendation service for task assignment suggestions.

Provides intelligent assignment recommendations based on skills,
workload, and past performance.
"""

import logging
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.db.models import (
    Avg,
    Count,
    DurationField,
    ExpressionWrapper,
    F,
    Q,
)
from django.utils import timezone

from apps.projects.models import Issue, ProjectTeamMember

User = get_user_model()
logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for assignment and resource recommendations."""

    def suggest_task_assignment(
        self, issue_id: str, project_id: str, top_n: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Suggest best team members for an issue.

        Args:
            issue_id: Issue UUID
            project_id: Project UUID
            top_n: Number of suggestions to return

        Returns:
            List of user recommendations with scores and reasoning
        """
        try:
            issue = Issue.objects.select_related("issue_type").get(id=issue_id)

            # Pre-calculate issue stats for ALL users in ONE query
            user_stats = self._precalculate_user_stats(project_id, issue)

            # Get all active team members with pre-loaded data
            team_members = ProjectTeamMember.objects.filter(
                project_id=project_id, is_active=True
            ).select_related("user")

            if not team_members:
                return []

            # Score each team member using pre-calculated stats
            scored_members = []
            for member in team_members:
                stats = user_stats.get(member.user.id, {})
                score_data = self._calculate_assignment_score_optimized(
                    member.user, issue, stats
                )
                scored_members.append(score_data)

            # Sort by total score
            scored_members.sort(key=lambda x: x["total_score"], reverse=True)

            return scored_members[:top_n]

        except Exception as e:
            logger.exception(f"Error suggesting task assignment: {str(e)}")
            raise

    def _precalculate_user_stats(
        self, project_id: str, issue: Issue
    ) -> Dict[str, Dict[str, Any]]:
        """
        Pre-calculate ALL user stats in ONE query to avoid N+1.

        Returns dict: {user_id: {stats}}
        """
        seven_days_ago = timezone.now() - timezone.timedelta(days=7)

        # Get all users with their stats in ONE query
        user_stats_qs = (
            User.objects.filter(
                project_memberships__project_id=project_id,
                project_memberships__is_active=True,
            )
            .distinct()
            .annotate(
                # Skill scores
                same_type_completed=Count(
                    "assigned_issues",
                    filter=Q(
                        assigned_issues__project_id=project_id,
                        assigned_issues__issue_type=issue.issue_type,
                        assigned_issues__status__is_final=True,
                    ),
                    distinct=True,
                ),
                total_completed=Count(
                    "assigned_issues",
                    filter=Q(
                        assigned_issues__project_id=project_id,
                        assigned_issues__status__is_final=True,
                    ),
                    distinct=True,
                ),
                # Workload
                active_issues_count=Count(
                    "assigned_issues",
                    filter=Q(
                        assigned_issues__project_id=project_id,
                        assigned_issues__status__is_final=False,
                        assigned_issues__is_active=True,
                    ),
                    distinct=True,
                ),
                # Performance
                total_assigned=Count(
                    "assigned_issues",
                    filter=Q(assigned_issues__project_id=project_id),
                    distinct=True,
                ),
                completed_count=Count(
                    "assigned_issues",
                    filter=Q(
                        assigned_issues__project_id=project_id,
                        assigned_issues__status__is_final=True,
                    ),
                    distinct=True,
                ),
                # Availability
                recent_updates=Count(
                    "assigned_issues",
                    filter=Q(
                        assigned_issues__updated_at__gte=seven_days_ago,
                    ),
                    distinct=True,
                ),
            )
            .values(
                "id",
                "same_type_completed",
                "total_completed",
                "active_issues_count",
                "total_assigned",
                "completed_count",
                "recent_updates",
            )
        )

        # Convert to dict for fast lookup (use UUID as key, not string)
        stats_dict = {stat["id"]: stat for stat in user_stats_qs}

        # Get avg resolution time separately (more complex aggregation)
        avg_resolution_qs = (
            Issue.objects.filter(
                project_id=project_id,
                status__is_final=True,
                resolved_at__isnull=False,
            )
            .values("assignee_id")
            .annotate(
                avg_resolution=Avg(
                    ExpressionWrapper(
                        F("resolved_at") - F("created_at"),
                        output_field=DurationField(),
                    )
                )
            )
        )

        for res in avg_resolution_qs:
            user_id = res["assignee_id"]
            if user_id in stats_dict:
                stats_dict[user_id]["avg_resolution"] = res["avg_resolution"]

        return stats_dict

    def _calculate_assignment_score_optimized(
        self, user: User, issue: Issue, stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate assignment score using pre-calculated stats.

        NO database queries here - all data from stats dict.
        """
        # 1. Skill score
        total_completed = stats.get("total_completed", 0)
        same_type_completed = stats.get("same_type_completed", 0)

        if total_completed == 0:
            skill_score = 0.3
        else:
            type_ratio = same_type_completed / total_completed
            skill_score = min(type_ratio * 2, 1.0)

        # 2. Workload score
        active_issues = stats.get("active_issues_count", 0)

        if active_issues == 0:
            workload_score = 1.0
        elif active_issues <= 3:
            workload_score = 0.8
        elif active_issues <= 6:
            workload_score = 0.5
        elif active_issues <= 10:
            workload_score = 0.3
        else:
            workload_score = 0.1

        # 3. Performance score
        total_assigned = stats.get("total_assigned", 0)
        completed_count = stats.get("completed_count", 0)

        if total_assigned == 0:
            performance_score = 0.5
        else:
            completion_rate = completed_count / total_assigned
            performance_score = completion_rate

            # Bonus for fast resolution
            avg_resolution = stats.get("avg_resolution")
            if avg_resolution:
                avg_days = avg_resolution.days if avg_resolution.days > 0 else 1
                if avg_days < 7:
                    performance_score = min(completion_rate * 1.2, 1.0)

        # 4. Availability score
        recent_updates = stats.get("recent_updates", 0)

        if recent_updates >= 5:
            availability_score = 1.0
        elif recent_updates >= 3:
            availability_score = 0.8
        elif recent_updates >= 1:
            availability_score = 0.6
        else:
            availability_score = 0.4

        # Weighted total
        total_score = (
            skill_score * 0.4
            + workload_score * 0.3
            + performance_score * 0.2
            + availability_score * 0.1
        )

        # Generate reasoning
        reasoning = []
        if skill_score > 0.7:
            reasoning.append(f"Strong experience with {issue.issue_type.name} issues")
        if workload_score > 0.7:
            reasoning.append("Currently has capacity")
        if performance_score > 0.7:
            reasoning.append("High success rate on similar issues")
        if skill_score < 0.3:
            reasoning.append("Limited experience with this issue type")
        if workload_score < 0.3:
            reasoning.append("Currently at high workload")

        return {
            "user_id": str(user.id),
            "user_name": user.get_full_name() or user.username,
            "user_email": user.email,
            "total_score": round(total_score, 2),
            "skill_score": round(skill_score, 2),
            "workload_score": round(workload_score, 2),
            "performance_score": round(performance_score, 2),
            "availability_score": round(availability_score, 2),
            "reasoning": reasoning,
        }

    def _calculate_assignment_score(
        self, user: User, issue: Issue, project_id: str
    ) -> Dict[str, Any]:
        """
        Calculate assignment score for a user.

        Scoring components:
        - Skill match (40%): Experience with issue type
        - Workload (30%): Current workload balance
        - Performance (20%): Success rate on similar issues
        - Availability (10%): Recent activity
        """
        # 1. Skill match score (0-1)
        skill_score = self._calculate_skill_score(user, issue, project_id)

        # 2. Workload score (0-1)
        workload_score = self._calculate_workload_score(user, project_id)

        # 3. Performance score (0-1)
        performance_score = self._calculate_performance_score(user, issue, project_id)

        # 4. Availability score (0-1)
        availability_score = self._calculate_availability_score(user)

        # Weighted total
        total_score = (
            skill_score * 0.4
            + workload_score * 0.3
            + performance_score * 0.2
            + availability_score * 0.1
        )

        # Generate reasoning
        reasoning = []
        if skill_score > 0.7:
            reasoning.append(f"Strong experience with {issue.issue_type.name} issues")
        if workload_score > 0.7:
            reasoning.append("Currently has capacity")
        if performance_score > 0.7:
            reasoning.append("High success rate on similar issues")
        if skill_score < 0.3:
            reasoning.append("Limited experience with this issue type")
        if workload_score < 0.3:
            reasoning.append("Currently at high workload")

        return {
            "user_id": str(user.id),
            "user_name": user.get_full_name() or user.username,
            "user_email": user.email,
            "total_score": round(total_score, 2),
            "skill_score": round(skill_score, 2),
            "workload_score": round(workload_score, 2),
            "performance_score": round(performance_score, 2),
            "availability_score": round(availability_score, 2),
            "reasoning": reasoning,
        }

    def _calculate_skill_score(
        self, user: User, issue: Issue, project_id: str
    ) -> float:
        """Calculate skill match score based on past experience."""
        # Count issues of same type completed by user
        same_type_completed = Issue.objects.filter(
            project_id=project_id,
            assignee=user,
            issue_type=issue.issue_type,
            status__is_final=True,
        ).count()

        # Total completed issues by user in project
        total_completed = Issue.objects.filter(
            project_id=project_id, assignee=user, status__is_final=True
        ).count()

        if total_completed == 0:
            return 0.3  # New team member baseline

        # Ratio of experience with this type
        type_ratio = same_type_completed / total_completed

        # Normalize to 0-1 score
        score = min(type_ratio * 2, 1.0)  # 50% experience = full score

        return score

    def _calculate_workload_score(self, user: User, project_id: str) -> float:
        """Calculate workload score (inverse of current workload)."""
        # Count active assigned issues
        active_issues = Issue.objects.filter(
            project_id=project_id,
            assignee=user,
            status__is_final=False,
            is_active=True,
        ).count()

        # Inverse scoring (fewer issues = higher score)
        if active_issues == 0:
            return 1.0
        elif active_issues <= 3:
            return 0.8
        elif active_issues <= 6:
            return 0.5
        elif active_issues <= 10:
            return 0.3
        else:
            return 0.1

    def _calculate_performance_score(
        self, user: User, issue: Issue, project_id: str
    ) -> float:
        """Calculate performance score based on completion rate."""
        # Get user's completed vs total assigned issues
        assigned_issues = Issue.objects.filter(
            project_id=project_id, assignee=user
        ).count()

        if assigned_issues == 0:
            return 0.5  # Neutral score for new members

        completed_issues = Issue.objects.filter(
            project_id=project_id, assignee=user, status__is_final=True
        ).count()

        completion_rate = completed_issues / assigned_issues

        # Check average resolution time (in days)
        avg_resolution = (
            Issue.objects.filter(
                project_id=project_id,
                assignee=user,
                status__is_final=True,
                resolved_at__isnull=False,
            )
            .annotate(
                resolution_time=ExpressionWrapper(
                    F("resolved_at") - F("created_at"), output_field=DurationField()
                )
            )
            .aggregate(avg_time=Avg("resolution_time"))["avg_time"]
        )

        # Combine completion rate with speed
        # Bonus for fast resolution (if avg < 7 days)
        performance = completion_rate
        if avg_resolution:
            avg_days = avg_resolution.days if avg_resolution.days > 0 else 1
            if avg_days < 7:
                performance = min(completion_rate * 1.2, 1.0)  # 20% bonus

        return min(performance, 1.0)

    def _calculate_availability_score(self, user: User) -> float:
        """Calculate availability score based on recent activity."""
        # Check recent issue updates
        recent_updates = Issue.objects.filter(
            assignee=user,
            updated_at__gte=timezone.now() - timezone.timedelta(days=7),
        ).count()

        # More recent activity = higher availability
        if recent_updates >= 5:
            return 1.0
        elif recent_updates >= 3:
            return 0.8
        elif recent_updates >= 1:
            return 0.6
        else:
            return 0.4  # Less active recently

    def recommend_sprint_team(
        self, sprint_id: str, required_skills: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Recommend optimal team composition for a sprint.

        Args:
            sprint_id: Sprint UUID
            required_skills: List of required skill areas

        Returns:
            Recommended team members with role assignments
        """
        # TODO: Implement team composition recommendation
        # This would analyze sprint scope and recommend balanced team
        return []

    def suggest_issue_prioritization(
        self, project_id: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Suggest which issues should be prioritized next.

        Args:
            project_id: Project UUID
            max_results: Maximum number of recommendations

        Returns:
            List of prioritized issues with reasoning
        """
        try:
            # Get open issues
            open_issues = Issue.objects.filter(
                project_id=project_id,
                status__is_final=False,
                is_active=True,
            ).select_related("issue_type", "status", "assignee")

            scored_issues = []
            for issue in open_issues:
                priority_score = self._calculate_priority_score(issue)
                scored_issues.append(
                    {
                        "issue_id": str(issue.id),
                        "title": issue.title,
                        "priority_score": priority_score["score"],
                        "reasoning": priority_score["reasoning"],
                    }
                )

            # Sort by priority score
            scored_issues.sort(key=lambda x: x["priority_score"], reverse=True)

            return scored_issues[:max_results]

        except Exception as e:
            logger.exception(f"Error suggesting issue prioritization: {str(e)}")
            raise

    def _calculate_priority_score(self, issue: Issue) -> Dict[str, Any]:
        """Calculate priority score for an issue."""
        score = 0.0
        reasoning = []

        # Age factor
        age_days = (timezone.now() - issue.created_at).days
        if age_days > 30:
            score += 0.3
            reasoning.append("Issue has been open for over 30 days")
        elif age_days > 14:
            score += 0.2
            reasoning.append("Issue has been open for over 2 weeks")

        # Priority factor
        priority_scores = {"P0": 0.5, "P1": 0.4, "P2": 0.2, "P3": 0.1}
        if issue.priority in priority_scores:
            score += priority_scores[issue.priority]
            if issue.priority in ["P0", "P1"]:
                reasoning.append(f"High priority ({issue.priority})")

        # Blocker factor
        if issue.is_blocked:
            score += 0.2
            reasoning.append("Issue is currently blocked")

        # Unassigned factor
        if not issue.assignee:
            score += 0.1
            reasoning.append("Issue is unassigned")

        return {"score": round(score, 2), "reasoning": reasoning}
