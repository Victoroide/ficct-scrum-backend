"""
Signals for automatic issue indexing in Pinecone.

Automatically indexes issues when created/updated and removes them when deleted.
Includes anti-duplication logic to prevent redundant reindexing.
"""

import logging

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.projects.models import Issue, Sprint

logger = logging.getLogger(__name__)

# Semantic fields that require reindexing when changed
ISSUE_SEMANTIC_FIELDS = {
    "title",
    "description",
    "status_id",
    "priority",
    "assignee_id",
    "sprint_id",
    "issue_type_id",
}

SPRINT_SEMANTIC_FIELDS = {"name", "goal", "status", "start_date", "end_date"}


@receiver(pre_save, sender=Issue)
def store_issue_old_values(sender, instance, **kwargs):
    """
    Store old values before save to detect changes in post_save.

    Args:
        sender: Issue model
        instance: Issue instance
        **kwargs: Additional arguments
    """
    if instance.pk:
        try:
            old_instance = Issue.objects.get(pk=instance.pk)
            instance._old_values = {
                "title": old_instance.title,
                "description": old_instance.description,
                "status_id": old_instance.status_id,
                "priority": old_instance.priority,
                "assignee_id": old_instance.assignee_id,
                "sprint_id": old_instance.sprint_id,
                "issue_type_id": old_instance.issue_type_id,
            }
        except Issue.DoesNotExist:
            instance._old_values = {}
    else:
        instance._old_values = {}


@receiver(post_save, sender=Issue)
def auto_index_issue(sender, instance, created, **kwargs):
    """
    Automatically index issues in Pinecone when created or updated.

    Only reindexes if semantic fields changed to avoid redundant API calls.
    Uses cache-based debouncing to prevent duplicate reindexing within 30 seconds.

    Args:
        sender: Issue model
        instance: Issue instance
        created: True if newly created
        **kwargs: Additional arguments
    """
    # Check cache to prevent duplicate reindexing within 30 seconds
    cache_key = f"pinecone_reindex_issue_{instance.id}"
    if cache.get(cache_key):
        logger.debug(f"Skipping reindex for issue {instance.id} (debounced)")
        return

    # Determine if reindex is needed
    should_reindex = created

    if not created and hasattr(instance, "_old_values"):
        # Check if any semantic fields changed
        old_values = instance._old_values
        for field in ISSUE_SEMANTIC_FIELDS:
            old_val = old_values.get(field)
            new_val = getattr(instance, field, None)
            if old_val != new_val:
                logger.debug(
                    f"Issue {instance.id} field '{field}' changed: {old_val} -> {new_val}"  # noqa: E501
                )
                should_reindex = True
                break

    if not should_reindex:
        logger.debug(f"Skipping reindex for issue {instance.id} (no semantic changes)")
        return

    # Perform reindexing
    try:
        from apps.ai_assistant.services import RAGService

        rag_service = RAGService()
        rag_service.index_issue(str(instance.id))

        # Set cache to prevent duplicate reindexing
        cache.set(cache_key, True, 30)  # 30 second debounce

        logger.info(f"Auto-indexed issue {instance.id} in Pinecone")
    except Exception as e:
        logger.exception(f"Failed to auto-index issue {instance.id}: {str(e)}")


@receiver(post_delete, sender=Issue)
def remove_issue_from_index(sender, instance, **kwargs):
    """
    Remove deleted issues from Pinecone index.

    Args:
        sender: Issue model
        instance: Issue instance
        **kwargs: Additional arguments
    """
    try:
        from apps.ai_assistant.services import RAGService

        rag_service = RAGService()
        rag_service.delete_issue_embedding(str(instance.id))

        logger.info(f"Removed issue {instance.id} from Pinecone index")
    except Exception as e:
        logger.exception(f"Failed to remove issue {instance.id} from index: {str(e)}")


# ============================================================================
# SPRINT SIGNALS
# ============================================================================


@receiver(pre_save, sender=Sprint)
def store_sprint_old_values(sender, instance, **kwargs):
    """
    Store old values before save to detect changes in post_save.

    Args:
        sender: Sprint model
        instance: Sprint instance
        **kwargs: Additional arguments
    """
    if instance.pk:
        try:
            old_instance = Sprint.objects.get(pk=instance.pk)
            instance._old_values = {
                "name": old_instance.name,
                "goal": old_instance.goal,
                "status": old_instance.status,
                "start_date": old_instance.start_date,
                "end_date": old_instance.end_date,
            }
        except Sprint.DoesNotExist:
            instance._old_values = {}
    else:
        instance._old_values = {}


@receiver(post_save, sender=Sprint)
def auto_index_sprint(sender, instance, created, **kwargs):
    """
    Automatically index sprints in Pinecone when created or updated.

    Only reindexes if semantic fields changed.

    Args:
        sender: Sprint model
        instance: Sprint instance
        created: True if newly created
        **kwargs: Additional arguments
    """
    # Check cache to prevent duplicate reindexing within 30 seconds
    cache_key = f"pinecone_reindex_sprint_{instance.id}"
    if cache.get(cache_key):
        logger.debug(f"Skipping reindex for sprint {instance.id} (debounced)")
        return

    # Determine if reindex is needed
    should_reindex = created

    if not created and hasattr(instance, "_old_values"):
        # Check if any semantic fields changed
        old_values = instance._old_values
        for field in SPRINT_SEMANTIC_FIELDS:
            old_val = old_values.get(field)
            new_val = getattr(instance, field, None)
            if old_val != new_val:
                logger.debug(
                    f"Sprint {instance.id} field '{field}' changed: {old_val} -> {new_val}"  # noqa: E501
                )
                should_reindex = True
                break

    if not should_reindex:
        logger.debug(f"Skipping reindex for sprint {instance.id} (no semantic changes)")
        return

    # Perform reindexing
    try:
        from apps.ai_assistant.services import RAGService

        rag_service = RAGService()

        # Index the sprint
        success, error = rag_service.index_sprint(sprint_id=str(instance.id))

        if success:
            # Set cache to prevent duplicate reindexing
            cache.set(cache_key, True, 30)  # 30 second debounce
            logger.info(f"Auto-indexed sprint {instance.id} in Pinecone")
        else:
            logger.error(f"Failed to auto-index sprint {instance.id}: {error}")
    except Exception as e:
        logger.exception(f"Failed to auto-index sprint {instance.id}: {str(e)}")


@receiver(post_delete, sender=Sprint)
def remove_sprint_from_index(sender, instance, **kwargs):
    """
    Remove deleted sprints from Pinecone index.

    Args:
        sender: Sprint model
        instance: Sprint instance
        **kwargs: Additional arguments
    """
    try:
        from apps.ai_assistant.services import RAGService

        rag_service = RAGService()

        # Delete sprint vector from "sprints" namespace
        if rag_service.available and rag_service.index:
            vector_id = f"sprint_{instance.id}"
            rag_service.index.delete(ids=[vector_id], namespace="sprints")
            logger.info(f"Removed sprint {instance.id} from Pinecone index")
    except Exception as e:
        logger.exception(f"Failed to remove sprint {instance.id} from index: {str(e)}")
