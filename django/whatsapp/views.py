from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import datetime
import twilio.rest
import logging
from . import tasks
from . import models
import operator_interface.tasks
from operator_interface.models import Message


logger = logging.getLogger(__name__)
twilio_client = twilio.rest.Client(settings.TWILIO_ACCOUNT, settings.TWILIO_TOKEN)
twilio_validator = RequestValidator(settings.TWILIO_TOKEN)


def check_auth(f):
    def new_f(request, *args, **kwargs):
        uri = f"https://{request.get_host()}{request.path}"
        sig_valid = twilio_validator.validate(
            uri, request.POST, request.META.get("HTTP_X_TWILIO_SIGNATURE")
        )
        if not sig_valid:
            return HttpResponseForbidden()

        return f(request, *args, **kwargs)

    return new_f


@csrf_exempt
@check_auth
def webhook(request):
    logger.debug(f"Got event from twilio whatsapp webhook: {request.POST}")

    msg_from = request.POST.get("From")
    if not msg_from.startswith("whatsapp:"):
        return HttpResponseBadRequest()
    msg_from = msg_from[len("whatsapp:"):]
    msg_id = request.POST.get("MessageSid")
    tasks.handle_whatsapp.delay(msg_id, msg_from, request.POST)

    response = MessagingResponse()
    return HttpResponse(str(response))


@csrf_exempt
def notif_webhook(request):
    logger.debug(f"Got event from twilio whatsapp status webhook: {request.POST}")

    msg_id = request.POST.get("MessageSid")
    msg_status = request.POST.get("MessageStatus")
    msc_error_code = request.POST.get("ErrorCode")
    msg: Message = Message.objects.filter(platform_message_id=msg_id).first()

    if msg_status == "delivered" and msg and msg.state != Message.READ:
        msg.state = Message.DELIVERED
        msg.save()
    elif msg_status == "failed" and msg:
        if msc_error_code == "63003":
            tasks.attempt_alternative_delivery.delay(msg.id)
        else:
            msg.state = Message.FAILED
            msg.save()
    elif msg_status == "read" and msg:
        msg.state = Message.READ
        msg.save()

    return HttpResponse("")


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
