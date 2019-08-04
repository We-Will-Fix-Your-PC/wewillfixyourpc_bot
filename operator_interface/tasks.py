from celery import shared_task
from django.conf import settings
from pywebpush import webpush
import rasa_api.tasks
import dialogflow_client.tasks
import facebook.tasks
import twitter.tasks
import pika
import json
from . import models

_channel = None


def get_channel():
    global _channel
    if _channel is not None:
        return _channel
    rmq = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    channel = rmq.channel()
    channel.exchange_declare(exchange='bot_messages', exchange_type='fanout')
    _channel = channel
    return channel


@shared_task
def send_message_to_interface(mid):
    get_channel().basic_publish(exchange='bot_messages', routing_key='', body=json.dumps({
        "mid": mid
    }))


@shared_task
def send_push_notification(sid, data):
    subscription = models.NotificationSubscription.objects.get(id=sid)
    webpush(
        subscription_info=subscription.subscription_info_json,
        data=json.dumps(data),
        vapid_private_key=settings.PUSH_PRIV_KEY,
        vapid_claims={
            "sub": "mailto:q@misell.cymru",
            "aud": "https://cardifftec.uk"
        }
    )


@shared_task
def send_message_notifications(data):
    subscriptions = models.NotificationSubscription.objects.all()
    for subscription in subscriptions:
        send_push_notification.delay(subscription.id, data)


@shared_task
def process_message(mid):
    message = models.Message.objects.get(id=mid)
    conversation = message.conversation

    send_message_to_interface.delay(mid)

    if message.direction == models.Message.FROM_CUSTOMER:
        if conversation.agent_responding:
            dialogflow_client.tasks.handle_message(mid)
        else:
            send_message_notifications({
                "type": "message",
                "name": message.conversation.customer_name,
                "text": message.text
            })

    elif message.direction == models.Message.TO_CUSTOMER:
        if conversation.platform == models.Conversation.FACEBOOK:
            facebook.tasks.send_facebook_message(mid)


@shared_task
def process_event(cid, event):
    dialogflow_client.tasks.handle_event(cid, event)


@shared_task
def hand_back(cid):
    conversation = models.Conversation.objects.get(id=cid)
    conversation.agent_responding = True
    conversation.save()


@shared_task
def process_typing(cid):
    conversation = models.Conversation.objects.get(id=cid)
    if conversation.platform == models.Conversation.FACEBOOK:
        facebook.tasks.handle_facebook_message_typing_on(cid)
    elif conversation.platform == models.Conversation.TWITTER:
        twitter.tasks.handle_twitter_message_typing_on(cid)
