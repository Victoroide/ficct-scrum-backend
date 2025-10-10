import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import logout
from django.db import transaction
from django.utils import timezone

from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authentication.models import PasswordResetToken, User, UserProfile
from apps.authentication.serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from apps.logging.services import LoggerService
from base.services import EmailService


@extend_schema(tags=["Authentication"])
class AuthViewSet(viewsets.GenericViewSet):
    """
    Authentication operations including registration, login, logout, and password reset.
    Handles all core authentication workflows with comprehensive logging and security.
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer

    def get_client_ip(self, request):
        """Extract client IP address from request headers."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def get_user_agent(self, request):
        """Extract user agent from request headers."""
        return request.META.get("HTTP_USER_AGENT", "")

    @action(detail=False, methods=["post"], url_path="register")
    @extend_schema(
        operation_id="auth_register",
        summary="User Registration",
        description=(
            "Register a new user account. **NEW FEATURES:** "
            "1) Automatically sends welcome email via AWS SES. "
            "2) Auto-accepts pending organization invitations for the registered email. "
            "3) Returns auto_joined_organizations if user had pending invitations. "
            "Email delivery failures are logged but do not block registration. "
            "Frontend should check for auto_joined_organizations and redirect to suggested organization."
        ),
        request=UserRegistrationSerializer,
        responses={
            201: inline_serializer(
                name="RegistrationSuccess",
                fields={
                    "id": serializers.IntegerField(),
                    "email": serializers.EmailField(),
                    "username": serializers.CharField(),
                    "first_name": serializers.CharField(),
                    "last_name": serializers.CharField(),
                    "auto_joined_organizations": serializers.ListField(
                        child=serializers.DictField(),
                        required=False,
                        help_text="Organizations auto-joined from pending invitations"
                    ),
                    "pending_invitations_accepted": serializers.IntegerField(
                        required=False,
                        help_text="Number of invitations auto-accepted"
                    ),
                    "redirect_suggestion": serializers.CharField(
                        required=False,
                        help_text="Suggested redirect URL to first organization"
                    ),
                },
            ),
            400: inline_serializer(
                name="RegistrationError",
                fields={
                    "email": serializers.ListField(
                        child=serializers.CharField(),
                        help_text="User with this email already exists",
                    ),
                    "username": serializers.ListField(
                        child=serializers.CharField(),
                        help_text="User with this username already exists",
                    ),
                    "non_field_errors": serializers.ListField(
                        child=serializers.CharField(),
                        help_text="Passwords don't match",
                    ),
                },
            ),
        },
    )
    @transaction.atomic
    def register(self, request):
        """Register a new user account."""
        try:
            # Check for required password fields first
            if "password" not in request.data:
                return Response(
                    {"error": "Password is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if "password_confirm" not in request.data:
                return Response(
                    {"error": "Password confirmation is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = UserRegistrationSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save()

                # Auto-accept pending invitations for this email
                auto_joined_organizations = []
                pending_invitations_count = 0
                
                try:
                    from apps.organizations.models import OrganizationInvitation
                    
                    pending_invitations = OrganizationInvitation.objects.filter(
                        email=user.email, status="pending"
                    ).select_related("organization", "invited_by")
                    
                    for invitation in pending_invitations:
                        if not invitation.is_expired:
                            try:
                                membership = invitation.accept(user)
                                auto_joined_organizations.append({
                                    "id": str(invitation.organization.id),
                                    "name": invitation.organization.name,
                                    "role": invitation.role,
                                })
                                pending_invitations_count += 1
                                
                                # Send welcome email for each organization
                                try:
                                    EmailService.send_organization_welcome_email(
                                        user=user,
                                        organization=invitation.organization,
                                        role=invitation.role,
                                    )
                                except Exception:
                                    pass  # Email failure shouldn't block registration
                                    
                            except Exception as e:
                                LoggerService.log_error(
                                    action="auto_accept_invitation_failed",
                                    user=user,
                                    error=str(e),
                                    details={"invitation_id": str(invitation.id)},
                                )
                                
                except Exception as e:
                    LoggerService.log_error(
                        action="auto_accept_invitations_check_failed",
                        user=user,
                        error=str(e),
                    )

                # Send welcome email
                try:
                    EmailService.send_welcome_email(user)
                except Exception as email_error:
                    LoggerService.log_error(
                        action="welcome_email_failed",
                        user=user,
                        ip_address=self.get_client_ip(request),
                        error=str(email_error),
                    )

                LoggerService.log_info(
                    action="user_registered",
                    user=user,
                    ip_address=self.get_client_ip(request),
                    details={
                        "email": user.email,
                        "username": user.username,
                        "auto_joined_organizations_count": pending_invitations_count,
                    },
                )

                user_serializer = UserSerializer(user)
                response_data = user_serializer.data
                
                # Add invitation acceptance info to response
                if auto_joined_organizations:
                    response_data["auto_joined_organizations"] = auto_joined_organizations
                    response_data["pending_invitations_accepted"] = pending_invitations_count
                    if auto_joined_organizations:
                        response_data["redirect_suggestion"] = (
                            f"/organizations/{auto_joined_organizations[0]['id']}/dashboard"
                        )
                
                return Response(response_data, status=status.HTTP_201_CREATED)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            LoggerService.log_error(
                action="user_registration_error",
                ip_address=self.get_client_ip(request),
                error=str(e),
            )
            return Response(
                {"error": f"Registration failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        operation_id="auth_login",
        summary="User Login",
        description="Authenticate user and return JWT tokens for API access",
        request=UserLoginSerializer,
        responses={
            200: inline_serializer(
                name="LoginResponse",
                fields={
                    "access": serializers.CharField(help_text="JWT access token"),
                    "refresh": serializers.CharField(help_text="JWT refresh token"),
                    "user": UserSerializer(),
                },
            ),
            400: inline_serializer(
                name="LoginError", fields={"error": serializers.CharField()}
            ),
        },
    )
    @action(detail=False, methods=["post"], url_path="login")
    @transaction.atomic
    def login(self, request):
        """Authenticate user and return JWT tokens."""
        try:
            serializer = UserLoginSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.validated_data["user"]

                # Create JWT tokens
                refresh = RefreshToken.for_user(user)
                access = refresh.access_token

                # Update last login
                user.last_login = timezone.now()
                user.save(update_fields=["last_login"])

                LoggerService.log_info(
                    action="user_login",
                    user=user,
                    ip_address=self.get_client_ip(request),
                    details={"user_agent": self.get_user_agent(request)},
                )

                user_serializer = UserSerializer(user)
                return Response(
                    {
                        "access": str(access),
                        "refresh": str(refresh),
                        "user": user_serializer.data,
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            LoggerService.log_error(
                action="user_login_error",
                ip_address=self.get_client_ip(request),
                error=str(e),
            )
            return Response(
                {"error": "Login failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        operation_id="auth_logout",
        summary="User Logout",
        description="Logout user and blacklist refresh token",
        request=inline_serializer(
            name="LogoutRequest",
            fields={
                "refresh": serializers.CharField(
                    help_text="JWT refresh token to blacklist"
                )
            },
        ),
        responses={
            200: inline_serializer(
                name="LogoutResponse", fields={"message": serializers.CharField()}
            )
        },
    )
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="logout",
    )
    @transaction.atomic
    def logout(self, request):
        """Logout user and blacklist tokens."""
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            LoggerService.log_info(
                action="user_logout",
                user=request.user,
                ip_address=self.get_client_ip(request),
            )

            return Response(
                {"message": "Logged out successfully"}, status=status.HTTP_200_OK
            )

        except Exception as e:
            LoggerService.log_error(
                action="user_logout_error",
                user=request.user,
                ip_address=self.get_client_ip(request),
                error=str(e),
            )
            return Response(
                {"error": "Logout failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        operation_id="auth_password_reset_request",
        summary="Request Password Reset",
        description=(
            "Send password reset email to user. **NEW:** Sends email via AWS SES with reset token (expires in 1 hour). "
            "Returns same success message even if email doesn't exist (security measure). "
            "Frontend should display: 'If an account exists with this email, a password reset link has been sent.'"
        ),
        request=PasswordResetRequestSerializer,
        responses={
            200: inline_serializer(
                name="PasswordResetRequestResponse",
                fields={"message": serializers.CharField(default="Password reset email sent")},
            )
        },
    )
    @action(detail=False, methods=["post"], url_path="password-reset-request")
    @transaction.atomic
    def password_reset_request(self, request):
        """Request password reset via email."""
        try:
            serializer = PasswordResetRequestSerializer(data=request.data)
            if serializer.is_valid():
                email = serializer.validated_data["email"]
                user = User.objects.get(email=email, is_active=True)

                # Generate reset token
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode()).hexdigest()

                # Create password reset token
                PasswordResetToken.objects.update_or_create(
                    user=user,
                    defaults={
                        "token": token_hash,
                        "expires_at": timezone.now() + timedelta(hours=1),
                        "is_used": False,
                    },
                )

                # Send password reset email
                try:
                    EmailService.send_password_reset_email(
                        user=user, reset_token=token, frontend_url=settings.FRONTEND_URL
                    )
                except Exception as email_error:
                    LoggerService.log_error(
                        action="password_reset_email_failed",
                        user=user,
                        ip_address=self.get_client_ip(request),
                        error=str(email_error),
                    )

                LoggerService.log_info(
                    action="password_reset_requested",
                    user=user,
                    ip_address=self.get_client_ip(request),
                )

                return Response(
                    {"message": "Password reset email sent"}, status=status.HTTP_200_OK
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            # Return success message even if user doesn't exist for security
            return Response(
                {"message": "Password reset email sent"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            LoggerService.log_error(
                action="password_reset_request_error",
                ip_address=self.get_client_ip(request),
                error=str(e),
            )
            return Response(
                {"error": "Password reset request failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        operation_id="auth_password_reset_confirm",
        summary="Confirm Password Reset",
        description="Reset password using token from email",
        request=PasswordResetConfirmSerializer,
        responses={
            200: inline_serializer(
                name="PasswordResetConfirmResponse",
                fields={"message": serializers.CharField()},
            )
        },
    )
    @action(detail=False, methods=["post"], url_path="password-reset-confirm")
    @transaction.atomic
    def password_reset_confirm(self, request):
        """Confirm password reset with token."""
        try:
            serializer = PasswordResetConfirmSerializer(data=request.data)
            if serializer.is_valid():
                token = serializer.validated_data["token"]
                new_password = serializer.validated_data["new_password"]

                # Hash the token to match stored hash
                token_hash = hashlib.sha256(token.encode()).hexdigest()

                # Find and validate token
                reset_token = PasswordResetToken.objects.get(
                    token=token_hash, is_used=False
                )

                if reset_token.is_expired:
                    return Response(
                        {"error": "Reset token has expired"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Update user password
                user = reset_token.user
                user.set_password(new_password)
                user.save()

                # Mark token as used
                reset_token.is_used = True
                reset_token.used_at = timezone.now()
                reset_token.save()

                LoggerService.log_info(
                    action="password_reset_completed",
                    user=user,
                    ip_address=self.get_client_ip(request),
                )

                return Response(
                    {"message": "Password reset successful"}, status=status.HTTP_200_OK
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except PasswordResetToken.DoesNotExist:
            return Response(
                {"error": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            LoggerService.log_error(
                action="password_reset_confirm_error",
                ip_address=self.get_client_ip(request),
                error=str(e),
            )
            return Response(
                {"error": "Password reset failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
