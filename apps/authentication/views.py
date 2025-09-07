from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout
from django.core.exceptions import ObjectDoesNotExist
from apps.authentication.serializers import UserSerializer
from drf_spectacular.utils import extend_schema

class LoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = UserSerializer
    
    @extend_schema(
        operation_id="auth_login_token",
        summary="Token-based Login",
        description="Legacy token-based authentication endpoint",
        responses={200: UserSerializer}
    )
    def post(self, request, *args, **kwargs):
        from django.contrib.auth import authenticate
        from rest_framework.authtoken.models import Token
        
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response(
                {'error': 'Please provide both email and password'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                token, created = Token.objects.get_or_create(user=user)
                serializer = UserSerializer(user)
                return Response({
                    'token': token.key,
                    'user': serializer.data
                })
            else:
                return Response(
                    {'error': 'Account is disabled'}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
        else:
            return Response(
                {'error': 'Invalid credentials'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        try:
            # Delete the token if it exists
            request.user.auth_token.delete()
        except (AttributeError, ObjectDoesNotExist):
            pass
        
        logout(request)
        return Response(
            {'success': 'Successfully logged out'}, 
            status=status.HTTP_200_OK
        )

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    
    @extend_schema(
        operation_id="auth_current_user",
        summary="Get Current User",
        description="Retrieve authenticated user information",
        responses={200: UserSerializer}
    )
    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
