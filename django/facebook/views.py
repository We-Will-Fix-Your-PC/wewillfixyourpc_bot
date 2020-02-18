from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    HttpResponseRedirect,
)
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
from operator_interface.models import Conversation, ConversationPlatform
from django.utils import timezone
from . import tasks
from . import models
import json
import datetime
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
def webhook(request):
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode is not None and token is not None:
            if mode == "subscribe" and token == settings.FACEBOOK_VERIFY_TOKEN:
                return HttpResponse(challenge)
        return HttpResponseForbidden()

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    logger.debug(f"Got event from facebook webhook: {data}")

    m_object = data.get("object")
    if m_object is None:
        return HttpResponseBadRequest()
    entries = data.get("entry")
    if entries is None:
        return HttpResponseBadRequest()

    if m_object != "page":
        return HttpResponseNotFound()

    for entry2 in entries:
        for entry in entry2["messaging"]:
            psid = {"sender": entry["sender"]["id"], "recipient": entry["recipient"]["id"]}

            message = entry.get("message")
            timestamp = entry.get("timestamp")
            postback = entry.get("postback")
            read = entry.get("read")
            acccount_linking = entry.get("account_linking")
            optin = entry.get("optin")

            if message is not None:
                tasks.handle_facebook_message.delay(psid, message, timestamp)
            if postback is not None:
                tasks.handle_facebook_postback.delay(psid, postback, timestamp)
            if read is not None:
                tasks.handle_facebook_read.delay(psid, read)
            if acccount_linking is not None:
                if acccount_linking.get("status") == "linked":
                    platform: ConversationPlatform = ConversationPlatform.exists(
                        ConversationPlatform.FACEBOOK, psid
                    )
                    if not platform:
                        return HttpResponseBadRequest()
                    try:
                        state = models.AccountLinkingState.objects.get(
                            id=acccount_linking.get("authorization_code")
                        )
                    except models.AccountLinkingState.DoesNotExist:
                        return HttpResponseBadRequest()
                    if state.timestamp + datetime.timedelta(minutes=5) < timezone.now():
                        return HttpResponseBadRequest()
                    platform.conversation.update_user_id(state.user_id)
                    state.delete()
            if optin is not None:
                tasks.handle_facebook_optin.delay(psid, optin)

    return HttpResponse("")


@login_required
def account_linking(request):
    redirect_uri = request.GET.get("redirect_uri")
    state = models.AccountLinkingState(user_id=request.user.username)
    state.save()

    return HttpResponseRedirect(f"{redirect_uri}&authorization_code={state.id}")
