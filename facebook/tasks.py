from celery import shared_task
from django.conf import settings
import requests
from operator_interface.models import Conversation, Message
import operator_interface.tasks


@shared_task
def handle_facebook_message(psid, message):
    text = message.get("text")
    mid = message["mid"]
    if text is not None:
        conversation = Conversation.get_or_create_conversation(Conversation.FACEBOOK, psid)
        if not Message.message_exits(conversation, mid):
            message_m = Message(conversation=conversation, message_id=mid, text=text, direction=Message.FROM_CUSTOMER)
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)


@shared_task
def send_facebook_message(mid):
    message = Message.objects.get(id=mid)
    psid = message.conversation.platform_id
    request_body = {
        "recipient": {
            "id": psid
        },
        "message": {
            "text": message.text
        }
    }
    r = requests.post("https://graph.facebook.com/v2.6/me/messages",
                      params={"access_token": settings.FACEBOOK_ACCESS_TOKEN}, json=request_body)
    r.raise_for_status()
