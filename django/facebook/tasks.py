import datetime
import json
import logging
import os.path
import re
import typing
import urllib.parse
import uuid
from io import BytesIO

import django_keycloak_auth.users
import requests
from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import DefaultStorage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.shortcuts import reverse
from django.utils import timezone

import operator_interface.consumers
import operator_interface.tasks
from operator_interface.models import Conversation, ConversationPlatform, Message


@shared_task
def handle_facebook_message(psid: dict, message: dict) -> None:
    text: typing.Text = message.get("text")
    attachments: typing.List[typing.Dict] = message.get("attachments")
    mid: typing.Text = message["mid"]
    is_echo: bool = message.get("is_echo")
    psid: typing.Text = psid["sender"] if not is_echo else psid["recipient"]
    platform: ConversationPlatform = ConversationPlatform.exists(
        ConversationPlatform.FACEBOOK, psid
    )
    if not platform:
        user_id = attempt_get_user_id(psid)
        platform = ConversationPlatform.create(
            ConversationPlatform.FACEBOOK, psid, customer_user_id=user_id
        )
    if not is_echo:
        update_facebook_profile(psid, platform.conversation.id)
        if not Message.message_exits(platform, mid):
            handle_mark_facebook_message_read.delay(psid)
            if text:
                message_m: Message = Message(
                    platform=platform,
                    platform_message_id=mid,
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
                                    platform=platform,
                                    platform_message_id=mid,
                                    image=fs.base_url + file_name,
                                    direction=Message.FROM_CUSTOMER,
                                )
                                message_m.save()
                                operator_interface.tasks.process_message.delay(
                                    message_m.id
                                )
                            else:
                                message_m: Message = Message(
                                    platform=platform,
                                    platform_message_id=mid,
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
                            platform=platform,
                            platform_message_id=mid,
                            direction=Message.FROM_CUSTOMER,
                            text=f"<a href=\"{attachment.get('url')}\" target=\"_blank\">Location</a>",
                        )
                        message_m.save()
                        operator_interface.tasks.send_message_to_interface.delay(
                            message_m.id
                        )
    else:
        if not Message.message_exits(platform, mid):
            message_m: Message = Message(
                platform=platform,
                platform_message_id=mid,
                text=text if text else "",
                direction=Message.TO_CUSTOMER,
                delivered=True,
            )
            message_m.save()
            operator_interface.tasks.send_message_to_interface.delay(message_m.id)


@shared_task
def handle_facebook_postback(psid: dict, postback: dict) -> None:
    psid: str = psid["sender"]
    payload: str = postback.get("payload")
    title: str = postback.get("title")
    if payload is not None:
        platform: ConversationPlatform = ConversationPlatform.exists(
            ConversationPlatform.FACEBOOK, psid
        )
        if not platform:
            user_id = attempt_get_user_id(psid)
            platform = ConversationPlatform.create(
                ConversationPlatform.FACEBOOK, psid, customer_user_id=user_id
            )
        payload: dict = json.loads(payload)
        action: str = payload.get("action")
        if action == "start_action":
            operator_interface.tasks.process_event.delay(platform.id, "WELCOME")
        else:
            operator_interface.tasks.process_event.delay(platform.id, action)

        message_m: Message = Message(
            platform=platform,
            message_id=uuid.uuid4(),
            text=title,
            direction=Message.FROM_CUSTOMER,
        )
        message_m.save()
        handle_mark_facebook_message_read.delay(psid)
        operator_interface.tasks.send_message_to_interface.delay(message_m.id)
        update_facebook_profile.delay(psid, platform.conversation.id)


@shared_task
def handle_facebook_read(psid: dict, read: dict) -> None:
    psid: str = psid["sender"]
    watermark: int = read.get("watermark")
    if watermark is not None:
        platform: ConversationPlatform = ConversationPlatform.exists(
            ConversationPlatform.FACEBOOK, psid
        )
        if platform:
            messages = Message.objects.filter(
                platform=platform,
                direction=Message.TO_CUSTOMER,
                state=Message.DELIVERED,
                timestamp__lte=datetime.datetime.fromtimestamp(watermark / 1000),
            )
            message_ids = [m.id for m in messages]
            messages.update(read=True)
            for message in message_ids:
                operator_interface.tasks.send_message_to_interface.delay(message)

            update_facebook_profile.delay(psid, platform.conversation.id)


def attempt_get_user_id(psid: str) -> str:
    profile_r = requests.get(
        f"https://graph.facebook.com/{psid}",
        params={
            "fields": "ids_for_apps",
            "access_token": settings.FACEBOOK_ACCESS_TOKEN,
        },
    )
    profile_r.raise_for_status()
    profile = profile_r.json()
    app_ids = profile.get("ids_for_apps", {}).get("data", [])

    def check_asid_with_psid(identity):
        for app in app_ids:
            if app.get("id") == identity.get("userId"):
                return True
        return False

    user = django_keycloak_auth.users.get_or_create_user(
        federated_provider="facebook", check_federated_user=check_asid_with_psid,
    )
    if user:
        django_keycloak_auth.users.link_roles_to_user(user.get("id"), ["customer"])
        return user.get("id")


