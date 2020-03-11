from celery import shared_task
import typing
import json
import phonenumbers
import operator_interface.consumers
import operator_interface.tasks
import django_keycloak_auth.users
import django_keycloak_auth.clients
from django.conf import settings
import twilio.base.exceptions
from django.shortcuts import reverse
from operator_interface.models import ConversationPlatform, Message
from . import views
from . import models


def get_platform(msg_from):
    platform: ConversationPlatform = ConversationPlatform.exists(
        ConversationPlatform.WHATSAPP, msg_from
    )
    if not platform:
        user_id = attempt_get_user_id(msg_from)
        platform = ConversationPlatform.create(
            ConversationPlatform.WHATSAPP, msg_from, customer_user_id=user_id
        )
    if platform:
        user_id = attempt_get_user_id(msg_from)
        if user_id and str(platform.conversation.conversation_user_id) != user_id:
            platform.conversation.update_user_id(user_id)
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
def handle_whatsapp(msg_id, msg_from, data):
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

    if message.selection:
        selection_data = json.loads(message.selection)
        msg_body = "\n".join(
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
            + reverse("whatsapp:account_linking")
            + f"?state={state.id}"
        )
        msg_body = f"{message.text}\n\nSign in here: {url}"
    elif message.text:
        msg_body = message.text
    else:
        return

    try:
        msg_resp = views.twilio_client.messages.create(
            to=f"whatsapp:{message.platform.platform_id}",
            provide_feedback=True,
            from_=f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}",
            body=msg_body,
        )
    except twilio.base.exceptions.TwilioException:
        message.state = Message.FAILED
        message.save()
        return

    message.platform_message_id = msg_resp.sid
    message.save()


@shared_task
def attempt_alternative_delivery(mid: int):
    message = Message.objects.get(id=mid)
    platform = message.platform
    if not platform.additional_platform_data:
        info = {}
    else:
        try:
            info = json.loads(platform.additional_platform_data)
        except json.JSONDecodeError:
            return
    try_others = info.get("try_others", [])
    already_tried = info.get("already_tried", [])
    if type(try_others) != list or type(already_tried) != list:
        return

    i = 0
    new_number = try_others[i]
    while new_number in already_tried or new_number == platform.platform_id:
        i += 1
        if i == len(try_others):
            new_number = None
            break
        else:
            new_number = try_others[i]

    if new_number:
        already_tried.append(platform.platform_id)
        platform.platform_id = new_number
        info["already_tried"] = already_tried
        platform.additional_platform_data = json.dumps(info)
        platform.save()
        send_message.delay(mid)
    else:
        info["already_tried"] = []
        new_platform = None
        for n in try_others:
            try:
                new_platform = ConversationPlatform.objects.get(
                    platform=ConversationPlatform.SMS,
                    platform_id=n,
                )
                break
            except ConversationPlatform.DoesNotExist:
                pass
        if not new_platform:
            new_platform = ConversationPlatform(
                conversation=platform.conversation,
                platform=ConversationPlatform.SMS,
                platform_id=platform.platform_id,
                additional_platform_data=json.dumps(info)
            )
            new_platform.save()

        message.platform = new_platform
        message.save()
        send_message.delay(message.id)
