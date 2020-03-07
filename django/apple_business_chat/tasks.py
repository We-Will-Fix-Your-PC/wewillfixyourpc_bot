import json
import logging
import uuid

import requests
from celery import shared_task
from django.conf import settings

import operator_interface.consumers
import operator_interface.tasks
from django.shortcuts import reverse
from operator_interface.models import ConversationPlatform, Message
from . import models


def send_abc_request(mid, to, data):
    data = dict(to=to, **data)
    if mid:
        data["id"] = str(mid)
    return requests.post(
        "https://msging.net/messages",
        headers={"Authorization": f"Key {settings.BLIP_KEY}"},
        json=data,
    )


def send_abc_notification(mid, to, event):
    return requests.post(
        "https://msging.net/messages",
        headers={"Authorization": f"Key {settings.BLIP_KEY}"},
        json={"id": mid, "from": to, "event": event},
    )


def get_platform(msg_from):
    platform: ConversationPlatform = ConversationPlatform.exists(
        ConversationPlatform.ABC, msg_from
    )
    if not platform:
        platform = ConversationPlatform.create(
            ConversationPlatform.ABC, msg_from, customer_user_id=None
        )
    return platform


@shared_task
def handle_abc_text(msg_id, msg_from, data):
    text = data.get("content")
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
    send_abc_notification(msg_id, msg_from, "consumed")


@shared_task
def handle_abc_media(msg_id, msg_from, data):
    content = data.get("content", {})
    platform = get_platform(msg_from)
    if not Message.message_exits(platform, msg_id):
        if content.get("type", "").startswith("image/"):
            message_m: Message = Message(
                platform=platform,
                platform_message_id=msg_id,
                image=content.get("uri"),
                direction=Message.FROM_CUSTOMER,
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)
            text = content.get("title", "").replace("￼", "")
            if text:
                message_m: Message = Message(
                    platform=platform,
                    platform_message_id=msg_id,
                    text=text,
                    direction=Message.FROM_CUSTOMER,
                )
                message_m.save()
                operator_interface.tasks.process_message.delay(message_m.id)
    send_abc_notification(msg_id, msg_from, "consumed")


@shared_task
def handle_abc_chatstate(msg_id, msg_from, data):
    state = data.get("content", {}).get("state")
    platform = get_platform(msg_from)
    if state == "composing":
        platform.is_typing = True
        platform.save()
    elif state == "paused":
        platform.is_typing = False
        platform.save()
    send_abc_notification(msg_id, msg_from, "consumed")


@shared_task
def handle_abc_typing_on(pid: int):
    platform = ConversationPlatform.objects.get(id=pid)
    r = send_abc_request(
        uuid.uuid4(),
        platform.platform_id,
        {
            "type": "application/vnd.lime.chatstate+json",
            "content": {"state": "composing"},
        },
    )
    if r.status_code != 202:
        logging.error(f"Error sending ABC typing on: {r.status_code} {r.text}")


@shared_task
def handle_abc_typing_off(pid: int):
    platform = ConversationPlatform.objects.get(id=pid)
    r = send_abc_request(
        uuid.uuid4(),
        platform.platform_id,
        {"type": "application/vnd.lime.chatstate+json", "content": {"state": "paused"}},
    )
    if r.status_code != 202:
        logging.error(f"Error sending ABC typing off: {r.status_code} {r.text}")


@shared_task
def send_message(mid: int):
    message = Message.objects.get(id=mid)

    messages = []

    if message.selection:
        selection_data = json.loads(message.selection)
        messages.append(
            {
                "type": "application/vnd.lime.select+json",
                "content": {
                    "title": selection_data.get("title", ""),
                    "options": [
                        {
                            "text": item.get("title", ""),
                            "type": "text/plain",
                            "value": f'/resolve_entity{{"number": "{i + 1}"}}',
                        }
                        for i, item in enumerate(selection_data.get("items", []))
                    ],
                },
            }
        )
    elif message.image:
        messages.append(
            {
                "type": "application/vnd.lime.media-link+json",
                "content": {"text": message.text, "uri": message.image},
            }
        )
    elif message.request == "sign_in":
        state = models.AccountLinkingState(conversation=message.platform)
        state.save()
        url = (
            settings.EXTERNAL_URL_BASE
            + reverse("apple_business_chat:account_linking")
            + f"?state={state.id}"
        )
        messages.append({"type": "text/plain", "content": message.text})
        messages.append(
            {
                "type": "application/json",
                "content": {
                    "type": "richLink",
                    "richLinkData": {"url": url, "title": "Sign in here", "assets": {}},
                },
            }
        )
    elif message.text:
        messages.append({"type": "text/plain", "content": message.text})
    else:
        return

    for msg_data in messages:
        r = send_abc_request(message.message_id, message.platform.platform_id, msg_data)
        if r.status_code != 202:
            message.state = Message.FAILED
            message.save()
