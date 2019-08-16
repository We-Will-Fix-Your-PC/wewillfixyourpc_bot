from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from . import tasks
import json
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
def webhook(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    logger.debug(f"Got event from telegram webhook: {data}")

    message = data.get("message")
    if message:
        tasks.handle_telegram_message.delay(message)

    return HttpResponse("")
