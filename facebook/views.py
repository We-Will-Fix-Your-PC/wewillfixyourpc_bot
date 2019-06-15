from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from . import tasks
import json
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
def webhook(request):
    if request.method == "GET":
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode is not None and token is not None:
            if mode == 'subscribe' and token == settings.FACEBOOK_VERIFY_TOKEN:
                return HttpResponse(challenge)
        return HttpResponseForbidden()

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    logger.debug(f"Got event from facebook webhook: {data}")

    m_object = data.get('object')
    if m_object is None:
        return HttpResponseBadRequest()
    entries = data.get('entry')
    if entries is None:
        return HttpResponseBadRequest()

    if m_object != "page":
        return HttpResponseNotFound()

    for entry in entries:
        entry = entry["messaging"][0]
        psid = {
            "sender": entry["sender"]["id"],
            "recipient": entry["recipient"]["id"]
        }

        message = entry.get("message")
        postback = entry.get("postback")

        if message is not None:
            tasks.handle_facebook_message.delay(psid, message)

        if postback is not None:
            tasks.handle_facebook_postback.delay(psid, postback)

    return HttpResponse("")
