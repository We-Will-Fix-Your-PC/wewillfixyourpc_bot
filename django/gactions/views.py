import json
import logging
import os
import re
import urllib.parse
import uuid
from io import BytesIO

import django_keycloak_auth.clients
import django_keycloak_auth.users
import google.auth.transport.requests
import google.oauth2.id_token
import jose.exceptions
import jwt
import requests
from django.utils import timezone
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

import operator_interface.consumers
import operator_interface.tasks
from operator_interface.models import Conversation, Message

logger = logging.getLogger(__name__)
emoji_pattern = re.compile(
    "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0\U000024C2-\U0001F251\U0001F900-\U0001F9FF]+",
    flags=re.UNICODE,
)


def process_inputs(inputs, conversation):
    outputs_l = []
    for i in inputs:
        intent = i.get("intent")
        if intent == "actions.intent.MAIN":
            outputs_l.append(
                operator_interface.tasks.process_event.delay(conversation.id, "WELCOME")
            )
        elif intent == "actions.intent.CANCEL":
            outputs_l.append(
                operator_interface.tasks.process_event.delay(conversation.id, "end")
            )
        elif intent == "actions.intent.OPTION":
            arguments = i.get("arguments", {})
            option = next(
                a["textValue"] for a in arguments if a.get("name") == "OPTION"
            )
            if option.startswith("SELECTION_NUM_"):
                num = option[len("SELECTION_NUM_"):]
                outputs_l.append(
                    operator_interface.tasks.process_event.delay(
                        conversation.id, f'resolve_entity{{"number": "{num}"}}'
                    )
                )
        elif intent == "actions.intent.CONFIRMATION":
            arguments = i.get("arguments", {})
            option = next(
                a["boolValue"] for a in arguments if a.get("name") == "CONFIRMATION"
            )
            outputs_l.append(
                operator_interface.tasks.process_event.delay(
                    conversation.id, 'affirm' if option else 'deny'
                )
            )
        elif intent == "actions.intent.DATETIME":
            arguments = i.get("arguments", {})
            option = next(
                a["datetimeValue"] for a in arguments if a.get("name") == "DATETIME"
            )
            time = timezone.datetime(
                year=option["date"]["year"], month=option["date"]["month"], day=option["date"]["day"],
                hour=option["time"]["hours"], minute=option["time"].get("minutes", 0), second=0
            )
            message_m = Message(
                conversation=conversation,
                message_id=uuid.uuid4(),
                text=time.strftime("%c"),
                direction=Message.FROM_CUSTOMER,
            )
            message_m.save()
            outputs_l.append(
                operator_interface.tasks.process_message.delay(message_m.id)
            )
        elif intent == "actions.intent.TEXT":
            arguments = i.get("arguments", {})
            text = next(a["textValue"] for a in arguments if a.get("name") == "text")
            message_m = Message(
                conversation=conversation,
                message_id=uuid.uuid4(),
                text=text,
                direction=Message.FROM_CUSTOMER,
            )
            message_m.save()
            outputs_l.append(
                operator_interface.tasks.process_message.delay(message_m.id)
            )
        elif intent == "actions.intent.SIGN_IN":
            arguments = i.get("arguments", {})
            status = next(
                a["extension"] for a in arguments if a.get("name") == "SIGN_IN"
            ).get("status", "SIGN_IN_STATUS_UNSPECIFIED")
            if status in ["SIGN_IN_STATUS_UNSPECIFIED", "ERROR"]:
                outputs_l.append(
                    operator_interface.tasks.process_event.delay(
                        conversation.id, "sign_in_error"
                    )
                )
            elif status == "CANCELLED":
                outputs_l.append(
                    operator_interface.tasks.process_event.delay(
                        conversation.id, "sign_in_cancelled"
                    )
                )
            else:
                outputs_l.append(
                    operator_interface.tasks.process_event.delay(
                        conversation.id, "sign_in"
                    )
                )
        elif intent == "actions.intent.NEW_SURFACE":
            arguments = i.get("arguments", {})
            status = next(
                a["extension"] for a in arguments if a.get("name") == "NEW_SURFACE"
            ).get("status", "NEW_SURFACE_STATUS_UNSPECIFIED")
            if status in ["NEW_SURFACE_STATUS_UNSPECIFIED", "CANCELLED"]:
                outputs_l.append(
                    operator_interface.tasks.process_event.delay(
                        conversation.id, "move_to_new_device_refused"
                    )
                )
            else:
                outputs_l.append(
                    operator_interface.tasks.process_event.delay(
                        conversation.id, "moved_to_new_device"
                    )
                )

    return outputs_l


