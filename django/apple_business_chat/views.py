from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from . import tasks
from operator_interface.models import Message
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
    elif msg_type == "application/vnd.lime.media-link+json":
        pass

    return HttpResponse("")


@csrf_exempt
def notif_webhook(request):
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

    logger.debug(f"Got event from ABC notification webhook: {data}")

    msg_id = data.get("id")
    msg_event = data.get("event")
    msg = Message.objects.get(message_id=msg_id)
    if msg_event == "received":
        msg.state = Message.DELIVERED
        msg.save()
    elif msg_event == "consumed":
        msg.state = Message.READ
        msg.save()

    return HttpResponse("")
