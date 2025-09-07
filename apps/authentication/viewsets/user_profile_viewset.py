from rest_framework import viewsets, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from drf_spectacular.utils import extend_schema, inline_serializer
from apps.authentication.models import UserProfile
from apps.authentication.serializers import UserProfileSerializer
from apps.logging.services import LoggerService


@extend_schema(tags=['Authentication'])
class UserProfileViewSet(viewsets.ModelViewSet):
    """
    User profile management operations including avatar uploads and personal information.
    Provides comprehensive profile management with S3 integration for avatar storage.
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Users can only see their own profile unless they are staff."""
        if self.request.user.is_staff:
            return UserProfile.objects.all()
        return UserProfile.objects.filter(user=self.request.user)
    
    @extend_schema(
        operation_id="profiles_create",
        summary="Create User Profile",
        description="Create a new user profile with personal information and avatar",
        request=UserProfileSerializer,
        responses={
            201: UserProfileSerializer,
            400: "Validation errors",
            500: "Server error"
        }
    )
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a new user profile."""
        try:
            response = super().create(request, *args, **kwargs)
            LoggerService.log_info(
                action='user_profile_created',
                user=request.user,
                ip_address=request.META.get('REMOTE_ADDR'),
                details={'user_id': request.user.id}
            )
            return response
        except Exception as e:
            LoggerService.log_error(
                action='user_profile_creation_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Profile creation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        operation_id="profiles_update",
        summary="Update User Profile", 
        description="Update user profile information including avatar upload",
        request=UserProfileSerializer,
        responses={
            200: UserProfileSerializer,
            400: "Validation errors",
            403: "Permission denied",
            500: "Server error"
        }
    )
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update user profile information."""
        try:
            # Ensure user can only update their own profile
            profile = self.get_object()
            if profile.user != request.user and not request.user.is_staff:
                return Response(
                    {'error': 'Permission denied'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
                
            response = super().update(request, *args, **kwargs)
            LoggerService.log_info(
                action='user_profile_updated',
                user=request.user,
                ip_address=request.META.get('REMOTE_ADDR'),
                details={
                    'profile_id': profile.id,
                    'updated_fields': list(request.data.keys())
                }
            )
            return response
        except Exception as e:
            LoggerService.log_error(
                action='user_profile_update_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Profile update failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    @extend_schema(
        operation_id="profiles_me",
        summary="Get Current User Profile",
        description="Retrieve the current user's profile information",
        responses={200: UserProfileSerializer}
    )
    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        """Get current user's profile."""
        try:
            profile = UserProfile.objects.get(user=request.user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except UserProfile.DoesNotExist:
            return Response(
                {'error': 'Profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
    @extend_schema(
        operation_id="profiles_upload_avatar",
        summary="Upload Avatar",
        description="Upload or update user avatar image",
        request=inline_serializer(
            name='AvatarUpload',
            fields={'avatar': serializers.ImageField(help_text="Avatar image file")}
        ),
        responses={
            200: UserProfileSerializer,
            400: "Invalid image file",
            404: "Profile not found"
        }
    )
    @action(detail=False, methods=['post'], url_path='upload-avatar')
    @transaction.atomic
    def upload_avatar(self, request):
        """Upload user avatar image."""
        try:
            profile = UserProfile.objects.get(user=request.user)
            
            if 'avatar' not in request.FILES:
                return Response(
                    {'error': 'No avatar file provided'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            profile.avatar = request.FILES['avatar']
            profile.save()
            
            LoggerService.log_info(
                action='avatar_uploaded',
                user=request.user,
                ip_address=request.META.get('REMOTE_ADDR'),
                details={'profile_id': profile.id}
            )
            
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
            
        except UserProfile.DoesNotExist:
            return Response(
                {'error': 'Profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            LoggerService.log_error(
                action='avatar_upload_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Avatar upload failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
