from celery import shared_task
import dialogflow_client.tasks
from . import models


@shared_task
def process_message(mid):
    message = models.Message.objects.get(id=mid)
    conversation = message.conversation

    if conversation.agent_responding:
        dialogflow_client.tasks.handle_message.delay(mid)
