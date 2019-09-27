import logging
import os
import re
import magic
import time
import urllib.parse
from io import BytesIO

import typing
import requests
from celery import shared_task
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.storage import DefaultStorage
from django.conf import settings
from django.shortcuts import reverse

import operator_interface.tasks
import django_keycloak_auth.users
from operator_interface.consumers import conversation_saved
from operator_interface.models import Conversation, Message
from . import views


@shared_task
def handle_twitter_message(mid: str, psid, message, user):
    text: str = message.get("text")
    attachment: dict = message.get("attachment")
    if text is not None:
        conversation: Conversation = Conversation.get_or_create_conversation(
            Conversation.TWITTER, psid,
        )

        if not conversation.conversation_user_id:
            user = django_keycloak_auth.users.get_or_create_user(
                federated_provider="twitter",
                federated_user_id=user.get("id"),
                federated_user_name=user.get("screen_name"),
                first_name=user.get("name"),
            )
            if user:
                conversation.conversation_user_id = user.get("id")
                conversation.save()

        if conversation.conversation_user_id:
            django_keycloak_auth.users.link_federated_identity_if_not_exists(
                conversation.conversation_user_id,
                federated_provider="twitter",
                federated_user_id=user.get("id"),
                federated_user_name=user.get("screen_name"),
            )

            django_keycloak_auth.users.update_user(
                conversation.conversation_user_id,
                first_name=user.get("name"),
            )

        if not Message.message_exits(conversation, mid):
            message_m: Message = Message(
                conversation=conversation,
                message_id=mid,
                text=text.strip(),
                direction=Message.FROM_CUSTOMER,
            )

            if attachment:
                if attachment["type"] == "media":
                    creds = views.get_creds()
                    url: str = attachment["media"]["media_url_https"]
                    indices: typing.Tuple = attachment["media"]["indices"]
                    message_m.text = (text[: indices[0]] + text[indices[1] :]).strip()

                    media_r = requests.get(url, auth=creds)
                    if media_r.status_code == 200:
                        orig_file_name = os.path.basename(
                            urllib.parse.urlparse(url).path
                        )
                        fs = DefaultStorage()
                        file_name = fs.save(orig_file_name, BytesIO(media_r.content))
                        message_m.image = fs.base_url + file_name

            message_m.save()
            handle_mark_twitter_message_read.delay(psid, mid)
            operator_interface.tasks.process_message.delay(message_m.id)

        file_name = os.path.basename(
            urllib.parse.urlparse(user["profile_image_url_https"]).path
        )
        r = requests.get(user["profile_image_url_https"])
        if r.status_code == 200:
            conversation.conversation_pic = InMemoryUploadedFile(
                file=BytesIO(r.content),
                size=len(r.content),
                charset=r.encoding,
                content_type=r.headers.get("content-type"),
                field_name=file_name,
                name=file_name,
            )
            conversation.save()
            conversation_saved(None, conversation)


@shared_task
def handle_twitter_read(psid: str, last_read: str):
    last_read: int = int(last_read)
    conversation: Conversation = Conversation.get_or_create_conversation(
        Conversation.TWITTER, psid
    )
    messages: typing.List[Message] = Message.objects.filter(
        conversation=conversation, direction=Message.TO_CUSTOMER, read=False
    )
    message_ids = []
    for m in messages:
        try:
            m_id = int(m.message_id)
        except ValueError:
            continue
        if m_id <= last_read:
            m.read = True
            m.save()
            message_ids.append(m.id)
    for message in message_ids:
        operator_interface.tasks.send_message_to_interface.delay(message)


@shared_task
def handle_mark_twitter_message_read(psid: str, mid: str):
    creds = views.get_creds()
    requests.post(
        "https://api.twitter.com/1.1/direct_messages/mark_read.json",
        data={"last_read_event_id": mid, "recipient_id": psid},
        auth=creds,
    )


@shared_task
def handle_twitter_message_typing_on(cid: int):
    creds = views.get_creds()
    conversation = Conversation.objects.get(id=cid)
    requests.post(
        "https://api.twitter.com/1.1/direct_messages/indicate_typing.json",
        data={"recipient_id": conversation.platform_id},
        auth=creds,
    )


