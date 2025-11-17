from django.urls import include, path

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, UserSerializer
from .viewsets import AuthViewSet, UserProfileViewSet, UserViewSet


class CustomTokenRefreshView(TokenRefreshView):
    """Wraps SimpleJWT TokenRefreshView with proper Swagger documentation"""

    @extend_schema(
        tags=["Authentication"],
        operation_id="auth_token_refresh",
        summary="Refresh JWT Token",
        description="Obtain a new access token using a valid refresh token",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(
            {
                "user_id": user.pk,
                "email": user.email,
                "username": user.username,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            }
        )


router = DefaultRouter()
router.register(r"", AuthViewSet, basename="auth")
router.register(r"users", UserViewSet, basename="users")
router.register(r"profiles", UserProfileViewSet, basename="profiles")

urlpatterns = [
    path("", include(router.urls)),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("token/", CustomAuthToken.as_view(), name="api_token_auth"),
    path("session/", include("rest_framework.urls", namespace="rest_framework")),
    # Custom auth endpoints
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
