from django.conf import settings
from celery import shared_task
import operator_interface.tasks
import logging
import requests
import json
import logging
import uuid
import operator_interface.tasks
from operator_interface.models import Message, MessageSuggestion, Conversation, PaymentMessage

logger = logging.getLogger(__name__)


@shared_task
def handle_message(mid):
    message = Message.objects.get(id=mid)
    conversation = message.conversation
    text = message.text

    if text:
        logging.info(f"Got message of \"{text}\" to process with rasa")

        handle_text(conversation, text)


@shared_task
def handle_event(cid, event):
    conversation = Conversation.objects.get(id=cid)

    logging.info(f"Got event of \"{event}\" to process with rasa")

    if event == "WELCOME":
        handle_text(conversation, "/greet")
    else:
        handle_text(conversation, f"/{event}")


def handle_text(conversation, text):
    operator_interface.tasks.process_typing.delay(conversation.id)

    r = requests.post(f"{settings.RASA_HTTP_URL}/webhooks/rest/webhook?stream=true", json={
        "sender": f"{conversation.platform}:{conversation.platform_id}",
        "message": text
    }, stream=True)
    r.raise_for_status()

    items = r.iter_lines(None, True)
    for item in items:
        if item:
            try:
                data = json.loads(item)
            except json.JSONDecodeError:
                continue

            logger.debug(f"Got messages from rasa callback: {data}")

            if not data.get("recipient_id"):
                continue

            platform, platform_id = data["recipient_id"].split(":")
            conversation = Conversation.objects.get(platform=platform, platform_id=platform_id)
            message = Message(conversation=conversation, direction=Message.TO_CUSTOMER, message_id=uuid.uuid4())

            if data.get("text"):
                message.text = data["text"]
            elif data.get("image"):
                message.image = data["image"]
            elif data.get("custom"):
                custom = data["custom"]
                if not custom.get("type"):
                    continue
                event_type = custom["type"]

                if event_type == "payment":
                    payment_id = custom.get("payment_id")

                    message.text = "To complete payment follow this link 💸"
                    message.save()
                    payment_message = PaymentMessage(message=message, payment_id=payment_id)
                    payment_message.save()
                elif event_type == "request_human":
                    conversation.agent_responding = False
                    conversation.save()

                    operator_interface.tasks.send_message_notifications.delay({
                        "type": "alert",
                        "name": conversation.customer_name,
                        "text": "Human needed!"
                    })
                    continue
                else:
                    continue
            else:
                continue
            message.save()

            if data.get("buttons"):
                for button in data["buttons"]:
                    suggestion = MessageSuggestion(message=message, suggested_response=button["payload"])
                    suggestion.save()

            operator_interface.tasks.process_message(message.id)
