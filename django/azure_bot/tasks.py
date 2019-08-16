from celery import shared_task

import datetime
import json
import requests
import operator_interface.consumers
import operator_interface.tasks
from operator_interface.models import Conversation, Message
from django.conf import settings

from . import models


def event_to_conversation(msg):
    from_id = msg["conversation"]["id"]
    customer_name = msg["from"].get("name")

    additional_id = json.dumps({
        "to": msg["from"]["id"],
        "from": msg["recipient"]["id"],
        "endpoint": msg["serviceUrl"]
    })

    conversation = Conversation.get_or_create_conversation(
        Conversation.AZURE, from_id, customer_name=customer_name, from_id=additional_id)
    return conversation


def get_access_token():
    tokens = models.AccessToken.objects.all()
    valid_tokens = []

    for token in tokens:
        if token.expires_at <= datetime.datetime.now():
            token.delete()
        else:
            valid_tokens.append(token.token)

    if len(valid_tokens):
        return valid_tokens.pop()

    r = requests.post("https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token", data={
        "grant_type": "client_credentials",
        "client_id": settings.AZURE_APP_ID,
        "client_secret": settings.AZURE_APP_PASSWORD,
        "oauth": "https://api.botframework.com/.default"
    })
    r.raise_for_status()
    data = r.json()

    token = models.AccessToken(token=data["access_token"])
    token.expires_at = datetime.datetime.now() + datetime.timedelta(seconds=data["expires_in"])
    token.save()

    return token.token


@shared_task
def handle_azure_contact_relation_update(msg):
    conversation = event_to_conversation(msg)

    if msg["action"] == "add":
        operator_interface.tasks.process_event.delay(conversation.id, "WELCOME")


@shared_task
def handle_azure_conversation_update(msg):
    from_id = msg["conversation"]["id"]

    send_welcome = bool(len(Conversation.objects.filter(platform=Conversation.AZURE, platform_id=from_id)))

    conversation = event_to_conversation(msg)

    if send_welcome:
        operator_interface.tasks.process_event.delay(conversation.id, "WELCOME")


@shared_task
def send_azure_message(mid):
    message = Message.objects.get(id=mid)
    access_token = get_access_token()
    additional_id = json.loads(message.conversation.platform_from_id)

    endpoint = f"{additional_id['endpoint']}/v3/conversations/{message.conversation.platform_id}/activities"

    r = requests.post(endpoint, headers={
        "Authorization": f"Bearer {access_token}"
    })
    print(r.content)
