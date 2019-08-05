from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
import operator_interface.routing


application = SentryAsgiMiddleware(ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(
        URLRouter(
            operator_interface.routing.websocket_urlpatterns
        )
    ),
}))
