from __future__ import absolute_import, unicode_literals
import os
import django
from celery import Celery
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wewillfixyourpc_bot.settings')
django.setup()
from django.conf import settings

if not settings.DEBUG:
    sentry_sdk.init(
        "https://efc22f89d34a46d0adffb302181ed3f9@sentry.io/1471674", environment=settings.SENTRY_ENVIRONMENT,
        integrations=[CeleryIntegration(), DjangoIntegration()]
    )

app = Celery('wewillfixyourpc_bot')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
