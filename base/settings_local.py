"""
Django settings for local development (Windows compatible).

This configuration is identical to base.settings but without Daphne,
which has SSL compatibility issues on Windows.

Usage:
    python manage.py runserver --settings=base.settings_local
    python manage.py check --settings=base.settings_local
"""

from .settings import *  # noqa: F403, F401

# Remove daphne from INSTALLED_APPS for Windows compatibility
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "daphne"]  # noqa: F405

# Use default ASGI application instead of custom one
ASGI_APPLICATION = "django.core.asgi.get_asgi_application()"
