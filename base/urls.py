from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from .spectacular_views import get_spectacular_urls

urlpatterns = get_spectacular_urls() + [
    path(
        "admin/login/",
        auth_views.LoginView.as_view(
            template_name="admin/login.html",
            extra_context={
                "title": "Login",
                "site_title": "FICCT-SCRUM Admin",
                "site_header": "FICCT-SCRUM Administration",
            },
        ),
        name="login",
    ),
    path("admin/logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.authentication.urls")),
    path("api/v1/orgs/", include("apps.organizations.urls")),
    path("api/v1/workspaces/", include("apps.workspaces.urls")),
    path("api/v1/projects/", include("apps.projects.urls")),
    path("api/v1/logs/", include("apps.logging.urls")),
    path("api/v1/integrations/", include("apps.integrations.urls")),
    path("api/v1/reporting/", include("apps.reporting.urls")),
    path("api/v1/ml/", include("apps.ml.urls")),
    path("api/v1/ai/", include("apps.ai_assistant.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    try:
        import debug_toolbar

        urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    except ImportError:
        pass
