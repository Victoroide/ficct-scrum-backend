from django.urls import path

from apps.projects.consumers import BoardConsumer

websocket_urlpatterns = [
    path("ws/boards/<uuid:board_id>/", BoardConsumer.as_asgi()),
]
