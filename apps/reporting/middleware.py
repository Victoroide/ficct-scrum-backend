"""
Middleware to track user and request for ActivityLog.

Stores current user and request in thread-local storage for access by utility functions.
"""

import threading

# Thread-local storage for current user and request
_thread_locals = threading.local()


def get_current_user():
    """Get current user from thread-local storage."""
    return getattr(_thread_locals, "user", None)


def get_current_request():
    """Get current request from thread-local storage."""
    return getattr(_thread_locals, "request", None)


class ActivityLogMiddleware:
    """
    Middleware to store current user and request in thread-local storage.

    This allows utility functions to access the current user and request
    without passing them explicitly through all function calls.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Store user and request in thread-local
        _thread_locals.user = getattr(request, "user", None)
        _thread_locals.request = request

        # Process request
        response = self.get_response(request)

        # Clean up thread-local after request
        if hasattr(_thread_locals, "user"):
            del _thread_locals.user
        if hasattr(_thread_locals, "request"):
            del _thread_locals.request

        return response
