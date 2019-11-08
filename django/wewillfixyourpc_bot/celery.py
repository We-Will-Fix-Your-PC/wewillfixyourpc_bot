from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wewillfixyourpc_bot.settings")
from django.conf import settings

if not settings.DEBUG:
    sentry_sdk.init(
        "https://efc22f89d34a46d0adffb302181ed3f9@sentry.io/1471674",
        environment=settings.SENTRY_ENVIRONMENT,
        integrations=[CeleryIntegration(), DjangoIntegration(), RedisIntegration()],
        release=os.getenv("RELEASE", None),
    )

app = Celery("wewillfixyourpc_bot")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
