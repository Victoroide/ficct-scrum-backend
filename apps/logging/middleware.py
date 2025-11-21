import time

from django.contrib.auth import get_user_model
from django.utils.deprecation import MiddlewareMixin

from .services import LoggerService

User = get_user_model()


class LoggingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.start_time = time.time()
        return None

    def process_response(self, request, response):
        try:
            # Calculate execution time
            execution_time = time.time() - getattr(request, "start_time", time.time())

            # Get client IP
            ip_address = self.get_client_ip(request)

            # Get user agent
            user_agent = request.META.get("HTTP_USER_AGENT", "")

            # Get request data (be careful with sensitive data)
            request_data = {}
            if hasattr(request, "data") and request.method in ["POST", "PUT", "PATCH"]:
                request_data = self.sanitize_request_data(request.data)
            elif request.method == "GET":
                request_data = dict(request.GET)

            # Log API request
            LoggerService.log_api_request(
                method=request.method,
                path=request.path,
                user=request.user if request.user.is_authenticated else None,
                ip_address=ip_address,
                user_agent=user_agent,
                request_data=request_data,
                response_status=response.status_code,
                execution_time=execution_time,
            )

            # Log security events for suspicious activity
            if response.status_code == 401:
                LoggerService.log_security_event(
                    action="unauthorized_access_attempt",
                    user=request.user if request.user.is_authenticated else None,
                    ip_address=ip_address,
                    details={
                        "path": request.path,
                        "method": request.method,
                        "user_agent": user_agent,
                    },
                    severity="medium",
                )
            elif response.status_code == 403:
                LoggerService.log_security_event(
                    action="forbidden_access_attempt",
                    user=request.user if request.user.is_authenticated else None,
                    ip_address=ip_address,
                    details={
                        "path": request.path,
                        "method": request.method,
                        "user_agent": user_agent,
                    },
                    severity="high",
                )

        except Exception as e:
            # Don't let logging errors break the response
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Logging middleware error: {str(e)}")

        return response

    def process_exception(self, request, exception):
        try:
            ip_address = self.get_client_ip(request)

            LoggerService.log_error(
                action="unhandled_exception",
                error=str(exception),
                user=request.user if request.user.is_authenticated else None,
                ip_address=ip_address,
                details={
                    "path": request.path,
                    "method": request.method,
                    "exception_type": type(exception).__name__,
                },
            )
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Exception logging error: {str(e)}")

        return None

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def sanitize_request_data(self, data):
        """Remove sensitive data from request logging"""
        if isinstance(data, dict):
            sanitized = {}
            sensitive_fields = ["password", "token", "secret", "key", "authorization"]

            for key, value in data.items():
                if any(field in key.lower() for field in sensitive_fields):
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = value
            return sanitized
        return data
