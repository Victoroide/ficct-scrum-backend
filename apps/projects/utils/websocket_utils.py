from datetime import datetime
from uuid import UUID

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def convert_uuids_to_strings(obj):
    """
    Recursively convert UUID objects to strings for msgpack serialization.
    
    Args:
        obj: Object to convert (dict, list, or primitive)
        
    Returns:
        Object with all UUIDs converted to strings
    """
    if isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: convert_uuids_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_uuids_to_strings(item) for item in obj]
    else:
        return obj


class BoardWebSocketNotifier:
    """Utility class to send WebSocket notifications for board events"""

    @staticmethod
    def send_issue_moved(board_id, issue_data, old_status_id, new_status_id, user):
        """
        Send notification when issue is moved between columns

        Args:
            board_id: UUID of the board
            issue_data: Serialized issue data
            old_status_id: Previous workflow status ID
            new_status_id: New workflow status ID
            user: User who performed the action
        """
        channel_layer = get_channel_layer()

        message = {
            "type": "issue_moved",
            "data": {
                "issue": issue_data,
                "from_status": str(old_status_id),
                "to_status": str(new_status_id),
                "timestamp": datetime.now().isoformat(),
                "user": {
                    "id": str(user.id),
                    "name": user.get_full_name() or user.username,
                },
            },
        }
        
        # Convert all UUIDs to strings for msgpack
        message = convert_uuids_to_strings(message)
        
        async_to_sync(channel_layer.group_send)(
            f"board_{board_id}",
            message,
        )

    @staticmethod
    def send_issue_created(board_id, issue_data, user):
        """
        Send notification when issue is created from board

        Args:
            board_id: UUID of the board
            issue_data: Serialized issue data
            user: User who created the issue
        """
        channel_layer = get_channel_layer()

        message = {
            "type": "issue_created",
            "data": {
                "issue": issue_data,
                "timestamp": datetime.now().isoformat(),
                "user": {
                    "id": str(user.id),
                    "name": user.get_full_name() or user.username,
                },
            },
        }
        
        # Convert all UUIDs to strings for msgpack
        message = convert_uuids_to_strings(message)
        
        async_to_sync(channel_layer.group_send)(
            f"board_{board_id}",
            message,
        )

    @staticmethod
    def send_issue_updated(board_id, issue_data, user, fields_changed=None):
        """
        Send notification when issue is updated

        Args:
            board_id: UUID of the board
            issue_data: Serialized issue data
            user: User who updated the issue
            fields_changed: List of field names that changed (optional)
        """
        channel_layer = get_channel_layer()

        message = {
            "type": "issue_updated",
            "data": {
                "issue": issue_data,
                "fields_changed": fields_changed or [],
                "timestamp": datetime.now().isoformat(),
                "user": {
                    "id": str(user.id),
                    "name": user.get_full_name() or user.username,
                },
            },
        }
        
        # Convert all UUIDs to strings for msgpack
        message = convert_uuids_to_strings(message)
        
        async_to_sync(channel_layer.group_send)(
            f"board_{board_id}",
            message,
        )

    @staticmethod
    def send_issue_deleted(board_id, issue_id, issue_key, user):
        """
        Send notification when issue is deleted

        Args:
            board_id: UUID of the board
            issue_id: UUID of deleted issue
            issue_key: Key of deleted issue
            user: User who deleted the issue
        """
        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            f"board_{board_id}",
            {
                "type": "issue_deleted",
                "data": {
                    "issue_id": str(issue_id),
                    "issue_key": issue_key,
                    "timestamp": datetime.now().isoformat(),
                    "user": {
                        "id": str(user.id),
                        "name": user.get_full_name() or user.username,
                    },
                },
            },
        )

    @staticmethod
    def send_column_created(board_id, column_data, user):
        """
        Send notification when column is created

        Args:
            board_id: UUID of the board
            column_data: Serialized column data
            user: User who created the column
        """
        channel_layer = get_channel_layer()

        message = {
            "type": "column_created",
            "data": {
                "column": column_data,
                "timestamp": datetime.now().isoformat(),
                "user": {
                    "id": str(user.id),
                    "name": user.get_full_name() or user.username,
                },
            },
        }
        
        # Convert all UUIDs to strings for msgpack
        message = convert_uuids_to_strings(message)
        
        async_to_sync(channel_layer.group_send)(
            f"board_{board_id}",
            message,
        )

    @staticmethod
    def send_column_updated(board_id, column_data, user):
        """
        Send notification when column is updated

        Args:
            board_id: UUID of the board
            column_data: Serialized column data
            user: User who updated the column
        """
        channel_layer = get_channel_layer()

        message = {
            "type": "column_updated",
            "data": {
                "column": column_data,
                "timestamp": datetime.now().isoformat(),
                "user": {
                    "id": str(user.id),
                    "name": user.get_full_name() or user.username,
                },
            },
        }
        
        # Convert all UUIDs to strings for msgpack
        message = convert_uuids_to_strings(message)
        
        async_to_sync(channel_layer.group_send)(
            f"board_{board_id}",
            message,
        )

    @staticmethod
    def send_column_deleted(board_id, column_id, column_name, user):
        """
        Send notification when column is deleted

        Args:
            board_id: UUID of the board
            column_id: UUID of deleted column
            column_name: Name of deleted column
            user: User who deleted the column
        """
        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            f"board_{board_id}",
            {
                "type": "column_deleted",
                "data": {
                    "column_id": str(column_id),
                    "column_name": column_name,
                    "timestamp": datetime.now().isoformat(),
                    "user": {
                        "id": str(user.id),
                        "name": user.get_full_name() or user.username,
                    },
                },
            },
        )
