import os
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

from decouple import config
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-=r-&)dvzf1b)o=8jx1ew-7de!8f-illj^k+yz&jun^mmt)jcdb",
)

DEBUG = config("DEBUG", default=True, cast=bool)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = False
USE_TLS = True

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:4200,http://127.0.0.1:4200",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.ficct\.com$",
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    "django_filters",
    "storages",
    "channels",
]

LOCAL_APPS = [
    "apps.authentication",
    "apps.organizations",
    "apps.workspaces",
    "apps.projects",
    "apps.logging",
    "apps.integrations",
    "apps.reporting",
    "apps.ml",
    "apps.ai_assistant",
    "apps.notifications",
    "apps.admin_tools",
]

INSTALLED_APPS = ["daphne"] + DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.reporting.middleware.ActivityLogMiddleware",  # Track user for ActivityLog
    "apps.admin_tools.middleware.PerformanceMonitoringMiddleware",  # Monitor performance
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "base.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
            os.path.join(
                BASE_DIR,
                ".venv",
                "Lib",
                "site-packages",
                "drf_spectacular",
                "templates",
            ),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "base.wsgi.application"
ASGI_APPLICATION = "base.asgi.application"

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    tmpPostgres = urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": tmpPostgres.path.replace("/", ""),
            "USER": tmpPostgres.username,
            "PASSWORD": tmpPostgres.password,
            "HOST": tmpPostgres.hostname,
            "PORT": 5432,
            "OPTIONS": dict(parse_qsl(tmpPostgres.query)),
            "ATOMIC_REQUESTS": False,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "ATOMIC_REQUESTS": False,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION", "us-east-1")

AWS_DEFAULT_ACL = None
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}

USE_S3 = config("USE_S3", default=True, cast=bool)

if USE_S3 and AWS_STORAGE_BUCKET_NAME and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    STORAGES = {
        "default": {
            "BACKEND": "base.storage.MediaStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
    STATIC_URL = "/static/"
    STATIC_ROOT = BASE_DIR / "staticfiles"

    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"

    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_S3_VERIFY = True
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

    STATIC_URL = "/static/"
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"
    STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "authentication.User"

# Email Configuration
USE_SES = config("USE_SES", default=True, cast=bool)
AWS_SES_REGION_NAME = os.getenv("AWS_SES_REGION_NAME", AWS_S3_REGION_NAME)
AWS_SES_REGION_ENDPOINT = f"email.{AWS_SES_REGION_NAME}.amazonaws.com"

if USE_SES and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    EMAIL_BACKEND = "django_ses.SESBackend"
    AWS_SES_RETURN_PATH = config("AWS_SES_RETURN_PATH", default=None)
else:
    # Fallback to console backend for development
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@ficct-scrum.com")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Frontend URL for email links
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:4200")

# Authentication backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

# Session settings
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_SAVE_EVERY_REQUEST = True

# CSRF settings
CSRF_USE_SESSIONS = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",  # For Swagger UI login
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_ACCESS_TOKEN_LIFETIME", default=60, cast=int)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_REFRESH_TOKEN_LIFETIME", default=1440, cast=int)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": config("JWT_SECRET_KEY", default=SECRET_KEY),
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

def postprocess_schema_tags(result, generator, request, public):
    """Remap lowercase tags to proper capitalized versions and fix nested routes"""
    tag_mapping = {
        'auth': 'Authentication',
        'workspaces': 'Workspaces',
        'workspace-members': 'Workspaces',
        'projects': 'Projects',
        'project-config': 'Projects',
        'issue': 'Issues',
        'issue-type': 'Issues',
        'sprint': 'Sprints',
        'board': 'Boards',
        'github-integration': 'Integrations',
        'github-commit': 'Integrations',
        'github-pull-request': 'Integrations',
        'integrations': 'Integrations',
    }
    
    # Path-based tag assignment for nested routes
    path_patterns = {
        '/issues/': 'Issues',
        '/sprints/': 'Sprints',
        '/boards/': 'Boards',
    }
    
    for path, path_item in result.get('paths', {}).items():
        for operation in path_item.values():
            if isinstance(operation, dict) and 'tags' in operation:
                # First, remap existing tags via mapping
                operation['tags'] = [
                    tag_mapping.get(tag, tag) 
                    for tag in operation['tags']
                ]
                
                # Then, override based on path patterns for nested routes
                for pattern, correct_tag in path_patterns.items():
                    if pattern in path and correct_tag not in operation['tags']:
                        # Replace incorrect tag with correct one
                        operation['tags'] = [correct_tag]
                        break
    
    return result


SPECTACULAR_SETTINGS = {
    "TITLE": "FICCT-SCRUM API",
    "DESCRIPTION": "API documentation for FICCT-SCRUM application",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "COMPONENT_SPLIT_REQUEST": True,
    "POSTPROCESSING_HOOKS": ["base.settings.postprocess_schema_tags"],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
        "syntaxHighlight.theme": "monokai",
        "operationsSorter": "method",
        "tagsSorter": "alpha",
        "showCommonExtensions": True,
    },
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "SCHEMA_PATH_PREFIX": "/api/v1/",
    "SORT_OPERATIONS": True,
    "TAGS": [
        {
            "name": "Authentication",
            "description": "User registration, authentication, profiles and password management",
        },
        {
            "name": "Organizations",
            "description": "Organization creation, management, member administration and invitations",
        },
        {
            "name": "Workspaces",
            "description": "Workspace management and team collaboration tools",
        },
        {
            "name": "Projects",
            "description": "Project creation, configuration and lifecycle management",
        },
        {
            "name": "Issues",
            "description": "Issue tracking, types, attachments, comments and links",
        },
        {
            "name": "Boards",
            "description": "Kanban board management, columns and workflow visualization",
        },
        {
            "name": "Sprints",
            "description": "Sprint planning, execution and progress tracking",
        },
        {
            "name": "Integrations",
            "description": "Third-party integrations including GitHub repositories, commits and pull requests",
        },
        {
            "name": "Reporting",
            "description": "Analytics, reports, diagrams, activity logs and custom filters",
        },
        {
            "name": "Logging",
            "description": "System audit trails, error tracking and monitoring",
        },
    ],
}

