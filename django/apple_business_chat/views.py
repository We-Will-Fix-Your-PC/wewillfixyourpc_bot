from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from . import tasks
import json
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
def webhook(request):
    key: str = request.META.get('HTTP_AUTHORIZATION', "")
    if not key.startswith("Key "):
        return HttpResponseForbidden()
    key = key[4:]
    if key != settings.BLIP_KEY:
        return HttpResponseForbidden()

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    logger.debug(f"Got event from ABC webhook: {data}")

    msg_from = data.get("from")
    msg_id = data.get("id")
    msg_type = data.get("type")
    if msg_type == "text/plain":
        tasks.handle_abc_text.delay(msg_id, msg_from, data)

    return HttpResponse("")
