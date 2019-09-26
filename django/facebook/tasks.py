import datetime
import decimal
import json
import logging
import os.path
import re
import typing
import urllib.parse
import uuid
from io import BytesIO

import requests
from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import DefaultStorage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.shortcuts import reverse
from django.utils import timezone

import keycloak_auth.clients
import operator_interface.consumers
import operator_interface.tasks
from operator_interface.models import Conversation, Message


@shared_task
def handle_facebook_message(psid: dict, message: dict) -> None:
    text: typing.Text = message.get("text")
    attachments: typing.List[typing.Dict] = message.get("attachments")
    mid: typing.Text = message["mid"]
    is_echo: bool = message.get("is_echo")
    psid: typing.Text = psid["sender"] if not is_echo else psid["recipient"]
    conversation: Conversation = Conversation.get_or_create_conversation(
        Conversation.FACEBOOK, psid
    )
    if not is_echo:
        update_facebook_profile(psid, conversation.id)
        if not Message.message_exits(conversation, mid):
            handle_mark_facebook_message_read.delay(psid)
            if text:
                message_m: Message = Message(
                    conversation=conversation,
                    message_id=mid,
                    text=text,
                    direction=Message.FROM_CUSTOMER,
                )
                message_m.save()
                operator_interface.tasks.process_message.delay(message_m.id)
            if attachments:
                for attachment in attachments:
                    payload = attachment["payload"]
                    att_type: typing.Text = attachment.get("type")
                    if att_type == "image" or att_type == "file":
                        url = payload.get("url")
                        r = requests.get(url)
                        if r.status_code == 200:
                            orig_file_name = os.path.basename(
                                urllib.parse.urlparse(url).path
                            )
                            fs = DefaultStorage()
                            file_name = fs.save(orig_file_name, BytesIO(r.content))

                            if att_type == "image":
                                message_m: Message = Message(
                                    conversation=conversation,
                                    message_id=mid,
                                    image=fs.base_url + file_name,
                                    direction=Message.FROM_CUSTOMER,
                                )
                                message_m.save()
                                operator_interface.tasks.process_message.delay(
                                    message_m.id
                                )
                            else:
                                message_m: Message = Message(
                                    conversation=conversation,
                                    message_id=mid,
                                    direction=Message.FROM_CUSTOMER,
                                    text=f'<a href="{fs.base_url + file_name}" target="_blank">'
                                    f"{orig_file_name}"
                                    f"</a>",
                                )
                                message_m.save()
                                operator_interface.tasks.send_message_to_interface.delay(
                                    message_m.id
                                )
                    elif att_type == "location":
                        message_m: Message = Message(
                            conversation=conversation,
                            message_id=mid,
                            direction=Message.FROM_CUSTOMER,
                            text=f"<a href=\"{attachment.get('url')}\" target=\"_blank\">Location</a>",
                        )
                        message_m.save()
                        operator_interface.tasks.send_message_to_interface.delay(
                            message_m.id
                        )
    else:
        if not Message.message_exits(conversation, mid):
            if text:
                similar_messages: typing.List[Message] = Message.objects.filter(
                    conversation=conversation,
                    text=text,
                    timestamp__gte=timezone.now() - datetime.timedelta(seconds=30),
                )
                if len(similar_messages) == 0:
                    message_m: Message = Message(
                        conversation=conversation,
                        message_id=mid,
                        text=text if text else "",
                        direction=Message.TO_CUSTOMER,
                        delivered=True,
                    )
                    message_m.save()
                    operator_interface.tasks.send_message_to_interface.delay(
                        message_m.id
                    )


@shared_task
def handle_facebook_postback(psid: dict, postback: dict) -> None:
    psid: str = psid["sender"]
    payload: str = postback.get("payload")
    title: str = postback.get("title")
    if payload is not None:
        conversation: Conversation = Conversation.get_or_create_conversation(
            Conversation.FACEBOOK, psid
        )
        payload: dict = json.loads(payload)
        action: str = payload.get("action")
        if action == "start_action":
            operator_interface.tasks.process_event.delay(conversation.id, "WELCOME")
        else:
            operator_interface.tasks.process_event.delay(conversation.id, action)

        message_m: Message = Message(
            conversation=conversation,
            message_id=uuid.uuid4(),
            text=title,
            direction=Message.FROM_CUSTOMER,
        )
        message_m.save()
        handle_mark_facebook_message_read.delay(psid)
        operator_interface.tasks.send_message_to_interface.delay(message_m.id)
        update_facebook_profile.delay(psid, conversation.id)


