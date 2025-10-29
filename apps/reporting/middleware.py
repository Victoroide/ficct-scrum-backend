"""
Middleware to track user and request for ActivityLog signals.

This middleware injects _current_user and _current_request into model instances
during save operations, allowing signals to access this information.
"""

import threading

# Thread-local storage for current user and request
_thread_locals = threading.local()


def get_current_user():
    """Get current user from thread-local storage."""
    return getattr(_thread_locals, 'user', None)


def get_current_request():
    """Get current request from thread-local storage."""
    return getattr(_thread_locals, 'request', None)


class ActivityLogMiddleware:
    """
    Middleware to store current user and request in thread-local storage.
    
    This allows signals to access the current user and request when creating
    ActivityLog entries, even though signals don't have direct access to the request.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Store user and request in thread-local
        _thread_locals.user = getattr(request, 'user', None)
        _thread_locals.request = request
        
        # Process request
        response = self.get_response(request)
        
        # Clean up thread-local after request
        if hasattr(_thread_locals, 'user'):
            del _thread_locals.user
        if hasattr(_thread_locals, 'request'):
            del _thread_locals.request
        
        return response


# Monkey patch Django models to inject current user/request before save
from django.db.models import Model

_original_save = Model.save


def save_with_user(self, *args, **kwargs):
    """Override save to inject current user and request."""
    user = get_current_user()
    request = get_current_request()
    
    if user and user.is_authenticated:
        self._current_user = user
        self._current_request = request
        
        # Track field changes for updates
        if self.pk:
            try:
                old_instance = self.__class__.objects.get(pk=self.pk)
                changes = {}
                for field in self._meta.fields:
                    field_name = field.name
                    if field_name in ['id', 'created_at', 'updated_at']:
                        continue
                    old_value = getattr(old_instance, field_name, None)
                    new_value = getattr(self, field_name, None)
                    if old_value != new_value:
                        changes[field_name] = {
                            'old': str(old_value) if old_value is not None else None,
                            'new': str(new_value) if new_value is not None else None
                        }
                self._field_changes = changes
            except self.__class__.DoesNotExist:
                pass
    
    return _original_save(self, *args, **kwargs)


Model.save = save_with_user
