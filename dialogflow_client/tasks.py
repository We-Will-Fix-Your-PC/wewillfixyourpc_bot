import dialogflow_v2 as dialogflow
from google.oauth2 import service_account
from django.conf import settings
from operator_interface.models import Message, MessageSuggestion, Conversation
from celery import shared_task
import operator_interface.tasks
import logging

credentials = service_account.Credentials.from_service_account_file(settings.GOOGLE_CREDENTIALS_FILE)
session_client = dialogflow.SessionsClient(credentials=credentials)


@shared_task
def handle_message(mid):
    message = Message.objects.get(id=mid)
    conversation = message.conversation
    text = message.text

    logging.info(f"Got message of \"{text}\" to process with dialogflow")

    text_input = dialogflow.types.TextInput(text=text, language_code="en-GB")
    query_input = dialogflow.types.QueryInput(text=text_input)

    handle_response(conversation, query_input)


@shared_task
def handle_event(cid, event):
    conversation = Conversation.objects.get(id=cid)

    logging.info(f"Got event of \"{event}\" to process with dialogflow")

    event_input = dialogflow.types.EventInput(name=event, language_code="en-GB")
    query_input = dialogflow.types.QueryInput(event=event_input)

    handle_response(conversation, query_input)


def handle_response(conversation, query_input):
    operator_interface.tasks.process_typing.delay(conversation.id)

    sentiment_analysis_request_config = \
        dialogflow.types.SentimentAnalysisRequestConfig(analyze_query_text_sentiment=True)
    query_parameters = \
        dialogflow.types.QueryParameters(sentiment_analysis_request_config=sentiment_analysis_request_config)

    session = session_client.session_path(settings.GOOGLE_PROJECT_ID,
                                          f"{conversation.platform}:{conversation.platform_id}:{conversation.noonce}")
    response = session_client.detect_intent(session=session, query_input=query_input, query_parameters=query_parameters)

    for context in response.query_result.output_contexts:
        context = context.name.split("/")[-1]
        if context == "human-needed":
            conversation.agent_responding = False
            conversation.save()
        if context == "close":
            conversation.reset()

    messages = response.query_result.fulfillment_messages
    text = list(filter(lambda m: m.WhichOneof("message") == "text", messages))
    text_platform = []
    if conversation.platform == Conversation.FACEBOOK:
        text_platform = \
            list(filter(lambda m: m.platform == dialogflow.types.intent_pb2.Intent.Message.FACEBOOK, text))
    if len(text_platform) > 0:
        text = text_platform[0].text.text[0]
    else:
        text = text[0].text.text[0]

    quick_replies = list(filter(lambda m: m.WhichOneof("message") == "quick_replies", messages))
    if conversation.platform == Conversation.FACEBOOK:
        quick_replies = \
            list(filter(lambda m: m.platform == dialogflow.types.intent_pb2.Intent.Message.FACEBOOK, quick_replies))

    resp_message = Message(conversation=conversation, text=text,
                           direction=Message.TO_CUSTOMER, message_id=response.response_id)
    resp_message.save()

    if conversation.platform == Conversation.FACEBOOK:
        if len(quick_replies) > 0:
            quick_replies = quick_replies[0].quick_replies.quick_replies
            for reply in quick_replies:
                suggestion = MessageSuggestion(message=resp_message, suggested_response=reply)
                suggestion.save()

    logging.info(f"Dialogflow gave response of \"{text}\"")

    operator_interface.tasks.process_message.delay(resp_message.id)
