"""
Test settings - excludes daphne/channels to avoid Windows OpenSSL issues.
"""

from .settings import *  # noqa

# Remove daphne from INSTALLED_APPS for testing
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "daphne"]  # noqa: F405

# Disable channels layer for tests
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Use in-memory cache for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Disable Celery during tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Speed up password hashing for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
