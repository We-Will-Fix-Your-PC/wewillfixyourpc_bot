from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from keycloak_auth.middleware import OIDCChannelsMiddleware
import operator_interface.routing


application = SentryAsgiMiddleware(ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(OIDCChannelsMiddleware(URLRouter(
         operator_interface.routing.websocket_urlpatterns
    ))),
}))
