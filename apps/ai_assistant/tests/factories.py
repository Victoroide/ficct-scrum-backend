"""
Factory classes for AI assistant models.
"""

from django.utils import timezone

import factory
from factory.django import DjangoModelFactory

from apps.ai_assistant.models import (
    ChatConversation,
    ChatMessage,
    IssueEmbedding,
    SummaryCache,
)


class IssueEmbeddingFactory(DjangoModelFactory):
    """Factory for IssueEmbedding."""

    class Meta:
        model = IssueEmbedding

    issue = factory.SubFactory("apps.projects.tests.factories.IssueFactory")
    vector_id = factory.Sequence(lambda n: f"issue_{n}")
    content_hash = factory.Faker("sha256")
    indexed_at = factory.LazyFunction(timezone.now)


class ChatConversationFactory(DjangoModelFactory):
    """Factory for ChatConversation."""

    class Meta:
        model = ChatConversation

    user = factory.SubFactory("apps.authentication.tests.factories.UserFactory")
    project = factory.SubFactory("apps.projects.tests.factories.ProjectFactory")
    title = factory.Faker("sentence")
    is_active = True


class ChatMessageFactory(DjangoModelFactory):
    """Factory for ChatMessage."""

    class Meta:
        model = ChatMessage

    conversation = factory.SubFactory(ChatConversationFactory)
    role = "user"
    content = factory.Faker("sentence")
    tokens_used = 150


class SummaryCacheFactory(DjangoModelFactory):
    """Factory for SummaryCache."""

    class Meta:
        model = SummaryCache

    content_type = factory.SubFactory("django.contrib.contenttypes.models.ContentType")
    object_id = factory.Faker("uuid4")
    summary_type = "issue_discussion"
    summary_text = factory.Faker("paragraph")
    is_valid = True
    expires_at = factory.LazyFunction(
        lambda: timezone.now() + timezone.timedelta(days=1)
    )
