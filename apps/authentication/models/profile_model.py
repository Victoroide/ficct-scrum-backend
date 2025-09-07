from django.db import models
from django.conf import settings
from PIL import Image
import os


def user_avatar_path(instance, filename):
    return f'avatars/user_{instance.user.id}/{filename}'


class UserProfile(models.Model):
    TIMEZONE_CHOICES = [
        ('UTC', 'UTC'),
        ('America/New_York', 'Eastern Time'),
        ('America/Chicago', 'Central Time'),
        ('America/Denver', 'Mountain Time'),
        ('America/Los_Angeles', 'Pacific Time'),
        ('Europe/London', 'London'),
        ('Europe/Paris', 'Paris'),
        ('Asia/Tokyo', 'Tokyo'),
        ('Asia/Shanghai', 'Shanghai'),
        ('Australia/Sydney', 'Sydney'),
    ]

    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('de', 'German'),
        ('pt', 'Portuguese'),
        ('zh', 'Chinese'),
        ('ja', 'Japanese'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        primary_key=True
    )
    avatar = models.ImageField(
        upload_to=user_avatar_path,
        null=True,
        blank=True,
        help_text='Profile picture (max 5MB)'
    )
    bio = models.TextField(max_length=500, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(
        max_length=50,
        choices=TIMEZONE_CHOICES,
        default='UTC'
    )
    language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default='en'
    )
    github_username = models.CharField(max_length=100, blank=True)
    linkedin_url = models.URLField(blank=True)
    website_url = models.URLField(blank=True)
    notification_preferences = models.JSONField(default=dict)
    is_online = models.BooleanField(default=False)
    last_activity = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.full_name}'s Profile"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.avatar:
            self._resize_avatar()

    def _resize_avatar(self):
        if self.avatar and os.path.exists(self.avatar.path):
            with Image.open(self.avatar.path) as img:
                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size)
                    img.save(self.avatar.path)

    @property
    def avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return None
