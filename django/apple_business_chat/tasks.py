import logging
import json
import uuid
import requests
from celery import shared_task
from django.conf import settings

import operator_interface.consumers
import operator_interface.tasks
from operator_interface.models import ConversationPlatform, Message


def send_abc_request(mid, to, data):
    data = {
        "to": to,
        "type": "application/json",
        "content": data
    }
    if mid:
        data["id"] = mid
    return requests.post(
        "https://msging.net/messages",
        headers={
            "Authorization": f"Key {settings.BLIP_KEY}"
        },
        json=data
    )


def send_abc_notification(mid, to, event):
    return requests.post(
        "https://msging.net/messages",
        headers={
            "Authorization": f"Key {settings.BLIP_KEY}"
        },
        json={
            "id": mid,
            "from": to,
            "event": event
        }
    )


@shared_task
def handle_abc_text(msg_id, msg_from, data):
    text = data.get("content")
    platform: ConversationPlatform = ConversationPlatform.exists(
        ConversationPlatform.ABC, msg_from
    )
    if not platform:
        platform = ConversationPlatform.create(
            ConversationPlatform.ABC, msg_from, customer_user_id=None
        )
        platform.additional_platform_data = json.dumps({"open": True})
        platform.save()
    if not Message.message_exits(platform, msg_id):
        if text:
            message_m: Message = Message(
                platform=platform,
                platform_message_id=msg_id,
                text=text,
                direction=Message.FROM_CUSTOMER
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)
    send_abc_notification(msg_id, msg_from, "consumed")


@shared_task
def handle_abc_typing_on(pid: int):
    platform = ConversationPlatform.objects.get(id=pid)
    r = send_abc_request(uuid.uuid4(), platform.platform_id, {
        "type": "typing_start"
    })
    if r.status_code != 200:
        logging.error(f"Error sending ABC typing on: {r.status_code} {r.text}")
