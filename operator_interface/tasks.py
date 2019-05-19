from celery import shared_task
import dialogflow_client.tasks
import facebook.tasks
from . import models


@shared_task
def process_message(mid):
    message = models.Message.objects.get(id=mid)
    conversation = message.conversation

    if message.direction == models.Message.FROM_CUSTOMER:
        if conversation.agent_responding:
            dialogflow_client.tasks.handle_message.delay(mid)

    elif message.direction == models.Message.TO_CUSTOMER:
        if conversation.platform == models.Conversation.FACEBOOK:
            facebook.tasks.send_facebook_message.delay(mid)
