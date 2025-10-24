"""
WebSocket authentication middleware for JWT tokens
"""
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

User = get_user_model()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using JWT tokens.
    
    Extracts token from query parameter (?token=...) and authenticates the user.
    If token is invalid or missing, user remains AnonymousUser.
    """
    
    async def __call__(self, scope, receive, send):
        # Parse query string to get token
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]
        
        # Authenticate user with token
        scope["user"] = await self.get_user_from_token(token)
        
        return await super().__call__(scope, receive, send)
    
    @database_sync_to_async
    def get_user_from_token(self, token):
        """
        Authenticate user from JWT token.
        
        Args:
            token: JWT access token string
            
        Returns:
            User object if token is valid, AnonymousUser otherwise
        """
        if not token:
            return AnonymousUser()
        
        try:
            # Validate and decode token
            access_token = AccessToken(token)
            user_id = access_token.get("user_id")
            
            if not user_id:
                return AnonymousUser()
            
            # Get user from database
            user = User.objects.get(id=user_id, is_active=True)
            return user
            
        except (InvalidToken, TokenError, User.DoesNotExist) as e:
            # Token is invalid, expired, or user doesn't exist
            # Log error for debugging (optional)
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"WebSocket JWT authentication failed: {str(e)}")
            return AnonymousUser()
        except Exception as e:
            # Unexpected error
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"WebSocket JWT authentication error: {str(e)}")
            return AnonymousUser()
