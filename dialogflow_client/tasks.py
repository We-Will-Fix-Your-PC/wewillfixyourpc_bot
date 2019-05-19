import dialogflow_v2 as dialogflow
from google.oauth2 import service_account
from django.conf import settings
from operator_interface.models import Message
from celery import shared_task
import operator_interface.tasks
import logging
import secrets

credentials = service_account.Credentials.from_service_account_file(settings.GOOGLE_CREDENTIALS_FILE)
session_client = dialogflow.SessionsClient(credentials=credentials)


@shared_task
def handle_message(mid):
    message = Message.objects.get(id=mid)
    conversation = message.conversation
    text = message.text

    logging.info(f"Got message of \"{text}\" to process with dialogflow")

    session = session_client.session_path(settings.GOOGLE_PROJECT_ID,
                                          f"{conversation.platform}:{conversation.platform_id}:{conversation.noonce}")

    text_input = dialogflow.types.TextInput(text=text, language_code="en-GB")
    query_input = dialogflow.types.QueryInput(text=text_input)

    response = session_client.detect_intent(session=session, query_input=query_input)

    resp_message = Message(conversation=conversation, text=response.query_result.fulfillment_text,
    for context in response.query_result.output_contexts:
        context = context.name.split("/")[-1]
        if context == "human-needed":
            conversation.agent_responding = False
            conversation.save()
        if context == "close":
            conversation.noonce = secrets.token_urlsafe(10)
            conversation.save()
                           direction=Message.TO_CUSTOMER, message_id=response.response_id)
    resp_message.save()

    logging.info(f"Dialogflow gave response of \"{text}\"")

    operator_interface.tasks.process_message.delay(resp_message.id)
