from django.conf import settings
from celery import shared_task
import operator_interface.tasks
import requests
import json
import logging
import uuid
import operator_interface.tasks
from operator_interface.models import Message, MessageSuggestion, ConversationPlatform
import operator_interface.consumers

logger = logging.getLogger(__name__)


@shared_task
def handle_message(mid: int):
    message = Message.objects.get(id=mid)
    platform = message.platform
    text = message.text

    if text:
        logging.info(f'Got message of "{text}" to process with rasa')

        return handle_text(platform, text)


@shared_task
def handle_event(cid: int, event: str):
    platform = ConversationPlatform.objects.get(id=cid)

    logging.info(f'Got event of "{event}" to process with rasa')

    if event == "WELCOME":
        return handle_text(platform, "/greet")
    else:
        return handle_text(platform, f"/{event}")


def handle_text(platform: ConversationPlatform, text: str):
    operator_interface.tasks.process_typing_on.delay(platform.id)

    r = requests.post(
        f"{settings.RASA_HTTP_URL}/webhooks/rest/webhook?stream=true",
        json={"sender": f"CONV:{platform.id}", "message": text},
        stream=True,
    )
    r.raise_for_status()

    items = r.iter_lines(None, True)
    out_data = []
    for item in items:
        if item:
            try:
                data = json.loads(item)
            except json.JSONDecodeError:
                continue

            logger.debug(f"Got messages from rasa callback: {data}")

            if not data.get("recipient_id"):
                continue

            message = Message(
                platform=platform,
                direction=Message.TO_CUSTOMER,
                message_id=uuid.uuid4(),
            )

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
                    # TODO: Integrate with new system
                    # payment_id = custom.get("payment_id")
                    # payment_o = payment.models.Payment.objects.get(id=payment_id)

                    message.text = "To complete payment follow this link 💸"
                    # message.payment_request = payment_o
                    message.save()
                elif event_type == "request_human":
                    platform.conversation.agent_responding = False
                    platform.conversation.save()

                    operator_interface.tasks.send_message_notifications.delay(
                        {
                            "type": "alert",
                            "cid": platform.conversation.id,
                            "name": platform.conversation.conversation_name,
                            "text": "Human needed!",
                        }
                    )
                    continue
                elif event_type == "request":
                    message.text = custom.get("text", "")
                    message.request = custom.get("request")
                elif event_type == "card":
                    message.card = json.dumps(custom.get("card"))
                elif event_type == "selection":
                    message.selection = json.dumps(custom.get("selection"))
                elif event_type == "restart":
                    message.end = True
                else:
                    continue
            else:
                continue
            message.save()

            if data.get("buttons"):
                for button in data["buttons"]:
                    suggestion = MessageSuggestion(
                        message=message, suggested_response=button["payload"]
                    )
                    suggestion.save()

            out_data.append(operator_interface.tasks.process_message(message.id))

    return out_data
