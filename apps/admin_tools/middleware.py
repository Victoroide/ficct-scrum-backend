"""
Performance monitoring middleware.

Tracks API request performance and logs slow requests.
"""

import logging
import time

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Monitor API request performance and log slow requests.

    Adds X-Response-Time header to all responses and logs warnings
    for requests exceeding performance thresholds.
    """

    def process_request(self, request):
        """Record request start time."""
        request._start_time = time.time()
        request._db_queries_start = self._get_db_query_count()

    def process_response(self, request, response):
        """Calculate and log request duration."""
        if not hasattr(request, "_start_time"):
            return response

        # Calculate metrics
        duration = time.time() - request._start_time
        db_queries = self._get_db_query_count() - request._db_queries_start

        # Add performance headers
        response["X-Response-Time"] = f"{duration:.3f}s"
        response["X-DB-Queries"] = str(db_queries)

        # Log slow requests (> 2 seconds)
        if duration > 2.0:
            logger.warning(
                f"SLOW REQUEST: {request.method} {request.path} "
                f"took {duration:.2f}s with {db_queries} DB queries - "
                f"Status: {response.status_code}"
            )

        # Log requests with many DB queries (> 50)
        elif db_queries > 50:
            logger.warning(
                f"HIGH DB QUERIES: {request.method} {request.path} "
                f"executed {db_queries} queries in {duration:.2f}s - "
                f"Status: {response.status_code} - Possible N+1 issue"
            )

        # Log info for normal requests in debug mode
        elif logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"{request.method} {request.path} - "
                f"{duration:.3f}s - {db_queries} queries - "
                f"Status: {response.status_code}"
            )

        return response

    def _get_db_query_count(self):
        """Get current database query count."""
        try:
            from django.db import connection

            return len(connection.queries)
        except Exception:
            return 0


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Log all incoming API requests.

    Useful for audit trails and debugging.
    """

    def process_request(self, request):
        """Log incoming request."""
        if request.path.startswith("/api/"):
            logger.info(
                f"API Request: {request.method} {request.path} "
                f"from {self._get_client_ip(request)} - "
                f"User: {getattr(request.user, 'email', 'Anonymous')}"
            )

    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR", "unknown")
        return ip
