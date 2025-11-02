"""
Factory classes for notification models.
"""

import factory
from factory.django import DjangoModelFactory

from apps.notifications.models import (
    Notification,
    NotificationPreference,
    ProjectNotificationSettings,
)


class NotificationPreferenceFactory(DjangoModelFactory):
    """Factory for NotificationPreference."""

    class Meta:
        model = NotificationPreference

    user = factory.SubFactory("apps.authentication.tests.factories.UserFactory")
    email_enabled = True
    in_app_enabled = True
    slack_enabled = False
    digest_enabled = False
    notification_types = factory.Dict({})


class NotificationFactory(DjangoModelFactory):
    """Factory for Notification."""

    class Meta:
        model = Notification

    recipient = factory.SubFactory("apps.authentication.tests.factories.UserFactory")
    notification_type = "issue_assigned"
    title = factory.Faker("sentence")
    message = factory.Faker("paragraph")
    is_read = False
    email_sent = False
    slack_sent = False


class ProjectNotificationSettingsFactory(DjangoModelFactory):
    """Factory for ProjectNotificationSettings."""

    class Meta:
        model = ProjectNotificationSettings

    project = factory.SubFactory("apps.projects.tests.factories.ProjectFactory")
    slack_notifications_enabled = False
    slack_webhook_url = ""
