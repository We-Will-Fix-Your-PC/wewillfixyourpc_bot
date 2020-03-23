from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
import operator_interface.tasks
from django.utils import timezone
import datetime
from . import tasks
from . import models
from operator_interface.models import Message, ConversationPlatform
import json
import logging
import hmac

logger = logging.getLogger(__name__)


def check_auth(f):
    def new_f(request, *args, **kwargs):
        if settings.ABC_PLATFORM == "blip":
            key: str = request.META.get("HTTP_AUTHORIZATION", "")
            if not key.startswith("Key "):
                return HttpResponseForbidden()
            key = key[4:]
            if key != settings.BLIP_KEY:
                return HttpResponseForbidden()

        elif settings.ABC_PLATFORM == "own":
            sig: str = request.META.get("HTTP_X_BODY_SIGNATURE", "")
            digest = hmac.new(key=settings.ABC_KEY.encode(), msg=request.body, digestmod='sha512')
            if not hmac.compare_digest(sig, digest.hexdigest()):
                return HttpResponseForbidden()

        return f(request, *args, **kwargs)

    return new_f


@csrf_exempt
@check_auth
def webhook(request):
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
        tasks.handle_abc_media.delay(msg_id, msg_from, data)
    elif msg_type == "application/vnd.lime.chatstate+json":
        tasks.handle_abc_chatstate.delay(msg_id, msg_from, data)

    return HttpResponse("")


@csrf_exempt
@check_auth
def message(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    logger.debug(f"Got event from ABC webhook: {data}")

    tasks.handle_abc_own.delay(data)

    return HttpResponse("")


@csrf_exempt
@check_auth
def notif_webhook(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    logger.debug(f"Got event from ABC notification webhook: {data}")

    msg_id = data.get("id")
    from_id = data.get("from")
    msg_event = data.get("event")
    conv: ConversationPlatform = ConversationPlatform.objects.filter(
        platform=ConversationPlatform.ABC, platform_id=from_id
    ).first()
    msg: Message = Message.objects.filter(message_id=msg_id).first()

    if msg_event == "failed":
        msg_fail_reason = data.get("reason", {})
        msg_error_code = msg_fail_reason.get("code")
        if msg_error_code == 87 and conv:
            m = Message(
                platform=conv,
                platform_message_id=msg_id,
                end=True,
                direction=Message.FROM_CUSTOMER,
                state=Message.DELIVERED,
            )
            m.save()
            operator_interface.tasks.process_message.delay(m.id)
        if msg:
            msg.state = Message.FAILED
            msg.save()
    elif msg_event == "accepted" and msg and msg.state != Message.READ:
        msg.state = Message.DELIVERED
        msg.save()
    elif msg_event == "consumed" and msg:
        msg.state = Message.READ
        msg.save()

    return HttpResponse("")


@csrf_exempt
@check_auth
def notification(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    logger.debug(f"Got event from ABC notification webhook: {data}")

    msg_id = data.get("id")
    msg_status = data.get("status")
    msg: Message = Message.objects.filter(message_id=msg_id).first()

    if msg:
        if msg_status == "failed":
            msg.state = Message.FAILED
            msg.save()
        elif msg_status == "sent":
            msg.state = Message.DELIVERED
            msg.save()

        return HttpResponse("")
    else:
        return HttpResponseNotFound()


@login_required
def account_linking(request):
    state = request.GET.get("state")

    try:
        state = models.AccountLinkingState.objects.get(id=state)
    except models.AccountLinkingState.DoesNotExist:
        return HttpResponseBadRequest()

    if state.timestamp + datetime.timedelta(minutes=5) < timezone.now():
        return HttpResponseBadRequest()
    state.conversation.conversation.update_user_id(request.user.username)
    state.delete()

    message = Message(
        platform=state.conversation,
        text="Login complete, thanks!",
        direction=Message.TO_CUSTOMER,
    )
    message.save()
    operator_interface.tasks.process_message.delay(message.id)

    return HttpResponse(
        '<script type="text/javascript">window.close();</script><h1>You can now close this window</h1>'
    )