@shared_task
def handle_facebook_read(psid: dict, read: dict) -> None:
    psid: str = psid["sender"]
    watermark: int = read.get("watermark")
    if watermark is not None:
        conversation: Conversation = Conversation.get_or_create_conversation(
            Conversation.FACEBOOK, psid
        )

        messages = Message.objects.filter(
            conversation=conversation,
            direction=Message.TO_CUSTOMER,
            read=False,
            timestamp__lte=datetime.datetime.fromtimestamp(watermark / 1000),
        )
        message_ids = [m.id for m in messages]
        messages.update(read=True)
        for message in message_ids:
            operator_interface.tasks.send_message_to_interface.delay(message)

        update_facebook_profile.delay(psid, conversation.id)


@shared_task
def update_facebook_profile(psid: str, cid: int) -> None:
    conversation: Conversation = Conversation.objects.get(id=cid)
    r = requests.get(
        f"https://graph.facebook.com/{psid}",
        params={
            "fields": "name,profile_pic,timezone,locale,gender",
            "access_token": settings.FACEBOOK_ACCESS_TOKEN,
        },
    )
    r.raise_for_status()
    r = r.json()
    name = r["name"]
    profile_pic = r["profile_pic"]
    timezone = r.get("timezone", None)
    if timezone < 0:
        timezone = f"Etc/GMT-{abs(timezone)}"
    else:
        timezone = f"Etc/GMT+{abs(timezone)}"
    locale = r.get("locale", None)
    gender = r.get("gender", None)

    pic_r = requests.get(profile_pic)
    if pic_r.status_code == 200:
        conversation.customer_pic = InMemoryUploadedFile(
            file=BytesIO(pic_r.content),
            size=len(pic_r.content),
            charset=pic_r.encoding,
            content_type=pic_r.headers.get("content-type"),
            field_name=psid,
            name=psid,
        )
    conversation.customer_name = name

    admin_client = keycloak_auth.clients.get_keycloak_admin_client()

    if not conversation.conversation_user_id:
        users = admin_client.users.all()
        for user in users:
            user = admin_client.users.by_id(user.get("id")).get()
            facebook_identity = next(
                filter(
                    lambda i: i.get("identityProvider") == "facebook",
                    user.get("federatedIdentities", []),
                ),
                None,
            )
            if facebook_identity:
                app_ids_r = requests.get(
                    f"https://graph.facebook.com/{psid}/ids_for_apps",
                    params={
                        "fields": "id",
                        "access_token": settings.FACEBOOK_ACCESS_TOKEN,
                    },
                )
                app_ids_r.raise_for_status()
                app_ids = app_ids_r.json()
                for app in app_ids.get("data", []):
                    if app.get("id") == facebook_identity.get("userId"):
                        conversation.conversation_user_id = user.get("id")
                        break

    if conversation.conversation_user_id:
        user = admin_client.users.by_id(conversation.conversation_user_id)
        user_data = user.get()
        attributes = user_data.get("attributes", {})
        if gender and not attributes.get("gender"):
            attributes["gender"] = gender
        if locale and not attributes.get("locale"):
            attributes["locale"] = locale
        if timezone and not attributes.get("timezone"):
            attributes["timezone"] = timezone
        user.update(attributes=attributes)

    conversation.save()
    operator_interface.consumers.conversation_saved(None, conversation)


@shared_task
def handle_mark_facebook_message_read(psid: str) -> None:
    requests.post(
        "https://graph.facebook.com/me/messages",
        params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
        json={"recipient": {"id": psid}, "sender_action": "mark_seen"},
    ).raise_for_status()


@shared_task
def handle_facebook_message_typing_on(cid: int) -> None:
    conversation: Conversation = Conversation.objects.get(id=cid)
    requests.post(
        "https://graph.facebook.com/me/messages",
        params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
        json={
            "recipient": {"id": conversation.platform_id},
            "sender_action": "typing_on",
        },
    ).raise_for_status()


