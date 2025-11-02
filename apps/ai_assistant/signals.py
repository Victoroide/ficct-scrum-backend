"""
Signals for automatic issue indexing in Pinecone.

Automatically indexes issues when created/updated and removes them when deleted.
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.projects.models import Issue

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Issue)
def auto_index_issue(sender, instance, created, **kwargs):
    """
    Automatically index issues in Pinecone when created or updated.

    Args:
        sender: Issue model
        instance: Issue instance
        created: True if newly created
        **kwargs: Additional arguments
    """
    # Only index if title or description changed
    if created or kwargs.get("update_fields") is None:
        try:
            from apps.ai_assistant.services import RAGService
            
            rag_service = RAGService()
            rag_service.index_issue(str(instance.id))
            
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