@shared_task
def send_twitter_message(mid: int):
    message = Message.objects.get(id=mid)
    psid: str = message.conversation.platform_id
    creds = views.get_creds()

    quick_replies = []
    for suggestion in message.messagesuggestion_set.all():
        quick_replies.append(
            {"label": suggestion.suggested_response, "metadata": suggestion.id}
        )

    request_body = {
        "event": {
            "type": "message_create",
            "message_create": {
                "target": {"recipient_id": psid},
                "message_data": {"text": message.text},
            },
        }
    }

    if len(quick_replies) > 0:
        request_body["event"]["message_create"]["message_data"]["quick_reply"] = {
            "type": "options",
            "options": quick_replies,
        }

    if message.payment_request:
        request_body["event"]["message_create"]["message_data"]["ctas"] = [
            {
                "type": "web_url",
                "label": "Pay",
                "url": settings.EXTERNAL_URL_BASE
                + reverse(
                    "payment:twitter_payment",
                    kwargs={"payment_id": message.payment_request.id},
                ),
            }
        ]
    elif message.payment_confirm:
        request_body["event"]["message_create"]["message_data"][
            "text"
        ] = "You can view your receipt using the link below"
        request_body["event"]["message_create"]["message_data"]["ctas"] = [
            {
                "type": "web_url",
                "label": "View Receipt",
                "url": settings.EXTERNAL_URL_BASE
                + reverse(
                    "payment:receipt", kwargs={"payment_id": message.payment_confirm.id}
                ),
            }
        ]
    else:
        urls = re.findall(
            "(http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)",
            message.text,
        )

        if len(urls) == 1:
            request_body["event"]["message_create"]["message_data"]["ctas"] = [
                {"type": "web_url", "label": "Open link", "url": urls[0]}
            ]

    if message.image:
        image = requests.get(message.image)
        image.raise_for_status()
        image = image.content
        mime = magic.from_buffer(image, mime=True)

        init_r = requests.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            auth=creds,
            data={
                "command": "INIT",
                "total_bytes": len(image),
                "media_type": mime,
                "media_category": "DmImage",
            },
        )
        init_r.raise_for_status()
        media_id = init_r.json()["media_id"]

        append_r = requests.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            auth=creds,
            files={
                "command": "APPEND",
                "media_id": media_id,
                "segment_index": 0,
                "media": image,
            },
        )
        append_r.raise_for_status()

        finalize_r = requests.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            auth=creds,
            data={"command": "FINALIZE", "media_id": media_id},
        )
        finalize_r.raise_for_status()
        finalize_r = finalize_r.json()

        uploaded = True
        wait_secs = 1

        if finalize_r.get("processing_info"):
            uploaded = False
            wait_secs = finalize_r["processing_info"]["check_after_secs"]

        while not uploaded:
            time.sleep(wait_secs)
            status_r = requests.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                auth=creds,
                data={"command": "STATUS", "media_id": media_id},
            )
            status_r.raise_for_status()
            status_r = finalize_r.json()
            processing_info = status_r["processing_info"]
            if processing_info["state"] == "succeded":
                uploaded = True
            else:
                wait_secs = processing_info["check_after_secs"]

        request_body["event"]["message_create"]["message_data"]["attachment"] = {
            "type": "media",
            "media": {"id": media_id},
        }

    r = requests.post(
        "https://api.twitter.com/1.1/direct_messages/events/new.json",
        auth=creds,
        json=request_body,
    )
    if r.status_code != 200:
        logging.error(f"Error sending twitter message: {r.status_code} {r.text}")
        request_body = {
            "event": {
                "type": "message_create",
                "message_create": {
                    "target": {"recipient_id": psid},
                    "message_data": {
                        "text": "Sorry, I'm having some difficulty processing your request. Please try again later"
                    },
                },
            }
        }
        requests.post(
            "https://api.twitter.com/1.1/direct_messages/events/new.json",
            auth=creds,
            json=request_body,
        ).raise_for_status()
    else:
        r = r.json()
        message.message_id = r["event"]["id"]
        message.delivered = True
        message.save()
        operator_interface.consumers.message_saved(None, message)