def process_outputs(outputs_l, is_guest_user, conversation):
    outputs_l = [o.get() for o in outputs_l]
    outputs = []
    for o in outputs_l:
        outputs.extend(o)
    outputs = [Message.objects.get(id=o) for o in outputs]
    messages = "\n\n".join(o.text for o in outputs if o.text.strip() != "")
    last_output = outputs[-1]

    possible_intents = []
    responses = []

    if last_output.request == "sign_in":
        if not is_guest_user:
            if not conversation.conversation_user_id:
                possible_intents.append(
                    {
                        "intent": "actions.intent.SIGN_IN",
                        "inputValueData": {
                            "@type": "type.googleapis.com/google.actions.v2.SignInValueSpec"
                        },
                    }
                )
                responses.append(
                    {
                        "simpleResponse": {
                            "textToSpeech": emoji_pattern.sub(r"", last_output.text),
                            "displayText": last_output.text,
                        }
                    }
                )
            else:
                return process_outputs(
                    [
                        operator_interface.tasks.process_event.delay(
                            conversation.id, "sign_in"
                        )
                    ],
                    is_guest_user,
                    conversation,
                )
        else:
            operator_interface.tasks.process_event.delay(
                conversation.id, "sign_in_cancelled"
            )
            possible_intents.append({"intent": "actions.intent.TEXT"})
            responses.append(
                {
                    "simpleResponse": {
                        "textToSpeech": "Sorry but you'll need a google account to proceed any further,"
                        " what else can I help you with?"
                    }
                }
            )
    elif last_output.request == "google_move_web_browser":
        responses.append(
            {
                "simpleResponse": {
                    "textToSpeech": emoji_pattern.sub(r"", messages),
                    "displayText": messages,
                }
            }
        )
        possible_intents.append(
            {
                "intent": "actions.intent.NEW_SURFACE",
                "inputValueData": {
                    "@type": "type.googleapis.com/google.actions.v2.NewSurfaceValueSpec",
                    "capabilities": ["actions.capability.WEB_BROWSER"],
                    "context": emoji_pattern.sub(r"", messages),
                    "notificationTitle": "Continue with We Will Fix Your PC here!",
                },
            }
        )
    elif last_output.request == "confirmation":
        responses.append(
            {
                "simpleResponse": {
                    "textToSpeech": emoji_pattern.sub(r"", messages),
                    "displayText": messages,
                }
            }
        )
        possible_intents.append(
            {
                "intent": "actions.intent.CONFIRMATION",
                "inputValueData": {
                    "@type": "type.googleapis.com/google.actions.v2.ConfirmationValueSpec",
                    "dialogSpec": {
                        "requestConfirmationText": messages
                    },
                },
            }
        )
    elif last_output.request == "time":
        responses.append(
            {
                "simpleResponse": {
                    "textToSpeech": emoji_pattern.sub(r"", messages),
                    "displayText": messages,
                }
            }
        )
        possible_intents.append({
            "intent": "actions.intent.DATETIME",
            "inputValueData": {
                "@type": "type.googleapis.com/google.actions.v2.DateTimeValueSpec",
                "dialogSpec": {
                    "requestDatetimeText": "When would best for you?",
                    "requestDateText": "What day was that?",
                    "requestTimeText": "What time works for you?"
                }
            }
        }
        )
    elif last_output.selection:
        selection = json.loads(last_output.selection)
        responses.append(
            {
                "simpleResponse": {
                    "textToSpeech": emoji_pattern.sub(r"", messages),
                    "displayText": messages,
                }
            }
        )
        possible_intents.append(
            {
                "intent": "actions.intent.OPTION",
                "inputValueData": {
                    "@type": "type.googleapis.com/google.actions.v2.OptionValueSpec",
                    "listSelect": {
                        "title": selection.get("title"),
                        "items": [
                            {
                                "optionInfo": {
                                    "key": f"SELECTION_NUM_{i + 1}",
                                    "synonyms": [],
                                },
                                "title": item.get("title"),
                            }
                            for i, item in enumerate(selection.get("items", []))
                        ],
                    },
                },
            }
        )
    else:
        possible_intents.append({"intent": "actions.intent.TEXT"})

        messages = []
        i = 0
        cur_msg = outputs[i]
        while not cur_msg.card:
            messages.append(cur_msg)
            i += 1
            if i < len(outputs):
                cur_msg = outputs[i]
            else:
                break

        msg = "\n\n".join(o.text for o in messages if o.text.strip() != "")
        if msg.strip() != "":
            responses.append(
                {
                    "simpleResponse": {
                        "textToSpeech": emoji_pattern.sub(r"", msg),
                        "displayText": msg,
                    }
                }
            )

        if cur_msg.card:
            card = json.loads(cur_msg.card)
            basic_card = {}

            if card.get("text"):
                basic_card["formattedText"] = card["text"]
            if card.get("title"):
                basic_card["title"] = card["title"]
            if card.get("button"):
                basic_card["buttons"] = [
                    {
                        "title": card["button"].get("title"),
                        "openUrlAction": {"url": card["button"].get("link")},
                    }
                ]

            responses.append({"basicCard": basic_card})

        if i < len(outputs):
            msg = "\n\n".join(o.text for o in outputs[i:] if o.text.strip() != "")
            if msg.strip() != "":
                responses.append(
                    {
                        "simpleResponse": {
                            "textToSpeech": emoji_pattern.sub(r"", msg),
                            "displayText": msg,
                        }
                    }
                )

    return possible_intents, responses, last_output