@shared_task
def update_facebook_profile(psid: str, cid) -> None:
    conversation: Conversation = Conversation.objects.get(id=cid)
    profile_r = requests.get(
        f"https://graph.facebook.com/{psid}",
        params={
            "fields": "name,profile_pic,timezone,locale,gender,first_name,last_name",
            "access_token": settings.FACEBOOK_ACCESS_TOKEN,
        },
    )
    profile_r.raise_for_status()
    profile = profile_r.json()
    name = profile.get("name")
    first_name = profile.get("first_name")
    last_name = profile.get("last_name")
    profile_pic = profile.get("profile_pic")
    user_timezone = profile.get("timezone")
    if user_timezone < 0:
        user_timezone = f"Etc/GMT-{abs(user_timezone)}"
    else:
        user_timezone = f"Etc/GMT+{abs(user_timezone)}"
    locale = profile.get("locale")
    gender = profile.get("gender")

    if not conversation.conversation_pic:
        pic_r = requests.get(profile_pic)
        if pic_r.status_code == 200:
            conversation.conversation_pic.save(psid, InMemoryUploadedFile(
                file=BytesIO(pic_r.content),
                size=len(pic_r.content),
                charset=pic_r.encoding,
                content_type=pic_r.headers.get("content-type"),
                field_name=psid,
                name=psid,
            ))
    if not conversation.conversation_name:
        conversation.conversation_name = name
    conversation.save()

    if conversation.conversation_user_id:
        django_keycloak_auth.users.update_user(
            str(conversation.conversation_user_id),
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            locale=locale,
            timezone=user_timezone,
            force_update=False,
        )
        if conversation.conversation_pic:
            django_keycloak_auth.users.update_user(
                str(conversation.conversation_user_id),
                profile_pictrue=conversation.conversation_pic.url,
                force_update=False,
            )


@shared_task
def handle_mark_facebook_message_read(psid: str) -> None:
    requests.post(
        "https://graph.facebook.com/me/messages",
        params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
        json={"recipient": {"id": psid}, "sender_action": "mark_seen"},
    ).raise_for_status()


@shared_task
def handle_facebook_message_typing_on(pid: int) -> None:
    platform: ConversationPlatform = ConversationPlatform.objects.get(id=pid)
    requests.post(
        "https://graph.facebook.com/me/messages",
        params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
        json={
            "recipient": {"id": platform.platform_id},
            "sender_action": "typing_on",
        },
    ).raise_for_status()


@shared_task
def send_facebook_message(mid: int) -> None:
    message: Message = Message.objects.get(id=mid)
    psid: str = message.platform.platform_id

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

    # TODO: Integrate with new system
    if message.payment_request:
        magic_key = django_keycloak_auth.users.get_user_magic_key(
            message.platform.conversation.conversation_user_id, 86400
        ).get("key")
        request_body["message"]["attachment"] = {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": message.text,
                "buttons": [
                    {
                        "type": "web_url",
                        "url": settings.PAYMENT_EXTERNAL_URL
                        + f"/payment/fb/{message.payment_request}/?key={magic_key}",
                        "title": "Pay",
                        "webview_height_ratio": "tall",
                        "messenger_extensions": True,
                        "webview_share_button": "hide",
                    }
                ],
            },
        }
    # elif message.payment_confirm:
    #     user = django_keycloak_auth.users.get_user_by_id(message.payment_confirm.customer_id)
    #
    #     request_body["message"]["attachment"] = {
    #         "type": "template",
    #         "payload": {
    #             "template_type": "receipt",
    #             "recipient_name": user.user.get("name"),
    #             "merchant_name": "We Will Fix Your PC",
    #             "timestamp": int(message.payment_confirm.timestamp.timestamp()),
    #             "order_number": f"{message.payment_confirm.id}",
    #             "currency": "GBP",
    #             "payment_method": message.payment_confirm.payment_method,
    #             "summary": {
    #                 "subtotal": str(
    #                     (
    #                         message.payment_confirm.total / decimal.Decimal("1.2")
    #                     ).quantize(decimal.Decimal(".01"), rounding=decimal.ROUND_DOWN)
    #                 ),
    #                 "total_tax": str(
    #                     (
    #                         message.payment_confirm.total * decimal.Decimal("0.2")
    #                     ).quantize(decimal.Decimal(".01"), rounding=decimal.ROUND_DOWN)
    #                 ),
    #                 "total_cost": str(
    #                     message.payment_confirm.total.quantize(
    #                         decimal.Decimal(".01"), rounding=decimal.ROUND_DOWN
    #                     )
    #                 ),
    #             },
    #             "elements": [
    #                 {
    #                     "title": item.title,
    #                     "quantity": item.quantity,
    #                     "price": str(
    #                         item.price.quantize(
    #                             decimal.Decimal(".01"), rounding=decimal.ROUND_DOWN
    #                         )
    #                     ),
    #                 }
    #                 for item in message.payment_confirm.paymentitem_set.all()
    #             ],
    #         },
    #     }
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
                                    {"action": f'resolve_entity{{"number": "{i + 1}"}}'}
                                ),
                            }
                        ],
                    }
                    for i, item in enumerate(selection_data.get("items", []))
                ],
            },
        }
    elif message.request == "sign_in":
        request_body["message"]["attachment"] = {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": message.text,
                "buttons": [
                    {
                        "type": "account_link",
                        "url": settings.EXTERNAL_URL_BASE
                        + reverse("facebook:account_linking"),
                    }
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
        message.platform_message_id = mid
        message.state = Message.DELIVERED
        message.save()
