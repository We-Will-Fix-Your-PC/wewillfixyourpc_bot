import json
import logging
import base64
import uuid
import magic
import os.path
import urllib.parse
import django_keycloak_auth.users
import requests
from celery import shared_task
from django.conf import settings
from io import BytesIO

import operator_interface.consumers
import operator_interface.tasks
from django.shortcuts import reverse
from operator_interface.models import ConversationPlatform, Message
from django.core.files.storage import DefaultStorage
from django.utils import html
from . import models


def send_blip_abc_request(mid, to, data):
    data = dict(to=to, **data)
    if mid:
        data["id"] = str(mid)
    return requests.post(
        "https://msging.net/messages",
        headers={"Authorization": f"Key {settings.BLIP_KEY}"},
        json=data,
    )


def send_own_abc_request(mid, to: str, locale: str, contents: dict, files: [], auto_reply: bool = True):
    data = {
        "to": to,
        "locale": locale,
        "auto-reply": auto_reply,
        "contents": contents
    }
    if mid:
        data["id"] = str(mid)
    return requests.post(
        "https://abc.cardifftec.uk/api/message",
        headers={"Authorization": f"Bearer {settings.ABC_KEY}"},
        data={
            "data": json.dumps(data)
        },
        files=[("file", f) for f in files]
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
    platform.is_typing = False
    platform.save()
    if not Message.message_exits(platform, msg_id):
        if text:
            message_m: Message = Message(
                platform=platform,
                platform_message_id=msg_id,
                text=html.conditional_escape(text),
                direction=Message.FROM_CUSTOMER,
                state=Message.DELIVERED,
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)
    send_abc_notification(msg_id, msg_from, "consumed")


@shared_task
def handle_abc_media(msg_id, msg_from, data):
    content = data.get("content", {})
    platform = get_platform(msg_from)
    platform.is_typing = False
    platform.save()
    if not Message.message_exits(platform, msg_id):
        if content.get("type", "").startswith("image/"):
            message_m: Message = Message(
                platform=platform,
                platform_message_id=msg_id,
                image=content.get("uri"),
                direction=Message.FROM_CUSTOMER,
                state=Message.DELIVERED,
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)
            text = content.get("title", "").replace("￼", "")
            if text:
                message_m: Message = Message(
                    platform=platform,
                    platform_message_id=msg_id,
                    text=html.conditional_escape(text),
                    direction=Message.FROM_CUSTOMER,
                    state=Message.DELIVERED,
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
def handle_abc_own(data: dict):
    msg_from: str = data.get("from")
    msg_id: str = data.get("id")
    device: str = data.get("device")
    capabilities: [str] = data.get("capabilities")
    msg_locale: str = data.get("locale")
    # msg_group: str = data.get("group")
    # msg_intent: str = data.get("intent")
    contents: dict = data.get("contents")

    platform = get_platform(msg_from)
    conversation = platform.conversation
    if not platform.additional_platform_data:
        info = {}
    else:
        try:
            info = json.loads(platform.additional_platform_data)
        except json.JSONDecodeError:
            info = {}

    info["current_capabilities"] = capabilities

    if conversation.conversation_user_id:
        django_keycloak_auth.users.update_user(
            str(conversation.conversation_user_id),
            locale=msg_locale,
            force_update=False,
        )

    if not Message.message_exits(platform, msg_id):
        if contents.get("text"):
            platform.is_typing = False
            platform.save()
            message_m: Message = Message(
                platform=platform,
                platform_message_id=msg_id,
                text=html.conditional_escape(contents["text"]),
                direction=Message.FROM_CUSTOMER,
                state=Message.DELIVERED,
                device_data=device
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)
        elif contents.get("action"):
            action: str = contents["action"]
            if action == "typing_start":
                platform.is_typing = True
                platform.save()
            elif action == "typing_end":
                platform.is_typing = False
                platform.save()
            elif action == "close":
                platform.is_typing = False
                platform.save()
                m = Message(
                    platform=platform,
                    platform_message_id=msg_id,
                    end=True,
                    direction=Message.FROM_CUSTOMER,
                    state=Message.DELIVERED,
                    device_data=device
                )
                m.save()
                operator_interface.tasks.send_message_to_interface.delay(m.id)

    platform.additional_platform_data = json.dumps(info)
    platform.save()

    for attachment in data.get("attachments", []):
        contents: str = attachment.get("contents")
        name: str = attachment.get("name")
        mime_type: str = attachment.get("mime-type")
        if contents:
            try:
                contents: bytes = base64.b64decode(contents)
            except ValueError:
                continue
            fs = DefaultStorage()
            file_name = fs.save(name, BytesIO(contents))

            if mime_type.startswith("image"):
                m = Message(
                    platform=platform,
                    platform_message_id=msg_id,
                    direction=Message.FROM_CUSTOMER,
                    state=Message.DELIVERED,
                    device_data=device,
                    image=fs.base_url + file_name
                )
            else:
                m = Message(
                    platform=platform,
                    platform_message_id=msg_id,
                    direction=Message.FROM_CUSTOMER,
                    state=Message.DELIVERED,
                    device_data=device,
                    text=f"<a href=\"{fs.base_url + file_name}\" target=\"_blank\">{name}</a>",
                )
            m.save()
            operator_interface.tasks.process_message.delay(m.id)


@shared_task
def handle_abc_typing_on(pid: int):
    platform = ConversationPlatform.objects.get(id=pid)
    if settings.ABC_PLATFORM == "blip":
        r = send_blip_abc_request(
            uuid.uuid4(),
            platform.platform_id,
            {
                "type": "application/vnd.lime.chatstate+json",
                "content": {"state": "composing"},
            },
        )
        if r.status_code != 202:
            logging.error(f"Error sending ABC typing on: {r.status_code} {r.text}")
    elif settings.ABC_PLATFORM == "own":
        r = send_own_abc_request(None, platform.platform_id, "en_GB", {
            "action": "typing_start"
        }, [], auto_reply=platform.conversation.current_agent is None)
        if r.status_code != 200:
            logging.error(f"Error sending ABC typing on: {r.status_code} {r.text}")


@shared_task
def handle_abc_typing_off(pid: int):
    platform = ConversationPlatform.objects.get(id=pid)
    if settings.ABC_PLATFORM == "blip":
        r = send_blip_abc_request(
            uuid.uuid4(),
            platform.platform_id,
            {"type": "application/vnd.lime.chatstate+json", "content": {"state": "paused"}},
        )
        if r.status_code != 202:
            logging.error(f"Error sending ABC typing off: {r.status_code} {r.text}")
    elif settings.ABC_PLATFORM == "own":
        r = send_own_abc_request(None, platform.platform_id, "en_GB", {
            "action": "typing_end"
        }, [], auto_reply=platform.conversation.current_agent is None)
        if r.status_code != 200:
            logging.error(f"Error sending ABC typing off: {r.status_code} {r.text}")


@shared_task
def send_message(mid: int):
    message = Message.objects.get(id=mid)

    if settings.ABC_PLATFORM == "blip":
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
            r = send_blip_abc_request(message.message_id, message.platform.platform_id, msg_data)
            if r.status_code != 202:
                logging.error(f"Error sending ABC message: {r.status_code} {r.text}")
                message.state = Message.FAILED
                message.save()
            else:
                message.state = Message.DELIVERED
                message.save()

    elif settings.ABC_PLATFORM == "own":
        messages = []

        if message.selection:
            selection_data = json.loads(message.selection)
            messages.append((message.message_id, {
                    "interactive": {
                        "bid": "com.apple.messages.MSMessageExtensionBalloonPlugin:0000000000:com."
                               "apple.icloud.apps.messages.business.extension",
                        "data": {
                            "listPicker": {
                                "multipleSelection": True,
                                "sections": [{
                                    "items": [{
                                            "title": item.get("title", ""),
                                            "style": "default",
                                            "identifier": f"{i + 1}",
                                        } for i, item in enumerate(selection_data.get("items", []))
                                    ],
                                    "title": selection_data.get("title", "")
                                }]
                            },
                            "version": "1.0",
                            "requestIdentifier": message.message_id
                        },
                        "receivedMessage": {
                            "title": selection_data.get("title", ""),
                            "subtitle": "Please make a selection",
                            "style": "small",
                        },
                        "replyMessage": {
                            "title": "Selection made",
                            "subtitle": "Thanks!",
                            "style": "small",
                        }
                    }
                }, []))
        elif message.card:
            card = json.loads(message.card)

            if card.get("text"):
                messages.append((message.message_id, {
                    "text": card["text"]
                }, []))
            if card.get("button"):
                messages.append((message.message_id if not card.get("text") else uuid.uuid4(), {
                    "title": card["button"].get("title"),
                    "url": card["button"].get("link")
                }, []))

        elif message.image:
            orig_file_name = os.path.basename(
                urllib.parse.urlparse(message.image).path
            )
            image = requests.get(message.image)
            image.raise_for_status()
            image = image.content
            mime = magic.from_buffer(image, mime=True)
            messages.append((message.message_id, {
                "text": ""
            }, [(orig_file_name, image, mime)]))
        elif message.request == "sign_in":
            state = models.AccountLinkingState(conversation=message.platform)
            state.save()
            url = (
                    settings.EXTERNAL_URL_BASE
                    + reverse("apple_business_chat:account_linking")
                    + f"?state={state.id}"
            )
            messages.append((message.message_id, {
                "text": message.text
            }, []))
            messages.append((uuid.uuid4(), {
                "title": "Sign in here",
                "url": url
            }, []))
        elif message.text:
            messages.append((message.message_id, {
                "text": message.text
            }, []))
        else:
            return

        for msg_data in messages:
            r = send_own_abc_request(
                msg_data[0], message.platform.platform_id, "en_GB", msg_data[1], msg_data[2],
                auto_reply=message.user is None
            )
            if r.status_code != 200:
                logging.error(f"Error sending ABC message: {r.status_code} {r.text}")
                message.state = Message.FAILED
                message.save()
            else:
                message.state = Message.DELIVERED
                message.save()
