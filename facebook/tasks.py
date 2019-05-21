from celery import shared_task
from django.conf import settings
import requests
from operator_interface.models import Conversation, Message
import operator_interface.tasks
import logging
import os
import urllib.parse
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile


@shared_task
def handle_facebook_message(psid, message):
    text = message.get("text")
    mid = message["mid"]
    if text is not None:
        conversation = Conversation.get_or_create_conversation(Conversation.FACEBOOK, psid)
        if not Message.message_exits(conversation, mid):
            message_m = Message(conversation=conversation, message_id=mid, text=text, direction=Message.FROM_CUSTOMER)
            message_m.save()
            handle_mark_facebook_message_read.delay(psid)
            operator_interface.tasks.process_message.delay(message_m.id)
        r = requests.get(f"https://graph.facebook.com/{psid}", params={
            "fields": "first_name,last_name,profile_pic",
            "access_token": settings.FACEBOOK_ACCESS_TOKEN
        })
        if r.status_code == 200:
            r = r.json()
            name = f"{r['first_name']} {r['last_name']}"
            profile_pic = r["profile_pic"]
            if not conversation.customer_pic or conversation.customer_pic.name != psid:
                r = requests.get(profile_pic)
                if r.status_code == 200:
                    conversation.customer_pic = \
                        InMemoryUploadedFile(file=BytesIO(r.content), size=len(r.content), charset=r.encoding,
                                             content_type=r.headers.get('content-type'), field_name=psid,
                                             name=psid)
            conversation.customer_name = name
            conversation.save()


@shared_task
def handle_mark_facebook_message_read(psid):
    requests.post("https://graph.facebook.com/v2.6/me/messages",
                  params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
                  json={
                      "recipient": {
                          "id": psid
                      },
                      "sender_action": "mark_seen"
                  })


@shared_task
def handle_facebook_message_typing_on(cid):
    conversation = Conversation.objects.get(id=cid)
    requests.post("https://graph.facebook.com/v2.6/me/messages",
                  params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
                  json={
                      "recipient": {
                          "id": conversation.platform_id
                      },
                      "sender_action": "typing_on"
                  })


@shared_task
def send_facebook_message(mid):
    message = Message.objects.get(id=mid)
    psid = message.conversation.platform_id

    requests.post("https://graph.facebook.com/v2.6/me/messages",
                  params={"access_token": settings.FACEBOOK_ACCESS_TOKEN},
                  json={
                      "recipient": {
                          "id": psid
                      },
                      "sender_action": "typing_off"
                  })

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
        "message": {
            "text": message.text
        }
    }
    if len(quick_replies) > 0:
        request_body["message"]["quick_replies"] = quick_replies
    r = requests.post("https://graph.facebook.com/v2.6/me/messages",
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
        requests.post("https://graph.facebook.com/v2.6/me/messages",
                      params={"access_token": settings.FACEBOOK_ACCESS_TOKEN}, json=request_body).raise_for_status()
