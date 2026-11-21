import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

django_application = get_asgi_application()

from backend.config.routing import websocket_urlpatterns

from django.conf import settings
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

websocket = URLRouter(websocket_urlpatterns)
if settings.HOSTED_DASHBOARD:
    websocket = AllowedHostsOriginValidator(AuthMiddlewareStack(websocket))

application = ProtocolTypeRouter({
    "http": django_application,
    "websocket": websocket,
})

