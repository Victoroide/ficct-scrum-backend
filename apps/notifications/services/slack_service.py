"""
Slack integration service for sending notifications to Slack.

Supports webhook-based notifications to channels and DMs.
"""

import logging
from typing import Any, Dict, Optional

import requests
from decouple import config

logger = logging.getLogger(__name__)


class SlackService:
    """Service for Slack integrations."""

    def __init__(self):
        """Initialize Slack service."""
        self.default_webhook_url = config("SLACK_WEBHOOK_URL_DEFAULT", default="")

    def validate_webhook_url(self, webhook_url: str) -> bool:
        """Validate Slack webhook URL format."""
        if not webhook_url:
            return False
        if not webhook_url.startswith('https://hooks.slack.com/'):
            return False
        return True

    def send_notification(
        self,
        title: str,
        message: str,
        channel: Optional[str] = None,
        link: Optional[str] = None,
        webhook_url: Optional[str] = None,
        color: str = "#36a64f",
        fields: Optional[list] = None,
    ) -> bool:
        """
        Send notification to Slack channel.

        Args:
            title: Notification title
            message: Notification message
            channel: Optional channel override
            link: Optional link to include
            webhook_url: Optional webhook URL (uses default if not provided)
            color: Color for attachment sidebar

        Returns:
            True if successful
        """
        try:
            url = webhook_url or self.default_webhook_url
            
            if not url:
                logger.warning("No Slack webhook URL configured")
                return False
            
            payload = self._build_payload(title, message, link, channel, color, fields)
            
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            
            if response.status_code == 200:
                logger.info(f"Slack notification sent: {title}")
                return True
            else:
                logger.error(f"Slack API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.exception(f"Error sending Slack notification: {str(e)}")
            return False

    def send_issue_notification(
        self, issue_data: Dict[str, Any], action: str, webhook_url: Optional[str] = None
    ) -> bool:
        """
        Send issue-related notification to Slack.

        Args:
            issue_data: Issue data dictionary
            action: Action performed (created, updated, etc.)
            webhook_url: Optional webhook URL

        Returns:
            True if successful
        """
        try:
            issue_key = f"{issue_data.get('project_key', '')}-{issue_data.get('key', '')}"
            title = f"Issue {action}: {issue_key}"
            message = issue_data.get("title", "")
            
            # Build rich message
            fields = []
            
            if issue_data.get("assignee"):
                fields.append({
                    "title": "Assignee",
                    "value": issue_data["assignee"],
                    "short": True,
                })
            
            if issue_data.get("priority"):
                fields.append({
                    "title": "Priority",
                    "value": issue_data["priority"],
                    "short": True,
                })
            
            if issue_data.get("status"):
                fields.append({
                    "title": "Status",
                    "value": issue_data["status"],
                    "short": True,
                })
            
            payload = {
                "text": title,
                "attachments": [
                    {
                        "color": self._get_color_for_action(action),
                        "title": message,
                        "title_link": issue_data.get("link", ""),
                        "fields": fields,
                        "footer": "FICCT-SCRUM",
                        "ts": issue_data.get("timestamp", ""),
                    }
                ],
            }
            
            url = webhook_url or self.default_webhook_url
            if not url:
                return False
            
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            logger.exception(f"Error sending issue notification to Slack: {str(e)}")
            return False

    def send_anomaly_alert(
        self, anomaly_data: Dict[str, Any], webhook_url: Optional[str] = None
    ) -> bool:
        """
        Send anomaly detection alert to Slack.

        Args:
            anomaly_data: Anomaly data dictionary
            webhook_url: Optional webhook URL

        Returns:
            True if successful
        """
        try:
            severity = anomaly_data.get("severity", "medium")
            color = self._get_color_for_severity(severity)
            
            title = f"⚠️ Anomaly Detected: {anomaly_data.get('type', 'Unknown')}"
            message = anomaly_data.get("description", "")
            
            suggestions = anomaly_data.get("mitigation_suggestions", [])
            if suggestions:
                message += "\n\n*Suggested Actions:*\n"
                message += "\n".join(f"• {s}" for s in suggestions)
            
            return self.send_notification(
                title=title,
                message=message,
                link=anomaly_data.get("link"),
                webhook_url=webhook_url,
                color=color,
            )
            
        except Exception as e:
            logger.exception(f"Error sending anomaly alert to Slack: {str(e)}")
            return False

    def test_webhook(self, webhook_url: str) -> bool:
        """
        Test Slack webhook configuration.

        Args:
            webhook_url: Webhook URL to test

        Returns:
            True if webhook is valid
        """
        try:
            payload = {
                "text": "✅ FICCT-SCRUM Slack integration test successful!",
                "attachments": [
                    {
                        "color": "#36a64f",
                        "text": "Your Slack notifications are configured correctly.",
                    }
                ],
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            logger.exception(f"Error testing Slack webhook: {str(e)}")
            return False

    def _build_payload(
        self,
        title: str,
        message: str,
        link: Optional[str],
        channel: Optional[str],
        color: str,
        fields: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Build Slack message payload."""
        payload = {"text": title}
        
        if channel:
            payload["channel"] = channel
        
        attachment = {
            "color": color,
            "text": message,
        }
        
        if link:
            attachment["title_link"] = link
        
        if fields:
            attachment["fields"] = fields
        
        payload["attachments"] = [attachment]
        
        return payload

    def _get_color_for_action(self, action: str) -> str:
        """Get color code for action type."""
        colors = {
            "created": "#36a64f",  # Green
            "updated": "#2196F3",  # Blue
            "deleted": "#f44336",  # Red
            "completed": "#4CAF50",  # Success green
        }
        return colors.get(action, "#808080")  # Default gray

    def _get_color_for_severity(self, severity: str) -> str:
        """Get color code for severity level."""
        colors = {
            "low": "#2196F3",  # Blue
            "medium": "#FF9800",  # Orange
            "high": "#f44336",  # Red
            "critical": "#D32F2F",  # Dark red
        }
        return colors.get(severity, "#808080")
