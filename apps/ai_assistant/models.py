"""AI Assistant models for chat history and embeddings."""

import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

User = get_user_model()


class IssueEmbedding(models.Model):
    """Stores vector embeddings for issues in Pinecone."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue_id = models.UUIDField(unique=True, db_index=True)
    project_id = models.UUIDField(db_index=True)

    # Pinecone reference
    vector_id = models.CharField(max_length=255, unique=True)
    namespace = models.CharField(max_length=100, default="issues")

    # Metadata for quick filtering
    title = models.CharField(max_length=500)
    content_hash = models.CharField(
        max_length=64, help_text="Hash of title+description"
    )

    # Indexing status
    is_indexed = models.BooleanField(default=False)
    indexed_at = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_issue_embeddings"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["issue_id"]),
            models.Index(fields=["project_id", "is_indexed"]),
        ]

    def __str__(self):
        return f"Embedding for issue {self.issue_id}"


class ChatConversation(models.Model):
    """Stores AI assistant chat conversations."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ai_conversations"
    )
    project_id = models.UUIDField(null=True, blank=True)

    title = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_chat_conversations"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["project_id"]),
        ]

    def __str__(self):
        return f"Conversation {self.id} - {self.user.email}"


class ChatMessage(models.Model):
    """Individual messages in a conversation."""

    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        ChatConversation, on_delete=models.CASCADE, related_name="messages"
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()

    # RAG context used
    context_issues = models.JSONField(default=list, blank=True)
    sources = models.JSONField(default=list, blank=True)

    # Token usage
    prompt_tokens = models.IntegerField(null=True, blank=True)
    completion_tokens = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_chat_messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
        ]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class SummaryCache(models.Model):
    """Caches AI-generated summaries to avoid regeneration."""

    SUMMARY_TYPES = [
        ("issue_discussion", "Issue Discussion"),
        ("sprint_retrospective", "Sprint Retrospective"),
        ("project_status", "Project Status"),
        ("release_notes", "Release Notes"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    summary_type = models.CharField(max_length=50, choices=SUMMARY_TYPES)

    # Generic relation to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")

    # Summary data
    summary_text = models.TextField()
    summary_length = models.CharField(
        max_length=20, default="medium"
    )  # brief, medium, detailed

    # Cache metadata
    content_hash = models.CharField(max_length=64, help_text="Hash of source content")
    is_valid = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ai_summary_cache"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["is_valid", "expires_at"]),
        ]
        unique_together = [
            ["content_type", "object_id", "summary_type", "summary_length"]
        ]

    def __str__(self):
        return f"{self.get_summary_type_display()} - {self.object_id}"
