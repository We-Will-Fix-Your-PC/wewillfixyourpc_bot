from celery import shared_task
import typing
import json
import phonenumbers
import operator_interface.consumers
import operator_interface.tasks
import django_keycloak_auth.users
from django.conf import settings
import twilio.base.exceptions
from django.shortcuts import reverse
from operator_interface.models import ConversationPlatform, Message
from . import views
from . import models


def get_platform(msg_from):
    platform: ConversationPlatform = ConversationPlatform.exists(
        ConversationPlatform.SMS, msg_from
    )
    if not platform:
        user_id = attempt_get_user_id(msg_from)
        platform = ConversationPlatform.create(
            ConversationPlatform.SMS, msg_from, customer_user_id=user_id
        )
    return platform


def attempt_get_user_id(msg_from: str) -> typing.Optional[str]:
    def match_user(u):
        numbers = u.user.get("attributes", {}).get("phone", [])
        for num in numbers:
            try:
                num = phonenumbers.parse(num, settings.PHONENUMBER_DEFAULT_REGION)
            except phonenumbers.NumberParseException:
                continue
            if (
                phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
                == msg_from
            ):
                return True

        return False

    user = next(filter(match_user, django_keycloak_auth.users.get_users()), None)
    return user.user.get("id") if user else None


@shared_task
def handle_sms(msg_id, msg_from, data):
    text = data.get("Body")
    platform = get_platform(msg_from)
    if not Message.message_exits(platform, msg_id):
        if text:
            message_m: Message = Message(
                platform=platform,
                platform_message_id=msg_id,
                text=text,
                direction=Message.FROM_CUSTOMER,
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)


@shared_task
def send_message(mid: int):
    message = Message.objects.get(id=mid)

    msg_args = {}

    if message.selection:
        selection_data = json.loads(message.selection)
        msg_args["body"] = "\n".join(
            [
                f"{i+1}) {item.get('title')}?"
                for i, item in enumerate(selection_data.get("items", []))
            ]
        )
    elif message.request == "sign_in":
        state = models.AccountLinkingState(conversation=message.platform)
        state.save()
        url = (
            settings.EXTERNAL_URL_BASE
            + reverse("sms:account_linking")
            + f"?state={state.id}"
        )
        msg_args["body"] = f"{message.text}\n\nSign in here: {url}"
    elif message.text:
        msg_args["body"] = message.text
    else:
        return

    try:
        msg_resp = views.twilio_client.messages.create(
            to=message.platform.platform_id,
            provide_feedback=True,
            messaging_service_sid=settings.TWILIO_MSID,
            **msg_args,
        )
    except twilio.base.exceptions.TwilioException:
        message.state = Message.FAILED
        message.save()
        return

    message.platform_message_id = msg_resp.sid
    message.save()
