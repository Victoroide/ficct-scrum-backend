"""
Summarization service for generating AI-powered summaries.

Generates summaries for issues, sprints, and projects.
"""

import hashlib
import logging
from typing import Any, Dict, Optional

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.ai_assistant.models import SummaryCache
from apps.projects.models import Issue, Sprint
from base.services import get_azure_openai_service

logger = logging.getLogger(__name__)


class SummarizationService:
    """Service for AI-powered summarization."""

    def __init__(self):
        """Initialize with Azure OpenAI."""
        self.openai = get_azure_openai_service()

    def summarize_issue_discussion(
        self, issue_id: str, length: str = "medium", use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Summarize issue comments and discussion.

        Args:
            issue_id: Issue UUID
            length: Summary length (brief, medium, detailed)
            use_cache: Use cached summary if available

        Returns:
            Dictionary with summary text and metadata
        """
        try:
            issue = Issue.objects.prefetch_related("comments").get(id=issue_id)
            
            # Check cache first
            if use_cache:
                cached = self._get_cached_summary(
                    issue, "issue_discussion", length
                )
                if cached:
                    return {"summary": cached.summary_text, "cached": True}
            
            # Get all comments
            comments = issue.comments.select_related("user").order_by("created_at")
            
            if not comments.exists():
                return {
                    "summary": "No discussion yet for this issue.",
                    "cached": False,
                }
            
            # Build discussion text
            discussion_text = f"Issue: {issue.title}\n\n"
            for comment in comments:
                user_name = comment.user.get_full_name() or comment.user.username
                discussion_text += f"{user_name}: {comment.content}\n\n"
            
            # Generate summary
            word_limits = {"brief": 50, "medium": 150, "detailed": 300}
            max_words = word_limits.get(length, 150)
            
            summary = self._generate_summary(
                discussion_text,
                f"Summarize this issue discussion in {max_words} words or less. "
                "Focus on key points, decisions made, and action items.",
            )
            
            # Cache the summary
            self._cache_summary(
                issue, "issue_discussion", length, summary, discussion_text
            )
            
            return {"summary": summary, "cached": False}
            
        except Exception as e:
            logger.exception(f"Error summarizing issue discussion: {str(e)}")
            raise

    def summarize_sprint_retrospective(
        self, sprint_id: str, length: str = "medium"
    ) -> Dict[str, Any]:
        """
        Generate sprint retrospective summary.

        Args:
            sprint_id: Sprint UUID
            length: Summary length

        Returns:
            Summary with what went well, what didn't, action items
        """
        try:
            sprint = Sprint.objects.prefetch_related("issues__comments").get(id=sprint_id)
            
            # Gather sprint data
            total_issues = sprint.issues.count()
            completed = sprint.issues.filter(status__is_final=True).count()
            
            # Build context
            context = (
                f"Sprint: {sprint.name}\n"
                f"Duration: {sprint.start_date} to {sprint.end_date or 'In Progress'}\n"
                f"Issues: {completed}/{total_issues} completed\n\n"
            )
            
            # Add sample of issue discussions for context
            # (In production, you might want to be more selective)
            
            prompt = (
                f"{context}\n"
                "Generate a sprint retrospective summary with:\n"
                "1. What went well\n"
                "2. What could be improved\n"
                "3. Action items for next sprint"
            )
            
            summary = self._generate_summary(context, prompt)
            
            return {"summary": summary, "sprint_metrics": {
                "total_issues": total_issues,
                "completed": completed,
                "completion_rate": round(completed / total_issues * 100, 1) if total_issues > 0 else 0,
            }}
            
        except Exception as e:
            logger.exception(f"Error summarizing sprint: {str(e)}")
            raise

    def generate_release_notes(
        self, project_id: str, start_date, end_date
    ) -> Dict[str, Any]:
        """
        Generate release notes from completed issues.

        Args:
            project_id: Project UUID
            start_date: Release period start
            end_date: Release period end

        Returns:
            Formatted release notes
        """
        try:
            # Get completed issues in date range
            issues = Issue.objects.filter(
                project_id=project_id,
                status__is_final=True,
                resolved_at__gte=start_date,
                resolved_at__lte=end_date,
            ).select_related("issue_type")
            
            if not issues.exists():
                return {"notes": "No issues completed in this period."}
            
            # Group by issue type
            by_type = {}
            for issue in issues:
                type_name = issue.issue_type.name
                if type_name not in by_type:
                    by_type[type_name] = []
                by_type[type_name].append(issue)
            
            # Build release notes context
            context = f"Release period: {start_date} to {end_date}\n\n"
            for type_name, type_issues in by_type.items():
                context += f"{type_name.upper()}S:\n"
                for issue in type_issues:
                    context += f"- {issue.title}\n"
                context += "\n"
            
            prompt = (
                "Generate professional release notes from these completed items. "
                "Group by category and describe changes clearly for end users."
            )
            
            release_notes = self._generate_summary(context, prompt)
            
            return {
                "notes": release_notes,
                "issues_count": issues.count(),
                "by_type": {k: len(v) for k, v in by_type.items()},
            }
            
        except Exception as e:
            logger.exception(f"Error generating release notes: {str(e)}")
            raise

    def _generate_summary(self, content: str, system_prompt: str) -> str:
        """Generate summary using Azure OpenAI."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]
        
        response = self.openai.chat_completion(
            messages, temperature=0.3, max_tokens=500
        )
        
        return response["content"]

    def _get_cached_summary(
        self, obj, summary_type: str, length: str
    ) -> Optional[SummaryCache]:
        """Retrieve cached summary if valid."""
        content_type = ContentType.objects.get_for_model(obj)
        
        try:
            cached = SummaryCache.objects.get(
                content_type=content_type,
                object_id=obj.id,
                summary_type=summary_type,
                summary_length=length,
                is_valid=True,
            )
            
            # Check if expired
            if cached.expires_at and cached.expires_at < timezone.now():
                cached.is_valid = False
                cached.save()
                return None
            
            return cached
        except SummaryCache.DoesNotExist:
            return None

    def _cache_summary(
        self, obj, summary_type: str, length: str, summary_text: str, content: str
    ):
        """Cache generated summary."""
        content_type = ContentType.objects.get_for_model(obj)
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Cache for 24 hours
        expires_at = timezone.now() + timezone.timedelta(hours=24)
        
        SummaryCache.objects.update_or_create(
            content_type=content_type,
            object_id=obj.id,
            summary_type=summary_type,
            summary_length=length,
            defaults={
                "summary_text": summary_text,
                "content_hash": content_hash,
                "expires_at": expires_at,
                "is_valid": True,
            },
        )
