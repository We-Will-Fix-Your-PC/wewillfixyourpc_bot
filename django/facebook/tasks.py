import datetime
import json
import logging
import re
import uuid
import os.path
import decimal
import urllib.parse
from io import BytesIO

import requests
from celery import shared_task
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.storage import DefaultStorage
from django.shortcuts import reverse
from django.utils import timezone

import operator_interface.tasks
from operator_interface.models import Conversation, Message


@shared_task
def handle_facebook_message(psid, message):
    text = message.get("text")
    attachments = message.get("attachments")
    mid = message["mid"]
    is_echo = message.get("is_echo")
    psid = psid["sender"] if not is_echo else psid["recipient"]
    conversation = Conversation.get_or_create_conversation(Conversation.FACEBOOK, psid)
    if not is_echo:
        update_facebook_profile(psid, conversation.id)
        if not Message.message_exits(conversation, mid):
            handle_mark_facebook_message_read.delay(psid)
            if text:
                message_m = Message(conversation=conversation, message_id=mid, text=text,
                                    direction=Message.FROM_CUSTOMER)
                message_m.save()
                operator_interface.tasks.process_message.delay(message_m.id)
            if attachments:
                for attachment in attachments:
                    payload = attachment["payload"]
                    att_type = attachment.get("type")
                    if att_type == "image" or att_type == "file":
                        url = payload.get("url")
                        r = requests.get(url)
                        if r.status_code == 200:
                            orig_file_name = os.path.basename(urllib.parse.urlparse(url).path)
                            fs = DefaultStorage()
                            file_name = fs.save(orig_file_name, BytesIO(r.content))

                            if att_type == "image":
                                message_m = Message(
                                    conversation=conversation, message_id=mid, image=fs.base_url + file_name,
                                    direction=Message.FROM_CUSTOMER
                                )
                                message_m.save()
                                operator_interface.tasks.process_message.delay(message_m.id)
                            else:
                                message_m = Message(
                                    conversation=conversation, message_id=mid, direction=Message.FROM_CUSTOMER,
                                    text=f"<a href=\"{fs.base_url + file_name}\" target=\"_blank\">"
                                         f"{orig_file_name}"
                                         f"</a>",
                                )
                                message_m.save()
                                operator_interface.tasks.send_message_to_interface.delay(message_m.id)
                    elif att_type == "location":
                        message_m = Message(
                            conversation=conversation, message_id=mid, direction=Message.FROM_CUSTOMER,
                            text=f"<a href=\"{attachment.get('url')}\" target=\"_blank\">Location</a>",
                        )
                        message_m.save()
                        operator_interface.tasks.send_message_to_interface.delay(message_m.id)
    else:
        if not Message.message_exits(conversation, mid):
            similar_messages = \
                Message.objects.filter(conversation=conversation, text=text,
                                       timestamp__gte=timezone.now() - datetime.timedelta(seconds=30))
            if len(similar_messages) == 0:
                message_m = \
                    Message(conversation=conversation, message_id=mid, text=text if text else "", direction=Message.TO_CUSTOMER)
                message_m.save()
                operator_interface.tasks.send_message_to_interface.delay(message_m.id)


@shared_task
def handle_facebook_postback(psid, postback):
    psid = psid["sender"]
    payload = postback.get("payload")
    title = postback.get("title")
    if payload is not None:
        conversation = Conversation.get_or_create_conversation(Conversation.FACEBOOK, psid)
        payload = json.loads(payload)
        action = payload.get("action")
        if action == "start_action":
            operator_interface.tasks.process_event.delay(conversation.id, "WELCOME")
        else:
            operator_interface.tasks.process_event.delay(conversation.id, action)

        message_m = Message(conversation=conversation, message_id=uuid.uuid4(), text=title,
                            direction=Message.FROM_CUSTOMER)
        message_m.save()
        handle_mark_facebook_message_read.delay(psid)
        operator_interface.tasks.send_message_to_interface.delay(message_m.id)
        update_facebook_profile.delay(psid, conversation.id)


@shared_task
def handle_facebook_read(psid, read):
    psid = psid["sender"]
    watermark = read.get("watermark")
    if watermark is not None:
        conversation = Conversation.get_or_create_conversation(Conversation.FACEBOOK, psid)

        messages = Message.objects.filter(
            conversation=conversation, direction=Message.TO_CUSTOMER, read=False,
            timestamp__lte=datetime.datetime.fromtimestamp(watermark/1000)
        )
        message_ids = [m.id for m in messages]
        messages.update(read=True)
        for message in message_ids:
            operator_interface.tasks.send_message_to_interface.delay(message)

        update_facebook_profile.delay(psid, conversation.id)


