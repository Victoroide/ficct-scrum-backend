from django.contrib.auth import get_user_model
from django.db import transaction

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.authentication.serializers import PasswordChangeSerializer, UserSerializer
from apps.logging.services import LoggerService

User = get_user_model()


@extend_schema(tags=["Authentication"])
class UserViewSet(viewsets.ModelViewSet):
    """
    User management operations including profile viewing, editing and password changes.
    Provides comprehensive user account management with security controls.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Users can only see their own profile unless they are staff."""
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)

    @extend_schema(
        operation_id="users_me",
        summary="Get Current User",
        description="Retrieve the current authenticated user's profile information",
        responses={200: UserSerializer},
    )
    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """Get current user profile."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @extend_schema(
        operation_id="users_update_me",
        summary="Update Current User",
        description="Update the current authenticated user's profile information",
        request=UserSerializer,
        responses={200: UserSerializer},
    )
    @action(detail=False, methods=["patch", "put"], url_path="me")
    @transaction.atomic
    def update_me(self, request):
        """Update current user profile."""
        try:
            serializer = self.get_serializer(
                request.user, data=request.data, partial=True
            )
            if serializer.is_valid():
                serializer.save()

                LoggerService.log_info(
                    action="user_profile_updated",
                    user=request.user,
                    ip_address=request.META.get("REMOTE_ADDR"),
                    details={"updated_fields": list(request.data.keys())},
                )

                return Response(serializer.data)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            LoggerService.log_error(
                action="user_profile_update_error", user=request.user, error=str(e)
            )
            return Response(
                {"error": "Profile update failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        operation_id="users_change_password",
        summary="Change Password",
        description="Change the user's password with old password verification",
        request=PasswordChangeSerializer,
        responses={
            200: inline_serializer(
                name="PasswordChangeResponse",
                fields={"message": serializers.CharField()},
            ),
            400: "Invalid old password or validation errors",
            403: "Permission denied",
        },
    )
    @action(detail=True, methods=["post"], url_path="change-password")
    @transaction.atomic
    def change_password(self, request, pk=None):
        """Change user password with old password verification."""
        try:
            user = self.get_object()

            # Ensure user can only change their own password
            if user != request.user and not request.user.is_staff:
                return Response(
                    {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
                )

            serializer = PasswordChangeSerializer(data=request.data)
            if serializer.is_valid():
                old_password = serializer.validated_data["old_password"]
                new_password = serializer.validated_data["new_password"]

                if not user.check_password(old_password):
                    return Response(
                        {"error": "Invalid old password"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                user.set_password(new_password)
                user.save()

                LoggerService.log_info(
                    action="password_changed",
                    user=user,
                    ip_address=request.META.get("REMOTE_ADDR"),
                )

                return Response(
                    {"message": "Password changed successfully"},
                    status=status.HTTP_200_OK,
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            LoggerService.log_error(
                action="password_change_error", user=request.user, error=str(e)
            )
            return Response(
                {"error": "Password change failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
