from celery import shared_task
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
def process_message(mid):
    message = models.Message.objects.get(id=mid)
    conversation = message.conversation

    send_message_to_interface.delay(mid)

    if message.direction == models.Message.FROM_CUSTOMER:
        if conversation.agent_responding:
            dialogflow_client.tasks.handle_message.delay(mid)

    elif message.direction == models.Message.TO_CUSTOMER:
        if conversation.platform == models.Conversation.FACEBOOK:
            facebook.tasks.send_facebook_message.delay(mid)


@shared_task
def process_typing(cid):
    conversation = models.Conversation.objects.get(id=cid)
    if conversation.platform == models.Conversation.FACEBOOK:
        facebook.tasks.handle_facebook_message_typing_on.delay(cid)
    elif conversation.platform == models.Conversation.TWITTER:
        twitter.tasks.handle_twitter_message_typing_on.delay(cid)