@csrf_exempt
def webhook(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    google_request = google.auth.transport.requests.Request()
    token = request.META.get("HTTP_AUTHORIZATION")
    try:
        google.oauth2.id_token.verify_token(
            token, google_request, settings.GOOGLE_PROJECT_ID
        )
    except ValueError:
        return HttpResponseForbidden()

    logger.debug(f"Got event from actions on google webhook: {data}")

    user = data.get("user", {})
    inputs = data.get("inputs", [])
    is_guest_user = user.get("userVerificationStatus", "GUEST") != "VERIFIED"
    conversation_id = data.get("conversation", {}).get("conversationId", "")

    user_id = user.get("userStorage", None) if not is_guest_user else None
    conversation: Conversation = Conversation.get_or_create_conversation(
        Conversation.GOOGLE_ACTIONS, conversation_id
    )

    additional_conversation_data = {
        "surfaceCapabilities": data.get("surface", {}).get("capabilities", []),
        "availableSurfaces": data.get("availableSurfaces", []),
    }
    conversation.additional_conversation_data = json.dumps(additional_conversation_data)

    conversation.save()

    user_id_token = user.get("idToken")
    user_access_token = user.get("accessToken")

    if user_id:
        conversation.conversation_user_id = user_id
        conversation.save()

    if user_access_token:
        oidc_client = django_keycloak_auth.clients.get_openid_connect_client()

        certs = oidc_client.certs().get("keys", [])
        header = jwt.get_unverified_header(user_access_token)
        cert = next(filter(lambda c: c.get("kid") == header.get("kid"), certs), None)

        if cert is None:
            return HttpResponseForbidden()

        try:
            user_token = oidc_client.decode_token(user_access_token, cert)
        except jose.exceptions.JWTError:
            return HttpResponseForbidden()

        conversation.conversation_user_id = user_token.get("sub")
        conversation.save()

    if user_id_token:
        try:
            user_id_token = google.oauth2.id_token.verify_token(
                user_id_token, google_request
            )
        except ValueError:
            return HttpResponseForbidden()

        profile_pic = user_id_token.get("picture")

        if not conversation.conversation_user_id:
            user = django_keycloak_auth.users.get_or_create_user(
                federated_provider="google",
                federated_user_id=user_id_token.get("sub"),
                federated_user_name=user_id_token.get("email"),
                email=user_id_token.get("email"),
                first_name=user_id_token.get("given_name"),
                last_name=user_id_token.get("family_name"),
                required_actions=["UPDATE_PROFILE"],
                profile_picture=profile_pic,
            )
            if user:
                django_keycloak_auth.users.user_required_actions(
                    user.get("id"), ["UPDATE_PROFILE"]
                )
                django_keycloak_auth.users.link_roles_to_user(
                    user.get("id"), ["customer"]
                )
                conversation.conversation_user_id = user.get("id")
                conversation.save()

        if conversation.conversation_user_id:
            django_keycloak_auth.users.link_federated_identity_if_not_exists(
                conversation.conversation_user_id,
                federated_provider="google",
                federated_user_id=user_id_token.get("sub"),
                federated_user_name=user_id_token.get("email"),
            )

            django_keycloak_auth.users.update_user(
                conversation.conversation_user_id,
                first_name=user_id_token.get("given_name"),
                last_name=user_id_token.get("family_name"),
                email=user_id_token.get("email"),
                email_verified=user_id_token.get("email_verified", True),
                profile_picture=profile_pic,
            )

        if profile_pic:
            r = requests.get(profile_pic)
            if r.status_code == 200:
                file_name = os.path.basename(urllib.parse.urlparse(profile_pic).path)
                conversation.conversation_pic = InMemoryUploadedFile(
                    file=BytesIO(r.content),
                    size=len(r.content),
                    charset=r.encoding,
                    content_type=r.headers.get("content-type"),
                    field_name=file_name,
                    name=file_name,
                )
        conversation.save()

    possible_intents, responses, last_output = process_outputs(
        process_inputs(inputs, conversation), is_guest_user, conversation
    )

    response = {
        "items": responses,
        "suggestions": [
            {"title": s.suggested_response}
            for s in last_output.messagesuggestion_set.all()
        ],
    }

    out_data = {"isInSandbox": data.get("isInSandbox", True)}
    if not last_output.end:
        out_data["expectUserResponse"] = True
        out_data["expectedInputs"] = [
            {
                "inputPrompt": {"richInitialPrompt": response},
                "possibleIntents": possible_intents,
            }
        ]
    else:
        out_data["expectUserResponse"] = False
        out_data["finalResponse"] = {"richResponse": response}

    print(out_data)
    if not is_guest_user:
        out_data["userStorage"] = conversation.conversation_user_id
    return HttpResponse(json.dumps(out_data), content_type="application/json")