@shared_task
def update_facebook_profile(psid, cid):
    conversation = Conversation.objects.get(id=cid)
    r = requests.get(f"https://graph.facebook.com/{psid}", params={
        "fields": "name,profile_pic,timezone",
        "access_token": settings.FACEBOOK_ACCESS_TOKEN
    })
    r.raise_for_status()
    r = r.json()
    name = r['name']
    profile_pic = r["profile_pic"]
    timezone = r['timezone']
    if not conversation.customer_pic or conversation.customer_pic.name != psid:
        r = requests.get(profile_pic)
        if r.status_code == 200:
            conversation.customer_pic = \
                InMemoryUploadedFile(file=BytesIO(r.content), size=len(r.content), charset=r.encoding,
                                     content_type=r.headers.get('content-type'), field_name=psid,
                                     name=psid)
    conversation.customer_name = name
    if timezone < 0:
        conversation.timezone = f"Etc/GMT-{abs(timezone)}"
    else:
        conversation.timezone = f"Etc/GMT+{abs(timezone)}"
    conversation.save()


@shared_task
def handle_mark_facebook_message_read(psid):
    requests.post("https://graph.facebook.com/me/messages",
                  params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
                  json={
                      "recipient": {
                          "id": psid
                      },
                      "sender_action": "mark_seen"
                  }).raise_for_status()


@shared_task
def handle_facebook_message_typing_on(cid):
    conversation = Conversation.objects.get(id=cid)
    requests.post("https://graph.facebook.com/me/messages",
                  params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
                  json={
                      "recipient": {
                          "id": conversation.platform_id
                      },
                      "sender_action": "typing_on"
                  }).raise_for_status()


@shared_task
def send_facebook_message(mid):
    message = Message.objects.get(id=mid)
    psid = message.conversation.platform_id

    persona_id = None
    if message.user is not None:
        if message.user.userprofile.fb_persona_id is None:
            r = requests.post("https://graph.facebook.com/me/personas",
                              params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
                              json={
                                  "name": message.user.first_name,
                                  "profile_picture_url": settings.EXTERNAL_URL_BASE
                                                         + reverse("operator:profile_pic", args=[message.user.id]),
                              })
            if r.status_code == 200:
                r = r.json()
                message.user.userprofile.fb_persona_id = r["id"]
                message.user.userprofile.save()
                persona_id = r["id"]
        else:
            persona_id = message.user.userprofile.fb_persona_id

    requests.post("https://graph.facebook.com/me/messages",
                  params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
                  json={
                      "recipient": {
                          "id": psid
                      },
                      "sender_action": "typing_off"
                  }).raise_for_status()

    quick_replies = []
    for suggestion in message.messagesuggestion_set.all():
        quick_replies.append({
            "content_type": "text",
            "title": suggestion.suggested_response,
            "payload": suggestion.id
        })

    request_body = {
        "recipient": {
            "id": psid
        },
        "message": {}
    }

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
                        "url": settings.EXTERNAL_URL_BASE + reverse(
                            "payment:fb_payment", kwargs={"payment_id": message.payment_request.id}
                        ),
                        "title": "Pay",
                        "webview_height_ratio": "compact",
                        "messenger_extensions": True,
                        "webview_share_button": "hide",
                    }
                ]
            }
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
                    "subtotal": (message.payment_confirm.total / decimal.Decimal('1.2'))
                        .quantize(decimal.Decimal('.01'), rounding=decimal.ROUND_DOWN),
                    "total_tax": (message.payment_confirm.total * decimal.Decimal('0.2'))
                        .quantize(decimal.Decimal('.01'), rounding=decimal.ROUND_DOWN),
                    "total_cost": message.payment_confirm.total
                        .quantize(decimal.Decimal('.01'), rounding=decimal.ROUND_DOWN)
                },
                "elements": [{
                    "title": item.title,
                    "quantity": item.quantity,
                    "price": item.price,
                } for item in message.payment_confirm.paymentitem_set.all()]
            }
        }
    elif message.text:
        urls = re.findall("(http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)",
                          message.text)
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
                            "webview_height_ratio": "full"
                        }
                    ]
                }
            }
        else:
            request_body["message"]["text"] = message.text
    elif message.image:
        request_body["message"]["attachment"] = {
            "type": "image",
            "payload": {
                "url": message.image,
            }
        }

    r = requests.post("https://graph.facebook.com/me/messages",
                      params={"access_token": settings.FACEBOOK_ACCESS_TOKEN}, json=request_body)
    if r.status_code != 200:
        logging.error(f"Error sending facebook message: {r.status_code} {r.text}")
        request_body = {
            "recipient": {
                "id": psid
            },
            "message": {
                "text": "Sorry, I'm having some difficulty processing your request. Please try again later"
            }
        }
        requests.post("https://graph.facebook.com/me/messages",
                      params={"access_token": settings.FACEBOOK_ACCESS_TOKEN}, json=request_body).raise_for_status()
