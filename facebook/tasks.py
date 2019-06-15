from celery import shared_task
from django.conf import settings
from django.shortcuts import reverse
import requests
from operator_interface.models import Conversation, Message
import operator_interface.tasks
import logging
import json
import uuid
import re
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile


@shared_task
def handle_facebook_message(psid, message):
    text = message.get("text")
    mid = message["mid"]
    is_echo = message.get("is_echo")
    if text is not None:
        psid = psid["sender"] if not is_echo else psid["recipient"]
        conversation = Conversation.get_or_create_conversation(Conversation.FACEBOOK, psid)
        if not is_echo:
            update_facebook_profile(psid, conversation.id)
            if not Message.message_exits(conversation, mid):
                message_m = Message(conversation=conversation, message_id=mid, text=text, direction=Message.FROM_CUSTOMER)
                message_m.save()
                handle_mark_facebook_message_read.delay(psid)
                operator_interface.tasks.process_message.delay(message_m.id)
        else:
            if not Message.message_exits(conversation, mid):
                message_m = Message(conversation=conversation, message_id=mid, text=text, direction=Message.TO_CUSTOMER)
                message_m.save()
                operator_interface.tasks.send_message_to_interface.delay(message_m.id)


@shared_task
def handle_facebook_postback(psid, postback):
    psid = psid["sender"]
    payload = postback.get("payload")
    if payload is not None:
        conversation = Conversation.get_or_create_conversation(Conversation.FACEBOOK, psid)
        payload = json.loads(payload)
        action = payload["action"]
        if action == "start_action":
            operator_interface.tasks.process_event.delay(conversation.id, "WELCOME")
            message_m = Message(conversation=conversation, message_id=uuid.uuid4(), text="Get started",
                                direction=Message.FROM_CUSTOMER)
            message_m.save()
            handle_mark_facebook_message_read.delay(psid)
            operator_interface.tasks.send_message_to_interface.delay(message_m.id)
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
    profile_pic = r["profile_pic"]
    timezone = r['timezone']
    if not conversation.customer_pic or conversation.customer_pic.name != psid:
        r = requests.get(profile_pic)
        if r.status_code == 200:
            conversation.customer_pic = \
                InMemoryUploadedFile(file=BytesIO(r.content), size=len(r.content), charset=r.encoding,
                                     content_type=r.headers.get('content-type'), field_name=psid,
                                     name=psid)
    conversation.customer_name = r['name']
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

    urls = re.findall("(http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)", message.text)

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
