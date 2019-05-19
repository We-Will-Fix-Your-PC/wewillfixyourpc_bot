import dialogflow_v2 as dialogflow
from google.oauth2 import service_account
from django.conf import settings
from operator_interface.models import Message
from celery import shared_task
import operator_interface.tasks

credentials = service_account.Credentials.from_service_account_file(settings.GOOGLE_CREDENTIALS_FILE)
session_client = dialogflow.SessionsClient(credentials=credentials)


@shared_task
def handle_message(mid):
    message = Message.objects.get(id=mid)
    conversation = message.conversation
    text = message.text
    session = session_client.session_path(settings.GOOGLE_PROJECT_ID,
                                          f"{conversation.platform}:{conversation.platform_id}")

    text_input = dialogflow.types.TextInput(text=text, language_code="en-GB")
    query_input = dialogflow.types.QueryInput(text=text_input)

    response = session_client.detect_intent(session=session, query_input=query_input)

    resp_message = Message(conversation=conversation, text=response.query_result.fulfillment_text,
                           direction=Message.TO_CUSTOMER, message_id=response.response_id)
    resp_message.save()

    operator_interface.tasks.process_message.delay(resp_message.id)
