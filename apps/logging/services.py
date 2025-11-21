import logging
import traceback
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Alert, AlertRule, AuditLog, ErrorLog, SystemLog

User = get_user_model()
logger = logging.getLogger(__name__)


class LoggerService:
    @staticmethod
    @transaction.atomic
    def log_info(
        action: str,
        user: Optional[User] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        content_object: Any = None,
    ):
        try:
            SystemLog.objects.create(
                level="INFO",
                action=action,
                action_type="system_event",
                message=f"Action: {action}",
                user=user,
                ip_address=ip_address,
                metadata=details or {},
                content_object=content_object,
            )
        except Exception as e:
            logger.error(f"Failed to log info: {str(e)}")

    @staticmethod
    @transaction.atomic
    def log_warning(
        action: str,
        user: Optional[User] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        content_object: Any = None,
    ):
        try:
            SystemLog.objects.create(
                level="WARNING",
                action=action,
                action_type="system_event",
                message=f"Warning: {action}",
                user=user,
                ip_address=ip_address,
                metadata=details or {},
                content_object=content_object,
            )
        except Exception as e:
            logger.error(f"Failed to log warning: {str(e)}")

    @staticmethod
    @transaction.atomic
    def log_error(
        action: str,
        error: str,
        user: Optional[User] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        content_object: Any = None,
    ):
        try:
            stack_trace = traceback.format_exc()

            SystemLog.objects.create(
                level="ERROR",
                action=action,
                action_type="error",
                message=f"Error in {action}: {error}",
                user=user,
                ip_address=ip_address,
                metadata=details or {},
                stack_trace=stack_trace,
                content_object=content_object,
            )

            # Also create an ErrorLog entry
            ErrorLog.objects.create(
                error_type=action,
                error_message=error,
                stack_trace=stack_trace,
                user=user,
                ip_address=ip_address,
                request_data=details or {},
                severity="medium",
            )

        except Exception as e:
            logger.error(f"Failed to log error: {str(e)}")

    @staticmethod
    @transaction.atomic
    def log_critical(
        action: str,
        error: str,
        user: Optional[User] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        content_object: Any = None,
    ):
        try:
            stack_trace = traceback.format_exc()

            SystemLog.objects.create(
                level="CRITICAL",
                action=action,
                action_type="error",
                message=f"Critical error in {action}: {error}",
                user=user,
                ip_address=ip_address,
                metadata=details or {},
                stack_trace=stack_trace,
                content_object=content_object,
            )

            # Create critical ErrorLog entry
            error_log = ErrorLog.objects.create(
                error_type=action,
                error_message=error,
                stack_trace=stack_trace,
                user=user,
                ip_address=ip_address,
                request_data=details or {},
                severity="critical",
            )

            # Check for alert rules and trigger alerts
            LoggerService._check_alert_rules("error_count", {"error_log": error_log})

        except Exception as e:
            logger.error(f"Failed to log critical error: {str(e)}")

    @staticmethod
    @transaction.atomic
    def log_api_request(
        method: str,
        path: str,
        user: Optional[User] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_data: Optional[Dict[str, Any]] = None,
        response_status: Optional[int] = None,
        execution_time: Optional[float] = None,
    ):
        try:
            SystemLog.objects.create(
                level="INFO",
                action=f"{method} {path}",
                action_type="api_request",
                message=f"API Request: {method} {path}",
                user=user,
                ip_address=ip_address,
                user_agent=user_agent or "",
                request_method=method,
                request_path=path,
                request_data=request_data or {},
                response_status=response_status,
                execution_time=execution_time,
            )
        except Exception as e:
            logger.error(f"Failed to log API request: {str(e)}")

    @staticmethod
    @transaction.atomic
    def log_audit(
        user: User,
        action: str,
        resource_type: str,
        content_object: Any = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ):
        try:
            resource_id = None
            if content_object and hasattr(content_object, "id"):
                resource_id = str(content_object.id)

            AuditLog.objects.create(
                user=user,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                content_object=content_object,
                old_values=old_values or {},
                new_values=new_values or {},
                ip_address=ip_address or "",
                user_agent=user_agent or "",
                session_id=session_id or "",
                additional_data=additional_data or {},
            )
        except Exception as e:
            logger.error(f"Failed to log audit: {str(e)}")

    @staticmethod
    @transaction.atomic
    def log_security_event(
        action: str,
        user: Optional[User] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "medium",
    ):
        try:
            SystemLog.objects.create(
                level="WARNING" if severity in ["low", "medium"] else "CRITICAL",
                action=action,
                action_type="security_event",
                message=f"Security event: {action}",
                user=user,
                ip_address=ip_address,
                metadata=details or {},
            )

            # Check for security-related alert rules
            LoggerService._check_alert_rules(
                "security_event",
                {
                    "action": action,
                    "user": user,
                    "ip_address": ip_address,
                    "severity": severity,
                },
            )

        except Exception as e:
            logger.error(f"Failed to log security event: {str(e)}")

    @staticmethod
    def _check_alert_rules(condition_type: str, data: Dict[str, Any]):
        try:
            active_rules = AlertRule.objects.filter(
                condition_type=condition_type, status="active", is_active=True
            )

            for rule in active_rules:
                if LoggerService._evaluate_alert_condition(rule, data):
                    LoggerService._trigger_alert(rule, data)

        except Exception as e:
            logger.error(f"Failed to check alert rules: {str(e)}")

    @staticmethod
    def _evaluate_alert_condition(rule: AlertRule, data: Dict[str, Any]) -> bool:
        try:
            config = rule.condition_config

            if rule.condition_type == "error_count":
                threshold = config.get("threshold", 10)
                time_window = config.get("time_window_minutes", 60)

                from datetime import timedelta

                since = timezone.now() - timedelta(minutes=time_window)

                error_count = ErrorLog.objects.filter(
                    created_at__gte=since, severity__in=["high", "critical"]
                ).count()

                return error_count >= threshold

            elif rule.condition_type == "security_event":
                severity_threshold = config.get("severity_threshold", "medium")
                event_severity = data.get("severity", "low")

                severity_levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
                return severity_levels.get(event_severity, 1) >= severity_levels.get(
                    severity_threshold, 2
                )

            return False

        except Exception as e:
            logger.error(f"Failed to evaluate alert condition: {str(e)}")
            return False

    @staticmethod
    @transaction.atomic
    def _trigger_alert(rule: AlertRule, data: Dict[str, Any]):
        try:
            # Check if there's already an active alert for this rule
            existing_alert = Alert.objects.filter(rule=rule, status="triggered").first()

            if existing_alert:
                return  # Don't create duplicate alerts

            message = f"Alert triggered: {rule.name}"
            if rule.condition_type == "error_count":
                message += " - Error threshold exceeded"
            elif rule.condition_type == "security_event":
                message += (
                    f" - Security event detected: {data.get('action', 'Unknown')}"
                )

            Alert.objects.create(rule=rule, message=message, details=data)

            # TODO: Implement notification sending based on rule.notification_channels

        except Exception as e:
            logger.error(f"Failed to trigger alert: {str(e)}")

    @staticmethod
    def get_system_health_metrics():
        try:
            from datetime import timedelta

            now = timezone.now()
            last_24h = now - timedelta(hours=24)
            last_hour = now - timedelta(hours=1)

            return {
                "total_logs_24h": SystemLog.objects.filter(
                    created_at__gte=last_24h
                ).count(),
                "error_logs_24h": SystemLog.objects.filter(
                    level__in=["ERROR", "CRITICAL"], created_at__gte=last_24h
                ).count(),
                "error_logs_1h": SystemLog.objects.filter(
                    level__in=["ERROR", "CRITICAL"], created_at__gte=last_hour
                ).count(),
                "active_alerts": Alert.objects.filter(status="triggered").count(),
                "critical_errors_24h": ErrorLog.objects.filter(
                    severity="critical", created_at__gte=last_24h
                ).count(),
                "unique_users_24h": SystemLog.objects.filter(
                    created_at__gte=last_24h, user__isnull=False
                )
                .values("user")
                .distinct()
                .count(),
            }
        except Exception as e:
            logger.error(f"Failed to get system health metrics: {str(e)}")
            return {}
