from celery import shared_task
from operator_interface.models import Conversation, Message
from operator_interface.consumers import conversation_saved
import operator_interface.tasks
import requests
import logging
from django.core.files.uploadedfile import InMemoryUploadedFile
import os
import urllib.parse
import re
from io import BytesIO
from . import views


@shared_task
def handle_twitter_message(mid, psid, message, user):
    text = message.get("text")
    if text is not None:
        conversation = Conversation.get_or_create_conversation(Conversation.TWITTER, psid, user["name"],
                                                               f"@{user['screen_name']}", None)
        if not Message.message_exits(conversation, mid):
            message_m = Message(conversation=conversation, message_id=mid, text=text, direction=Message.FROM_CUSTOMER)
            message_m.save()
            handle_mark_twitter_message_read.delay(psid, mid)
            operator_interface.tasks.process_message.delay(message_m.id)
        file_name = os.path.basename(urllib.parse.urlparse(user["profile_image_url_https"]).path)
        if not conversation.customer_pic or conversation.customer_pic.name != file_name:
            r = requests.get(user["profile_image_url_https"])
            if r.status_code == 200:
                conversation.customer_pic = \
                    InMemoryUploadedFile(file=BytesIO(r.content), size=len(r.content), charset=r.encoding,
                                         content_type=r.headers.get('content-type'), field_name=file_name,
                                         name=file_name)
                conversation.save()
                conversation_saved(None, conversation)


@shared_task
def handle_mark_twitter_message_read(psid, mid):
    creds = views.get_creds()
    requests.post("https://api.twitter.com/1.1/direct_messages/mark_read.json", data={
        "last_read_event_id": mid,
        "recipient_id": psid
    }, auth=creds)


@shared_task
def handle_twitter_message_typing_on(cid):
    creds = views.get_creds()
    conversation = Conversation.objects.get(id=cid)
    requests.post("https://api.twitter.com/1.1/direct_messages/indicate_typing.json",
                  data={
                      "recipient_id": conversation.platform_id
                  }, auth=creds)


@shared_task
def send_twitter_message(mid):
    message = Message.objects.get(id=mid)
    psid = message.conversation.platform_id
    creds = views.get_creds()

    quick_replies = []
    for suggestion in message.messagesuggestion_set.all():
        quick_replies.append({
            "label": suggestion.suggested_response,
            "metadata": suggestion.id
        })

    request_body = {
        "event": {
            "type": "message_create",
            "message_create": {
                "target": {
                    "recipient_id": psid
                },
                "message_data": {
                    "text": message.text,
                }
            }
        }
    }

    if len(quick_replies) > 0:
        request_body["event"]["message_create"]["message_data"]["quick_reply"] = {
            "type": "options",
            "options": quick_replies
        }

    urls = re.findall("(http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)", message.text)

    if len(urls) == 1:
        request_body["event"]["message_create"]["message_data"]["ctas"] = [
            {
                "type": "web_url",
                "label": "Open",
                "url": urls[0]
            }
        ]

    r = requests.post("https://api.twitter.com/1.1/direct_messages/events/new.json", auth=creds, json=request_body)
    if r.status_code != 200:
        logging.error(f"Error sending twitter message: {r.status_code} {r.text}")
        request_body = {
            "event": {
                "type": "message_create",
                "message_create": {
                    "target": {
                        "recipient_id": psid
                    },
                    "message_data": {
                        "text": "Sorry, I'm having some difficulty processing your request. Please try again later",
                    }
                }
            }
        }
        requests.post("https://api.twitter.com/1.1/direct_messages/events/new.json", auth=creds, json=request_body) \
            .raise_for_status()
