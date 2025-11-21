from pathlib import Path

from django.http import HttpResponse
from django.urls import path
from django.views.generic import TemplateView

import requests
from drf_spectacular.views import SpectacularAPIView


class SwaggerUIView(TemplateView):
    template_name = "swagger-ui.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        schema_url = self.request.build_absolute_uri("/api/schema/")
        if self.request.is_secure():
            schema_url = schema_url.replace("http://", "https://")
        context["schema_url"] = schema_url
        return context


def serve_swagger_file(request, filename):
    print(f"Looking for swagger file: {filename}")

    # Crear directorio si no existe
    static_dir = Path("staticfiles/drf_spectacular_sidecar/swagger-ui-dist")
    static_dir.mkdir(parents=True, exist_ok=True)

    # Define el contenido directamente para archivos críticos
    if filename == "swagger-ui.css":
        file_path = static_dir / "swagger-ui.css"
        if not file_path.exists():
            response = requests.get(
                "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css"
            )
            with open(file_path, "wb") as f:
                f.write(response.content)

        with open(file_path, "rb") as f:
            return HttpResponse(f.read(), content_type="text/css")

    elif filename == "swagger-ui-bundle.js":
        file_path = static_dir / "swagger-ui-bundle.js"
        if not file_path.exists():
            response = requests.get(
                "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"  # noqa: E501
            )
            with open(file_path, "wb") as f:
                f.write(response.content)

        with open(file_path, "rb") as f:
            return HttpResponse(f.read(), content_type="application/javascript")

    elif filename == "swagger-ui-standalone-preset.js":
        file_path = static_dir / "swagger-ui-standalone-preset.js"
        if not file_path.exists():
            response = requests.get(
                "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-standalone-preset.js"  # noqa: E501
            )
            with open(file_path, "wb") as f:
                f.write(response.content)

        with open(file_path, "rb") as f:
            return HttpResponse(f.read(), content_type="application/javascript")

    else:
        return HttpResponse(f"File not found: {filename}", status=404)


def get_spectacular_urls():
    return [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SwaggerUIView.as_view(), name="swagger-ui"),
        path("api/redoc/", SpectacularAPIView.as_view(), name="redoc"),
        path(
            "swagger-ui-assets/swagger-ui.css",
            serve_swagger_file,
            {"filename": "swagger-ui.css"},
        ),
        path(
            "swagger-ui-assets/swagger-ui-bundle.js",
            serve_swagger_file,
            {"filename": "swagger-ui-bundle.js"},
        ),
        path(
            "swagger-ui-assets/swagger-ui-standalone-preset.js",
            serve_swagger_file,
            {"filename": "swagger-ui-standalone-preset.js"},
        ),
    ]
