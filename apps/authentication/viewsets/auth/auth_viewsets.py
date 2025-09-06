from rest_framework import status, viewsets, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import login, logout
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
import secrets
import hashlib
from datetime import timedelta

from apps.authentication.models import User, UserProfile, UserSession, PasswordResetToken
from apps.authentication.serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserProfileSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)
from apps.logging.services import LoggerService


@extend_schema(tags=['Authentication'])
class AuthViewSet(viewsets.GenericViewSet):
    """
    Authentication operations including registration, login, logout, and password reset.
    """
    permission_classes = [permissions.AllowAny]
    # Provide a default serializer for schema generation
    serializer_class = UserSerializer
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def get_user_agent(self, request):
        return request.META.get('HTTP_USER_AGENT', '')

    @extend_schema(
        request=UserRegistrationSerializer,
        responses={201: UserSerializer}
    )
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def register(self, request):
        try:
            serializer = UserRegistrationSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save()
                
                # Create user session
                UserSession.objects.create(
                    user=user,
                    session_key=request.session.session_key or secrets.token_hex(20),
                    ip_address=self.get_client_ip(request),
                    user_agent=self.get_user_agent(request),
                    is_active=True
                )
                
                LoggerService.log_info(
                    action='user_registered',
                    user=user,
                    ip_address=self.get_client_ip(request),
                    details={
                        'email': user.email,
                        'username': user.username
                    }
                )
                
                user_serializer = UserSerializer(user)
                return Response(user_serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            LoggerService.log_error(
                action='user_registration_error',
                ip_address=self.get_client_ip(request),
                error=str(e)
            )
            return Response(
                {'error': 'Registration failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=UserLoginSerializer,
        responses={
            200: inline_serializer(
                name='LoginResponse',
                fields={
                    'access': serializers.CharField(),
                    'refresh': serializers.CharField(),
                    'user': UserSerializer()
                }
            )
        }
    )
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def login(self, request):
        try:
            serializer = UserLoginSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.validated_data['user']
                
                # Create JWT tokens
                refresh = RefreshToken.for_user(user)
                access = refresh.access_token
                
                # Update last login
                user.last_login = timezone.now()
                user.save(update_fields=['last_login'])
                
                # Create or update user session
                session_key = request.session.session_key or secrets.token_hex(20)
                user_session, created = UserSession.objects.get_or_create(
                    user=user,
                    session_key=session_key,
                    defaults={
                        'ip_address': self.get_client_ip(request),
                        'user_agent': self.get_user_agent(request),
                        'is_active': True,
                        'last_activity': timezone.now()
                    }
                )
                
                if not created:
                    user_session.ip_address = self.get_client_ip(request)
                    user_session.user_agent = self.get_user_agent(request)
                    user_session.is_active = True
                    user_session.last_activity = timezone.now()
                    user_session.save()
                
                LoggerService.log_info(
                    action='user_login',
                    user=user,
                    ip_address=self.get_client_ip(request),
                    details={
                        'session_id': user_session.id,
                        'user_agent': self.get_user_agent(request)
                    }
                )
                
                user_serializer = UserSerializer(user)
                return Response({
                    'access': str(access),
                    'refresh': str(refresh),
                    'user': user_serializer.data
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            LoggerService.log_error(
                action='user_login_error',
                ip_address=self.get_client_ip(request),
                error=str(e)
            )
            return Response(
                {'error': 'Login failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        responses={
            200: inline_serializer(
                name='LogoutResponse',
                fields={'message': serializers.CharField()}
            )
        }
    )
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    @transaction.atomic
    def logout(self, request):
        try:
            # Get refresh token from request
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
                
            # Deactivate user sessions
            UserSession.objects.filter(
                user=request.user,
                is_active=True
            ).update(
                is_active=False,
                logged_out_at=timezone.now()
            )
            
            LoggerService.log_info(
                action='user_logout',
                user=request.user,
                ip_address=self.get_client_ip(request)
            )
            
            return Response(
                {'message': 'Logged out successfully'},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            LoggerService.log_error(
                action='user_logout_error',
                user=request.user,
                ip_address=self.get_client_ip(request),
                error=str(e)
            )
            return Response(
                {'error': 'Logout failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={
            200: inline_serializer(
                name='PasswordResetRequestResponse',
                fields={'message': serializers.CharField()}
            )
        }
    )
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def password_reset_request(self, request):
        try:
            serializer = PasswordResetRequestSerializer(data=request.data)
            if serializer.is_valid():
                email = serializer.validated_data['email']
                user = User.objects.get(email=email, is_active=True)
                
                # Generate reset token
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                
                # Create or update password reset token
                reset_token, created = PasswordResetToken.objects.get_or_create(
                    user=user,
                    defaults={
                        'token': token_hash,
                        'expires_at': timezone.now() + timedelta(hours=1)
                    }
                )
                
                if not created:
                    reset_token.token = token_hash
                    reset_token.expires_at = timezone.now() + timedelta(hours=1)
                    reset_token.is_used = False
                    reset_token.save()
                
                # Send password reset email
                reset_url = f"{settings.FRONTEND_URL}/reset-password/{token}"
                send_mail(
                    subject='Password Reset Request',
                    message=f'Click here to reset your password: {reset_url}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                
                LoggerService.log_info(
                    action='password_reset_requested',
                    user=user,
                    ip_address=self.get_client_ip(request)
                )
                
                return Response(
                    {'message': 'Password reset email sent'},
                    status=status.HTTP_200_OK
                )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except User.DoesNotExist:
            # Return success message even if user doesn't exist for security
            return Response(
                {'message': 'Password reset email sent'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            LoggerService.log_error(
                action='password_reset_request_error',
                ip_address=self.get_client_ip(request),
                error=str(e)
            )
            return Response(
                {'error': 'Password reset request failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={
            200: inline_serializer(
                name='PasswordResetConfirmResponse',
                fields={'message': serializers.CharField()}
            )
        }
    )
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def password_reset_confirm(self, request):
        try:
            serializer = PasswordResetConfirmSerializer(data=request.data)
            if serializer.is_valid():
                token = serializer.validated_data['token']
                new_password = serializer.validated_data['new_password']
                
                # Hash the token to match stored hash
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                
                # Find and validate token
                reset_token = PasswordResetToken.objects.get(
                    token=token_hash,
                    is_used=False
                )
                
                if reset_token.is_expired:
                    return Response(
                        {'error': 'Reset token has expired'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Update user password
                user = reset_token.user
                user.set_password(new_password)
                user.save()
                
                # Mark token as used
                reset_token.is_used = True
                reset_token.used_at = timezone.now()
                reset_token.save()
                
                # Deactivate all user sessions
                UserSession.objects.filter(user=user, is_active=True).update(
                    is_active=False,
                    logged_out_at=timezone.now()
                )
                
                LoggerService.log_info(
                    action='password_reset_completed',
                    user=user,
                    ip_address=self.get_client_ip(request)
                )
                
                return Response(
                    {'message': 'Password reset successful'},
                    status=status.HTTP_200_OK
                )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except PasswordResetToken.DoesNotExist:
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            LoggerService.log_error(
                action='password_reset_confirm_error',
                ip_address=self.get_client_ip(request),
                error=str(e)
            )
            return Response(
                {'error': 'Password reset failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
