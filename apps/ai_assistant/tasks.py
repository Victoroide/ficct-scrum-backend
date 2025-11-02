"""
Celery tasks for AI assistant app.

Scheduled tasks for embedding maintenance and cache cleanup.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="apps.ai_assistant.tasks.reindex_stale_issues")
def reindex_stale_issues(self):
    """
    Reindex issues that have been updated but not re-indexed.

    This task runs daily at 4 AM and identifies issues whose content has changed
    since last indexing, then regenerates their embeddings.

    Returns:
        dict: Reindexing results summary
    """
    try:
        from apps.ai_assistant.models import IssueEmbedding
        from apps.ai_assistant.services import RAGService
        from apps.projects.models import Issue

        logger.info("Starting stale issues reindexing task")

        rag_service = RAGService()
        results = {
            "issues_checked": 0,
            "issues_reindexed": 0,
            "errors": [],
        }

        # Get all issues with embeddings
        embeddings = IssueEmbedding.objects.select_related("issue").all()

        for embedding in embeddings:
            try:
                issue = embedding.issue
                results["issues_checked"] += 1

                # Check if issue was updated after last embedding
                if issue.updated_at > embedding.indexed_at:
                    # Calculate new content hash
                    import hashlib

                    content = f"{issue.title} {issue.description or ''}"
                    new_hash = hashlib.sha256(content.encode()).hexdigest()

                    # Only reindex if content actually changed
                    if new_hash != embedding.content_hash:
                        logger.info(f"Reindexing stale issue {issue.key}")
                        rag_service.index_issue(str(issue.id), force_reindex=True)
                        results["issues_reindexed"] += 1

            except Exception as e:
                error_msg = f"Error reindexing issue {embedding.issue_id}: {str(e)}"
                logger.exception(error_msg)
                results["errors"].append(error_msg)

        logger.info(f"Stale issues reindexing task completed: {results}")
        return results

    except Exception as e:
        logger.exception(f"Critical error in reindex_stale_issues task: {str(e)}")
        raise


@shared_task(bind=True, name="apps.ai_assistant.tasks.cleanup_old_summaries")
def cleanup_old_summaries(self):
    """
    Clean up expired summary cache entries.

    This task runs daily at 3 AM and removes cached summaries that have expired.

    Returns:
        dict: Cleanup results
    """
    try:
        from apps.ai_assistant.models import SummaryCache

        logger.info("Starting summary cache cleanup task")

        now = timezone.now()

        # Delete expired summaries
        deleted_count, _ = SummaryCache.objects.filter(
            expires_at__lt=now
        ).delete()

        logger.info(f"Deleted {deleted_count} expired summary cache entries")

        # Also delete old invalid summaries (older than 30 days)
        thirty_days_ago = now - timedelta(days=30)
        old_invalid_count, _ = SummaryCache.objects.filter(
            is_valid=False,
            created_at__lt=thirty_days_ago,
        ).delete()

        logger.info(f"Deleted {old_invalid_count} old invalid summary cache entries")

        return {
            "expired_deleted": deleted_count,
            "invalid_deleted": old_invalid_count,
            "total_deleted": deleted_count + old_invalid_count,
        }

    except Exception as e:
        logger.exception(f"Error in cleanup_old_summaries task: {str(e)}")
        raise


@shared_task(bind=True, name="apps.ai_assistant.tasks.cleanup_old_chat_conversations")
def cleanup_old_chat_conversations(self):
    """
    Archive or delete old chat conversations (older than 6 months).

    This maintenance task prevents unbounded growth of chat history.

    Returns:
        dict: Cleanup results
    """
    try:
        from apps.ai_assistant.models import ChatConversation

        logger.info("Starting chat conversation cleanup task")

        six_months_ago = timezone.now() - timedelta(days=180)

        # Delete inactive conversations older than 6 months
        deleted_count, _ = ChatConversation.objects.filter(
            updated_at__lt=six_months_ago,
            is_active=False,
        ).delete()

        logger.info(f"Deleted {deleted_count} old chat conversations")
        return {"deleted_count": deleted_count}

    except Exception as e:
        logger.exception(f"Error in cleanup_old_chat_conversations task: {str(e)}")
        raise


@shared_task(bind=True, name="apps.ai_assistant.tasks.refresh_project_embeddings")
def refresh_project_embeddings(self, project_id: str):
    """
    Refresh all embeddings for a specific project.

    This task can be triggered manually to rebuild the vector index for a project.

    Args:
        project_id: UUID of the project

    Returns:
        dict: Refresh results
    """
    try:
        from apps.ai_assistant.services import RAGService

        logger.info(f"Starting project embeddings refresh for project {project_id}")

        rag_service = RAGService()
        result = rag_service.index_project_issues(project_id, batch_size=50)

        logger.info(f"Project embeddings refresh completed: {result}")
        return result

    except Exception as e:
        logger.exception(f"Error in refresh_project_embeddings task: {str(e)}")
        raise
