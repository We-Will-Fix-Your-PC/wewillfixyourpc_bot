from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path
from django_keycloak_auth.middleware import OIDCChannelsMiddleware
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

import customer_chat.consumers
import operator_interface.consumers

application = SentryAsgiMiddleware(
    ProtocolTypeRouter({
        "websocket": AuthMiddlewareStack(
            OIDCChannelsMiddleware(
                URLRouter([
                    path("ws/operator/", operator_interface.consumers.OperatorConsumer.as_asgi()),
                    path("ws/chat/", customer_chat.consumers.ChatConsumer.as_asgi()),
                ])
            )
        )
    })
)
