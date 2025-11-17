import json

from django.contrib.auth import get_user_model

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

User = get_user_model()


class BoardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket Consumer for Board real-time updates.

    Handles:
    - User connection/disconnection to board
    - Broadcasting issue movements
    - Broadcasting issue creation/updates/deletion
    - Broadcasting column changes
    """

    async def connect(self):
        import logging

        logger = logging.getLogger(__name__)

        self.board_id = self.scope["url_route"]["kwargs"]["board_id"]
        self.room_group_name = f"board_{self.board_id}"
        self.user = self.scope["user"]

        # Diagnostic logging
        logger.info(f"[WS CONSUMER] Connection attempt to board {self.board_id}")
        logger.info(f"[WS CONSUMER] User: {self.user}")
        logger.info(f"[WS CONSUMER] User authenticated: {self.user.is_authenticated}")
        if self.user.is_authenticated:
            logger.info(f"[WS CONSUMER] User ID: {self.user.id}")
            logger.info(f"[WS CONSUMER] User username: {self.user.username}")

        if not self.user.is_authenticated:
            logger.warning(
                f"[WS CONSUMER] Rejecting connection: User not authenticated"
            )
            await self.close()
            return

        logger.info(f"[WS CONSUMER] Checking board access permissions...")
        has_permission = await self.check_board_access()
        logger.info(f"[WS CONSUMER] Board access permission: {has_permission}")

        if not has_permission:
            logger.warning(
                f"[WS CONSUMER] Rejecting connection: User does not have board access"
            )
            await self.close()
            return

        logger.info(f"[WS CONSUMER] Adding user to group {self.room_group_name}")
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        logger.info(f"[WS CONSUMER] Accepting WebSocket connection")
        await self.accept()

        logger.info(f"[WS CONSUMER] Broadcasting user_joined event")
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_joined",
                "user_id": str(self.user.id),
                "user_name": self.user.get_full_name() or self.user.username,
            },
        )
        logger.info(f"[WS CONSUMER] Connection established successfully")

    async def disconnect(self, close_code):
        # Only send user_left event if user is authenticated
        # This prevents AttributeError when AnonymousUser disconnects
        if hasattr(self, "room_group_name"):
            if hasattr(self, "user") and self.user.is_authenticated:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "user_left",
                        "user_id": str(self.user.id),
                        "user_name": self.user.get_full_name() or self.user.username,
                    },
                )

            # Always remove from group (authenticated or not)
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages from client"""
        pass

    async def user_joined(self, event):
        """Broadcast when user joins the board"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "user.joined",
                    "data": {
                        "user_id": event["user_id"],
                        "user_name": event["user_name"],
                    },
                }
            )
        )

    async def user_left(self, event):
        """Broadcast when user leaves the board"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "user.left",
                    "data": {
                        "user_id": event["user_id"],
                        "user_name": event["user_name"],
                    },
                }
            )
        )

    async def issue_moved(self, event):
        """Broadcast when issue is moved between columns"""
        await self.send(
            text_data=json.dumps({"type": "issue.moved", "data": event["data"]})
        )

    async def issue_created(self, event):
        """Broadcast when new issue is created"""
        await self.send(
            text_data=json.dumps({"type": "issue.created", "data": event["data"]})
        )

    async def issue_updated(self, event):
        """Broadcast when issue is updated"""
        await self.send(
            text_data=json.dumps({"type": "issue.updated", "data": event["data"]})
        )

    async def issue_deleted(self, event):
        """Broadcast when issue is deleted"""
        await self.send(
            text_data=json.dumps({"type": "issue.deleted", "data": event["data"]})
        )

    async def column_created(self, event):
        """Broadcast when new column is created"""
        await self.send(
            text_data=json.dumps({"type": "column.created", "data": event["data"]})
        )

    async def column_updated(self, event):
        """Broadcast when column is updated"""
        await self.send(
            text_data=json.dumps({"type": "column.updated", "data": event["data"]})
        )

    async def column_deleted(self, event):
        """Broadcast when column is deleted"""
        await self.send(
            text_data=json.dumps({"type": "column.deleted", "data": event["data"]})
        )

    @database_sync_to_async
    def check_board_access(self):
        """Check if user has access to the board"""
        from apps.projects.models import Board, ProjectTeamMember
        from apps.workspaces.models import WorkspaceMember

        try:
            board = Board.objects.select_related("project__workspace").get(
                id=self.board_id
            )

            is_project_member = ProjectTeamMember.objects.filter(
                project=board.project, user=self.user, is_active=True
            ).exists()

            is_workspace_member = WorkspaceMember.objects.filter(
                workspace=board.project.workspace, user=self.user, is_active=True
            ).exists()

            return is_project_member or is_workspace_member
        except Board.DoesNotExist:
            return False
