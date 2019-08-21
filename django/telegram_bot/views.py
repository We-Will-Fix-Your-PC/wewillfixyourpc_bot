from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from . import tasks
import json
import logging
import sentry_sdk

logger = logging.getLogger(__name__)


@csrf_exempt
def webhook(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        sentry_sdk.capture_exception(e)
        return HttpResponseBadRequest()

    logger.debug(f"Got event from telegram webhook: {data}")

    message = data.get("message")
    pre_checkout_query = data.get("pre_checkout_query")
    if message:
        tasks.handle_telegram_message.delay(message)

    if pre_checkout_query:
        tasks.handle_telegram_pre_checkout_query.delay(pre_checkout_query)

    return HttpResponse("")
