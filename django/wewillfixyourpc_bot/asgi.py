"""
ASGI entrypoint. Configures Django and then runs the application
defined in the ASGI_APPLICATION setting.
"""

import django
from channels.routing import get_default_application
from django.conf import settings
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

django.setup()

if not settings.DEBUG:
    sentry_sdk.init(
        "https://efc22f89d34a46d0adffb302181ed3f9@sentry.io/1471674", environment=settings.SENTRY_ENVIRONMENT,
        integrations=[CeleryIntegration(), DjangoIntegration()]
    )

application = get_default_application()
