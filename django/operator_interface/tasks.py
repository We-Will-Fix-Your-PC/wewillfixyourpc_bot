import json
import uuid
import sentry_sdk
import requests

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from pywebpush import webpush, WebPushException

import facebook.tasks
import rasa_api.tasks
import rasa_api.actions
import telegram_bot.tasks
import twitter.tasks
import azure_bot.tasks
import customer_chat.tasks
import keycloak.exceptions
import django_keycloak_auth.clients
from django.utils import timezone
from . import consumers, models
from django.contrib.auth.models import User

channel_layer = get_channel_layer()


@shared_task
def send_message_to_interface(mid):
    async_to_sync(channel_layer.group_send)(
        "operator_interface", {"type": "message", "mid": mid}
    )


@shared_task
def send_push_notification(sid, data):
    subscription = models.NotificationSubscription.objects.get(id=sid)
    try:
        webpush(
            subscription_info=subscription.subscription_info_json,
            data=json.dumps(data),
            vapid_private_key=settings.PUSH_PRIV_KEY,
            vapid_claims={
                "sub": "mailto:q@misell.cymru",
            },
        )
    except WebPushException as e:
        sentry_sdk.capture_exception(e)
        if e.response.status_code in [404, 410]:
            subscription.delete()


@shared_task
def send_message_notifications(data):
    if data["type"] == "alert":
        subscriptions = models.NotificationSubscription.objects.all()
    else:
        conversation = models.Conversation.objects.get(id=data["cid"])
        subscriptions = models.NotificationSubscription.objects.filter(
            user=conversation.current_agent
        )

    for subscription in subscriptions:
        send_push_notification.delay(subscription.id, data)


@shared_task
def extract_entities_from_message(mid):
    message = models.Message.objects.get(id=mid)

    r = requests.post(
        settings.RASA_HTTP_URL + "/model/parse", json={"text": message.text}
    )
    r.raise_for_status()
    data = r.json()

    message.guessed_intent = data.get("intent")
    message.save()

    for match in data.get("entities", []):
        match_o = models.MessageEntity(
            message=message, entity=match["entity"], value=json.dumps(match["value"])
        )
        match_o.save()


@shared_task
def process_message(mid: int):
    message: models.Message = models.Message.objects.get(id=mid)
    platform = message.platform
    conversation = platform.conversation

    send_message_to_interface.delay(mid)

    if message.direction == models.Message.FROM_CUSTOMER:
        extract_entities_from_message.delay(mid)
        if conversation.agent_responding:
            return rasa_api.tasks.handle_message(mid)
        else:
            if (
                platform.messages.filter(
                    timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
                ).count()
                == 1
            ):
                send_welcome_message.delay(platform.id)

            admin_client = django_keycloak_auth.clients.get_keycloak_admin_client()
            if conversation.conversation_user_id:
                try:
                    user = admin_client.users.by_id(conversation.conversation_user_id).user
                    name = f'{user.get("firstName", "")} {user.get("lastName", "")}'
                except keycloak.exceptions.KeycloakClientError:
                    name = conversation.conversation_name
            else:
                name = conversation.conversation_name

            send_message_notifications(
                {
                    "type": "message",
                    "cid": conversation.id,
                    "name": name,
                    "text": message.text,
                }
            )

    elif message.direction == models.Message.TO_CUSTOMER:
        platform = message.platform.platform
        if platform == models.ConversationPlatform.FACEBOOK:
            facebook.tasks.send_facebook_message(mid)
        elif platform == models.ConversationPlatform.TWITTER:
            twitter.tasks.send_twitter_message(mid)
        elif platform == models.ConversationPlatform.TELEGRAM:
            telegram_bot.tasks.send_telegram_message(mid)
        elif platform == models.ConversationPlatform.AZURE:
            azure_bot.tasks.send_azure_message(mid)
        elif platform == models.ConversationPlatform.CHAT:
            customer_chat.tasks.send_message(mid)
        elif platform == models.ConversationPlatform.GOOGLE_ACTIONS:
            return mid

    return None


@shared_task
def process_event(pid, event):
    if event == "WELCOME":
        platform = models.ConversationPlatform.objects.get(id=pid)
        # conversation.agent_responding = True
        platform.conversation.current_agent = None
        platform.conversation.save()

    return rasa_api.tasks.handle_event(pid, event)


@shared_task
def hand_back(cid):
    conversation = models.Conversation.objects.get(id=cid)
    conversation.agent_responding = True
    conversation.current_agent = None
    conversation.save()
    message = models.Message(
        message_id=uuid.uuid4(),
        platform=conversation.last_usable_platform("HUMAN_AGENT"),
        direction=models.Message.TO_CUSTOMER,
        text=f"You've been handed back to the automated assistant.\n"
        f"You can always request an agent at any time by saying 'request an agent'.",
    )
    message.save()
    process_message(message.id)


@shared_task
def send_welcome_message(pid):
    if rasa_api.actions.is_open():
        text = "We're currently open and someone will be with you shortly."
    else:
        text = "We're currently closed, but someone will get back to you as soon as we're open again."

    platform = models.ConversationPlatform.objects.get(id=pid)
    message = models.Message(
        message_id=uuid.uuid4(),
        platform=platform,
        direction=models.Message.TO_CUSTOMER,
        text=f"Welcome to We Will Fix Your PC.\n{text}",
    )
    message.save()
    process_message(message.id)


@shared_task
def end_conversation(cid):
    conversation = models.Conversation.objects.get(id=cid)
    # conversation.agent_responding = True
    conversation.current_agent = None
    conversation.save()
    # if conversation.agent_responding:
    #     process_event(cid, "end")
    message = models.Message(
        message_id=uuid.uuid4(),
        platform=conversation.last_usable_platform("HUMAN_AGENT"),
        direction=models.Message.TO_CUSTOMER,
        text=f"Thanks for contacting We Will Fix Your PC."
        f" On a scale of 1 to 10 how would you rate your experience with us?",
    )
    message.save()
    process_message(message.id)


@shared_task
def take_over(cid, uid):
    conversation = models.Conversation.objects.get(id=cid)
    user = User.objects.get(id=uid)
    conversation.agent_responding = False
    conversation.current_agent = user
    conversation.save()
    message = models.Message(
        message_id=uuid.uuid4(),
        platform=conversation.last_usable_platform("HUMAN_AGENT"),
        direction=models.Message.TO_CUSTOMER,
        user=user,
        text=f"Hello I'm {user.first_name} and I'll be taking over from here",
    )
    message.save()
    process_message(message.id)


@shared_task
def process_typing(pid):
    platform = models.ConversationPlatform.objects.get(id=pid)
    if platform.platform == models.ConversationPlatform.FACEBOOK:
        facebook.tasks.handle_facebook_message_typing_on(pid)
    elif platform.platform == models.ConversationPlatform.TWITTER:
        twitter.tasks.handle_twitter_message_typing_on(pid)
    elif platform.platform == models.ConversationPlatform.TELEGRAM:
        telegram_bot.tasks.handle_telegram_message_typing_on(pid)
