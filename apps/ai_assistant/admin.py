"""
Django admin for AI Assistant app.
"""

from django.contrib import admin

from apps.ai_assistant.models import (
    ChatConversation,
    ChatMessage,
    IssueEmbedding,
    SummaryCache,
)


@admin.register(IssueEmbedding)
class IssueEmbeddingAdmin(admin.ModelAdmin):
    """Admin for IssueEmbedding."""

    list_display = ["issue_id", "vector_id", "indexed_at"]
    search_fields = ["title", "vector_id"]
    readonly_fields = ["content_hash", "indexed_at"]
    ordering = ["-indexed_at"]

    def has_add_permission(self, request):
        """Prevent manual addition."""
        return False


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    """Admin for ChatConversation."""

    list_display = ["user", "project_id", "title", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["user__email", "title"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


class ChatMessageInline(admin.TabularInline):
    """Inline for chat messages."""

    model = ChatMessage
    extra = 0
    readonly_fields = ["created_at"]
    fields = ["role", "content", "prompt_tokens", "completion_tokens", "created_at"]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Admin for ChatMessage."""

    list_display = ["conversation", "role", "prompt_tokens", "completion_tokens", "created_at"]
    list_filter = ["role", "created_at"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        """Prevent manual addition."""
        return False


@admin.register(SummaryCache)
class SummaryCacheAdmin(admin.ModelAdmin):
    """Admin for SummaryCache."""

    list_display = ["summary_type", "is_valid", "created_at", "expires_at"]
    list_filter = ["summary_type", "is_valid", "created_at"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]

    actions = ["invalidate_cache"]

    def invalidate_cache(self, request, queryset):
        """Invalidate selected cache entries."""
        count = queryset.update(is_valid=False)
        self.message_user(request, f"{count} cache entries invalidated.")

    invalidate_cache.short_description = "Invalidate selected summaries"
