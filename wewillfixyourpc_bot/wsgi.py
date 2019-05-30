"""
WSGI config for wewillfixyourpc_bot project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init("https://efc22f89d34a46d0adffb302181ed3f9@sentry.io/1471674", integrations=[CeleryIntegration()])

application = get_wsgi_application()
