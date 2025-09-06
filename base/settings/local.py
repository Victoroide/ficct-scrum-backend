from .base import *

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Database configuration is handled in base.py via DATABASE_URL

INSTALLED_APPS += [
    'django_extensions',
]

if DEBUG:
    INSTALLED_APPS += [
        'debug_toolbar',
    ]
    
    MIDDLEWARE += [
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    ]
    
    INTERNAL_IPS = [
        '127.0.0.1',
    ]

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
