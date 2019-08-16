import json
import uuid

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from pywebpush import webpush, WebPushException

import facebook.tasks
import rasa_api.tasks
import telegram_bot.tasks
import twitter.tasks
import azure_bot.tasks
from . import consumers, models
from django.contrib.auth.models import User

channel_layer = get_channel_layer()


@shared_task
def send_message_to_interface(mid):
    async_to_sync(channel_layer.group_send)("operator_interface", {
        "type": "message",
        "mid": mid
    })


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
                "aud": "https://cardifftec.uk"
            }
        )
    except WebPushException as e:
        if e.response.status_code in [404, 410]:
            subscription.delete()
        else:
            print(e.response.text)


@shared_task
def send_message_notifications(data):
    if data["type"] == "alert":
        subscriptions = models.NotificationSubscription.objects.all()
    else:
        conversation = models.Conversation.objects.get(id=data["cid"])
        subscriptions = models.NotificationSubscription.objects.filter(user=conversation.current_agent)

    for subscription in subscriptions:
        send_push_notification.delay(subscription.id, data)


@shared_task
def process_message(mid):
    message = models.Message.objects.get(id=mid)
    conversation = message.conversation

    send_message_to_interface.delay(mid)

    if message.direction == models.Message.FROM_CUSTOMER:
        if conversation.agent_responding:
            rasa_api.tasks.handle_message(mid)
        else:
            send_message_notifications({
                "type": "message",
                "cid": message.conversation.id,
                "name": message.conversation.customer_name,
                "text": message.text
            })

    elif message.direction == models.Message.TO_CUSTOMER:
        if conversation.platform == models.Conversation.FACEBOOK:
            facebook.tasks.send_facebook_message(mid)
        elif conversation.platform == models.Conversation.TWITTER:
            twitter.tasks.send_twitter_message(mid)
        elif conversation.platform == models.Conversation.TELEGRAM:
            telegram_bot.tasks.send_telegram_message(mid)
        elif conversation.platform == models.Conversation.AZURE:
            azure_bot.tasks.send_azure_message(mid)


@shared_task
def process_event(cid, event):
    rasa_api.tasks.handle_event(cid, event)


@shared_task
def hand_back(cid):
    conversation = models.Conversation.objects.get(id=cid)
    conversation.agent_responding = True
    conversation.current_agent = None
    conversation.save()
    consumers.conversation_saved(None, conversation)
    message = models.Message(
        message_id=uuid.uuid4(), conversation=conversation, direction=models.Message.TO_CUSTOMER,
        text=f"You've been handed back to the automated assistant.\n"
             f"You can always request an agent at any time you wish.")
    message.save()
    process_message(message.id)


@shared_task
def end_conversation(cid):
    conversation = models.Conversation.objects.get(id=cid)
    conversation.agent_responding = True
    conversation.current_agent = None
    conversation.save()
    consumers.conversation_saved(None, conversation)
    process_event.delay(cid, "end")


@shared_task
def take_over(cid, uid):
    conversation = models.Conversation.objects.get(id=cid)
    user = User.objects.get(id=uid)
    conversation.agent_responding = False
    conversation.current_agent = user
    conversation.save()
    consumers.conversation_saved(None, conversation)
    message = models.Message(
        message_id=uuid.uuid4(), conversation=conversation, direction=models.Message.TO_CUSTOMER, user=user,
        text=f"Hello I'm {user.first_name} and I'll be taking over from here")
    message.save()
    process_message(message.id)


@shared_task
def process_typing(cid):
    conversation = models.Conversation.objects.get(id=cid)
    if conversation.platform == models.Conversation.FACEBOOK:
        facebook.tasks.handle_facebook_message_typing_on(cid)
    elif conversation.platform == models.Conversation.TWITTER:
        twitter.tasks.handle_twitter_message_typing_on(cid)
    elif conversation.platform == models.Conversation.TELEGRAM:
        telegram_bot.tasks.handle_telegram_message_typing_on(cid)
