from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.authentication.models import User, UserProfile
from apps.authentication.serializers import (
    UserSerializer,
    UserProfileSerializer,
    PasswordChangeSerializer
)
from apps.logging.services import LoggerService


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related('profile').filter(is_active=True)
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.action == 'me':
            return User.objects.select_related('profile').filter(id=self.request.user.id)
        return super().get_queryset()

    @extend_schema(responses={200: UserSerializer})
    @action(detail=False, methods=['get'])
    def me(self, request):
        try:
            serializer = self.get_serializer(request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            LoggerService.log_error(
                action='get_user_profile_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to retrieve user profile'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=UserSerializer,
        responses={200: UserSerializer}
    )
    @action(detail=False, methods=['patch'])
    @transaction.atomic
    def update_profile(self, request):
        try:
            serializer = self.get_serializer(
                request.user,
                data=request.data,
                partial=True
            )
            if serializer.is_valid():
                user = serializer.save()
                
                LoggerService.log_info(
                    action='user_profile_updated',
                    user=user,
                    details={'updated_fields': list(request.data.keys())}
                )
                
                return Response(serializer.data, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            LoggerService.log_error(
                action='update_user_profile_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to update user profile'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=PasswordChangeSerializer,
        responses={
            200: inline_serializer(
                name='PasswordChangeResponse',
                fields={'message': serializers.CharField()}
            )
        }
    )
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def change_password(self, request):
        try:
            serializer = PasswordChangeSerializer(
                data=request.data,
                context={'request': request}
            )
            if serializer.is_valid():
                serializer.save()
                
                LoggerService.log_info(
                    action='password_changed',
                    user=request.user
                )
                
                return Response(
                    {'message': 'Password changed successfully'},
                    status=status.HTTP_200_OK
                )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            LoggerService.log_error(
                action='change_password_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to change password'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Guard for Spectacular schema generation
        if getattr(self, "swagger_fake_view", False):
            return UserProfile.objects.none()
        return UserProfile.objects.select_related('user').filter(user=self.request.user)

    @extend_schema(responses={200: UserProfileSerializer})
    @action(detail=False, methods=['get'])
    def me(self, request):
        try:
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            LoggerService.log_error(
                action='get_user_profile_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to retrieve user profile'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=UserProfileSerializer,
        responses={200: UserProfileSerializer}
    )
    @action(detail=False, methods=['patch'])
    @transaction.atomic
    def update_profile(self, request):
        try:
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            serializer = self.get_serializer(
                profile,
                data=request.data,
                partial=True
            )
            if serializer.is_valid():
                profile = serializer.save()
                
                LoggerService.log_info(
                    action='user_profile_updated',
                    user=request.user,
                    details={'updated_fields': list(request.data.keys())}
                )
                
                return Response(serializer.data, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            LoggerService.log_error(
                action='update_user_profile_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to update user profile'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