@shared_task
def send_facebook_message(mid: int) -> None:
    message: Message = Message.objects.get(id=mid)
    psid: str = message.conversation.platform_id

    persona_id = None
    if message.user is not None:
        try:
            if message.user.userprofile.fb_persona_id is None:
                persona_r = requests.post(
                    "https://graph.facebook.com/me/personas",
                    params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
                    json={
                        "name": message.user.first_name,
                        "profile_picture_url": settings.EXTERNAL_URL_BASE
                        + reverse("operator:profile_pic", args=[message.user.id]),
                    },
                )
                if persona_r.status_code == 200:
                    persona_json = persona_r.json()
                    message.user.userprofile.fb_persona_id = persona_json["id"]
                    message.user.userprofile.save()
                    persona_id = persona_json["id"]
            else:
                persona_id = message.user.userprofile.fb_persona_id
        except User.userprofile.RelatedObjectDoesNotExist:
            pass

    requests.post(
        "https://graph.facebook.com/me/messages",
        params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
        json={"recipient": {"id": psid}, "sender_action": "typing_off"},
    )

    quick_replies = []
    for suggestion in message.messagesuggestion_set.all():
        quick_replies.append(
            {
                "content_type": "text",
                "title": suggestion.suggested_response,
                "payload": suggestion.id,
            }
        )

    request_body = {"recipient": {"id": psid}, "message": {}}

    if persona_id is not None:
        request_body["persona_id"] = persona_id
    if len(quick_replies) > 0:
        request_body["message"]["quick_replies"] = quick_replies

    if message.payment_request:
        request_body["message"]["attachment"] = {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": message.text,
                "buttons": [
                    {
                        "type": "web_url",
                        "url": settings.EXTERNAL_URL_BASE
                        + reverse(
                            "payment:fb_payment",
                            kwargs={"payment_id": message.payment_request.id},
                        ),
                        "title": "Pay",
                        "webview_height_ratio": "compact",
                        "messenger_extensions": True,
                        "webview_share_button": "hide",
                    }
                ],
            },
        }
    elif message.payment_confirm:
        request_body["message"]["attachment"] = {
            "type": "template",
            "payload": {
                "template_type": "receipt",
                "recipient_name": message.payment_confirm.customer.name,
                "merchant_name": "We Will Fix Your PC",
                "timestamp": int(message.payment_confirm.timestamp.timestamp()),
                "order_number": f"{message.payment_confirm.id}",
                "currency": "GBP",
                "payment_method": message.payment_confirm.payment_method,
                "summary": {
                    "subtotal": str(
                        (
                            message.payment_confirm.total / decimal.Decimal("1.2")
                        ).quantize(decimal.Decimal(".01"), rounding=decimal.ROUND_DOWN)
                    ),
                    "total_tax": str(
                        (
                            message.payment_confirm.total * decimal.Decimal("0.2")
                        ).quantize(decimal.Decimal(".01"), rounding=decimal.ROUND_DOWN)
                    ),
                    "total_cost": str(
                        message.payment_confirm.total.quantize(
                            decimal.Decimal(".01"), rounding=decimal.ROUND_DOWN
                        )
                    ),
                },
                "elements": [
                    {
                        "title": item.title,
                        "quantity": item.quantity,
                        "price": str(
                            item.price.quantize(
                                decimal.Decimal(".01"), rounding=decimal.ROUND_DOWN
                            )
                        ),
                    }
                    for item in message.payment_confirm.paymentitem_set.all()
                ],
            },
        }
    elif message.selection:
        selection_data = json.loads(message.selection)
        request_body["message"]["attachment"] = {
            "type": "template",
            "payload": {
                "template_type": "generic",
                "elements": [
                    {
                        "title": item.get("title", ""),
                        "buttons": [
                            {
                                "type": "postback",
                                "title": f"Select {item.get('title', '')}",
                                "payload": json.dumps(
                                    {"action": f'resolve_entity{{"number": "{i+1}"}}'}
                                ),
                            }
                        ],
                    }
                    for i, item in enumerate(selection_data.get("items", []))
                ],
            },
        }
    elif message.text:
        urls = re.findall(
            "(http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)",
            message.text,
        )
        if len(urls) == 1:
            request_body["message"]["attachment"] = {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": message.text,
                    "buttons": [
                        {
                            "type": "web_url",
                            "url": urls[0],
                            "title": "Open",
                            "webview_height_ratio": "full",
                        }
                    ],
                },
            }
        else:
            request_body["message"]["text"] = message.text
    elif message.image:
        request_body["message"]["attachment"] = {
            "type": "image",
            "payload": {"url": message.image},
        }

    message_r = requests.post(
        "https://graph.facebook.com/me/messages",
        params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
        json=request_body,
    )
    if message_r.status_code != 200:
        logging.error(
            f"Error sending facebook message: {message_r.status_code} {message_r.text}"
        )
        request_body = {
            "recipient": {"id": psid},
            "message": {
                "text": "Sorry, I'm having some difficulty processing your request. Please try again later"
            },
        }
        requests.post(
            "https://graph.facebook.com/me/messages",
            params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
            json=request_body,
        ).raise_for_status()
    else:
        message_json = message_r.json()
        mid = message_json["message_id"]
        message.message_id = mid
        message.delivered = True
        message.save()
        operator_interface.consumers.message_saved(None, message)
