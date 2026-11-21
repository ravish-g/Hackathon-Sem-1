"""WebSocket routes owned by the stream-events workstream."""

from channels.auth import AuthMiddlewareStack
from django.urls import re_path

from backend.monitoring.consumers import DashboardConsumer


websocket_urlpatterns = [
    re_path(
        r"^ws/dashboard/$",
        AuthMiddlewareStack(DashboardConsumer.as_asgi()),
    ),
]

