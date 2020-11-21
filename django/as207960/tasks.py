import logging
import requests
from celery import shared_task
from django.conf import settings
import mimetypes

import operator_interface.consumers
import operator_interface.tasks
from operator_interface.models import ConversationPlatform, Message
from django.utils import html


def send_as207960_request(mid, to: str, media_type: str, contents):
    platform, conv_id = to.split(";", 1)
    data = {
        "platform": platform,
        "platform_conversation_id": conv_id,
        "client_message_id": None,
        "media_type": media_type,
        "content": contents,
        "representative": None
    }
    if mid:
        data["client_message_id"] = str(mid)
    return requests.post(
        f"https://messaging.as207960.net/api/brands/{settings.AS207960_BRAND_ID}/messages/",
        headers={"Authorization": f"X-AS207960-PAT {settings.AS207960_KEY}"},
        json=data,
    )


def get_platform(platform, conv_id, metadata):
    msg_from = f"{platform};{conv_id}"
    platform: ConversationPlatform = ConversationPlatform.exists(
        ConversationPlatform.AS207960, msg_from
    )
    if not platform:
        platform = ConversationPlatform.create(
            ConversationPlatform.AS207960, msg_from, customer_user_id=None
        )

    if not platform.conversation.conversation_name:
        platform.conversation.conversation_name = metadata.get("user_name")
        platform.conversation.save()

    return platform


@shared_task
def handle_as207960_text(msg_id, msg_platform, msg_conv_id, metadata, content):
    platform = get_platform(msg_platform, msg_conv_id, metadata)
    platform.is_typing = False
    platform.save()
    if not Message.message_exits(platform, msg_id):
        if content:
            message_m: Message = Message(
                platform=platform,
                platform_message_id=msg_id,
                text=html.conditional_escape(content),
                direction=Message.FROM_CUSTOMER,
                state=Message.DELIVERED,
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)


@shared_task
def handle_as207960_file(msg_id, msg_platform, msg_conv_id, metadata, content):
    platform = get_platform(msg_platform, msg_conv_id, metadata)
    platform.is_typing = False
    platform.save()
    if not Message.message_exits(platform, msg_id):
        if content.get("media_type", "").startswith("image/"):
            message_m: Message = Message(
                platform=platform,
                platform_message_id=msg_id,
                image=content.get("url"),
                direction=Message.FROM_CUSTOMER,
                state=Message.DELIVERED,
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)
        else:
            message_m: Message = Message(
                platform=platform,
                platform_message_id=msg_id,
                text=content.get("url"),
                direction=Message.FROM_CUSTOMER,
                state=Message.DELIVERED,
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)


@shared_task
def handle_as207960_chatstate(_msg_id, msg_platform, msg_conv_id, metadata, content):
    platform = get_platform(msg_platform, msg_conv_id, metadata)
    platform.is_typing = False
    platform.save()
    state = content.get("state")
    if state == "composing":
        platform.is_typing = True
        platform.save()
    elif state == "paused":
        platform.is_typing = False
        platform.save()


@shared_task
def handle_as207960_typing_on(pid: int):
    platform = ConversationPlatform.objects.get(id=pid)
    r = send_as207960_request(None, platform.platform_id, "chat_state", {
        "state": "composing"
    })
    if r.status_code != 201:
        logging.error(f"Error sending AS207960 typing on: {r.status_code} {r.text}")


@shared_task
def handle_as207960_typing_off(pid: int):
    platform = ConversationPlatform.objects.get(id=pid)
    r = send_as207960_request(None, platform.platform_id, "chat_state", {
        "state": "paused"
    })
    if r.status_code != 201:
        logging.error(f"Error sending AS207960 typing on: {r.status_code} {r.text}")


@shared_task
def send_message(mid: int):
    message = Message.objects.get(id=mid)
    messages = []

    if message.image:
        messages.append((message.message_id, "file", {
            "uri": message.image,
            "media_type": mimetypes.guess_type(message.image)
        }))
    elif message.text:
        messages.append((message.message_id, "text", message.text))
    else:
        return

    for msg_data in messages:
        r = send_as207960_request(
            msg_data[0], message.platform.platform_id, msg_data[1], msg_data[2],
        )
        if r.status_code != 201:
            logging.error(f"Error sending AS207960 message: {r.status_code} {r.text}")
            message.state = Message.FAILED
            message.save()
        else:
            message.state = Message.DELIVERED
            message.save()
