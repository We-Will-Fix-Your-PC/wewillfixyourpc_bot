from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django_keycloak_auth.middleware import OIDCChannelsMiddleware
import operator_interface.consumers
import customer_chat.consumers
from django.urls import path


application = SentryAsgiMiddleware(
    ProtocolTypeRouter(
        {
            "websocket": AuthMiddlewareStack(
                OIDCChannelsMiddleware(
                    URLRouter(
                        [
                            path(
                                "ws/operator/",
                                operator_interface.consumers.OperatorConsumer,
                            ),
                            path("ws/chat/", customer_chat.consumers.ChatConsumer),
                        ]
                    )
                )
            )
        }
    )
)
