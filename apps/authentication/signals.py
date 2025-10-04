from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.authentication.models import User, UserProfile


@receiver(post_save, sender=User)
@transaction.atomic
def create_user_profile(sender, instance, created, **kwargs):
    """Create user profile automatically when user is created."""
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
@transaction.atomic
def save_user_profile(sender, instance, **kwargs):
    """Save user profile when user is saved."""
    if hasattr(instance, "profile"):
        instance.profile.save()