CORS_ALLOW_CREDENTIALS = True

# Cache Configuration - Using Redis for persistence
# Database 2 used for general caching (OAuth states, temporary data)
CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL")

if CACHE_REDIS_URL:
    # Docker/Production: Use Redis URL with password
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": CACHE_REDIS_URL,
            "TIMEOUT": 300,  # 5 minutes default
        }
    }
else:
    # Local development: Use host/port
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": f"redis://:{config('REDIS_PASSWORD', default='redis123')}@{config('REDIS_HOST', default='127.0.0.1')}:{config('REDIS_PORT', default=6379, cast=int)}/2",
            "TIMEOUT": 300,  # 5 minutes default
        }
    }

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# ============================================================================
# GitHub OAuth Configuration
# ============================================================================

GITHUB_CLIENT_ID = config("GITHUB_CLIENT_ID", default="")
GITHUB_CLIENT_SECRET = config("GITHUB_CLIENT_SECRET", default="")
GITHUB_OAUTH_CALLBACK_URL = config(
    "GITHUB_OAUTH_CALLBACK_URL",
    default="http://localhost:8000/api/v1/integrations/github/oauth/callback/",
)

# ============================================================================
# Django Channels Configuration
# ============================================================================

# Support for both URL-based and host/port-based Redis configuration
CHANNEL_LAYERS_REDIS_URL = os.getenv("CHANNEL_LAYERS_REDIS_URL")

if CHANNEL_LAYERS_REDIS_URL:
    # Docker/Production: Use Redis URL with password
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [CHANNEL_LAYERS_REDIS_URL],
            },
        },
    }
else:
    # Local development: Use host/port
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [(config("REDIS_HOST", default="127.0.0.1"), config("REDIS_PORT", default=6379, cast=int))],
            },
        },
    }

# WebSocket CORS
CORS_ALLOW_CREDENTIALS = True

# ==========================================================================
# CELERY CONFIGURATION
# ==========================================================================

# Celery Broker URL (use same Redis as Channel Layers)
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    f"redis://:{config('REDIS_PASSWORD', default='redis123')}@{config('REDIS_HOST', default='127.0.0.1')}:{config('REDIS_PORT', default=6379, cast=int)}/0"
)

# Celery Result Backend
CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    f"redis://:{config('REDIS_PASSWORD', default='redis123')}@{config('REDIS_HOST', default='127.0.0.1')}:{config('REDIS_PORT', default=6379, cast=int)}/1"
)

# Celery Task Settings
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 3600  # 1 hour max
CELERY_TASK_SOFT_TIME_LIMIT = 3300  # 55 minutes soft limit

# Celery Worker Settings
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Celery Beat Schedule (defined in base/celery.py)
