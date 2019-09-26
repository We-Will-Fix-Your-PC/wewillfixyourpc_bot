import json
import logging
import os
import re
import urllib.parse
import uuid
from io import BytesIO

import google.auth.transport.requests
import google.oauth2.id_token
import requests
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

import keycloak_auth.clients
import operator_interface.consumers
import operator_interface.tasks
from operator_interface.models import Conversation, Message

logger = logging.getLogger(__name__)
emoji_pattern = \
    re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
               "\U00002702-\U000027B0\U000024C2-\U0001F251\U0001F900-\U0001F9FF]+", flags=re.UNICODE)


def process_inputs(inputs, conversation):
    outputs_l = []
    for i in inputs:
        if i.get("intent") == "actions.intent.MAIN":
            outputs_l.append(operator_interface.tasks.process_event.delay(conversation.id, "WELCOME"))
        elif i.get("intent") == "actions.intent.CANCEL":
            outputs_l.append(operator_interface.tasks.process_event.delay(conversation.id, "end"))
        elif i.get("intent") == "actions.intent.TEXT":
            arguments = i.get("arguments", {})
            text = next(a["textValue"] for a in arguments if a.get('name') == "text")
            message_m = Message(
                conversation=conversation, message_id=uuid.uuid4(), text=text, direction=Message.FROM_CUSTOMER)
            message_m.save()
            outputs_l.append(operator_interface.tasks.process_message.delay(message_m.id))
        elif i.get("intent") == "actions.intent.SIGN_IN":
            arguments = i.get("arguments", {})
            status = next(a["extension"] for a in arguments if a.get('name') == "SIGN_IN") \
                .get("status", "SIGN_IN_STATUS_UNSPECIFIED")
            if status in ["SIGN_IN_STATUS_UNSPECIFIED", "ERROR"]:
                outputs_l.append(operator_interface.tasks.process_event.delay(conversation.id, "sign_in_error"))
            elif status == "CANCELLED":
                outputs_l.append(operator_interface.tasks.process_event.delay(conversation.id, "sign_in_cancelled"))
            else:
                outputs_l.append(operator_interface.tasks.process_event.delay(conversation.id, "sign_in"))
        elif i.get("intent") == "actions.intent.NEW_SURFACE":
            arguments = i.get("arguments", {})
            status = next(a["extension"] for a in arguments if a.get('name') == "NEW_SURFACE") \
                .get("status", "NEW_SURFACE_STATUS_UNSPECIFIED")
            if status in ["NEW_SURFACE_STATUS_UNSPECIFIED", "CANCELLED"]:
                outputs_l.append(
                    operator_interface.tasks.process_event.delay(conversation.id, "move_to_new_device_refused"))
            else:
                outputs_l.append(operator_interface.tasks.process_event.delay(conversation.id, "moved_to_new_device"))

    return outputs_l


def process_outputs(outputs_l, is_guest_user, user_id_token, conversation):
    outputs_l = [o.get() for o in outputs_l]
    outputs = []
    for o in outputs_l:
        outputs.extend(o)
    outputs = [Message.objects.get(id=o) for o in outputs]
    messages = "\n\n".join(o.text for o in outputs if o.text.strip() != "")
    last_output = outputs[-1]

    possible_intents = []
    responses = []

    if last_output.request == "google_sign_in":
        if not is_guest_user:
            if not user_id_token:
                possible_intents.append({
                    "intent": "actions.intent.SIGN_IN",
                    "inputValueData": {
                        "@type": "type.googleapis.com/google.actions.v2.SignInValueSpec"
                    }
                })
                responses.append({
                    "simpleResponse": {
                        "textToSpeech": emoji_pattern.sub(r'', last_output.text),
                        "displayText": last_output.text,
                    }
                })
            else:
                return process_outputs([operator_interface.tasks.process_event.delay(conversation.id, "sign_in")],
                                       is_guest_user, user_id_token, conversation)
        else:
            possible_intents.append({
                "intent": "actions.intent.TEXT",
            })
            responses.append({
                "simpleResponse": {
                    "textToSpeech": "Sorry but you'll need a google account to proceed any further,"
                                    " what else can I help you with?",
                }
            })
    elif last_output.request == "google_move_web_browser":
        responses.append({
            "simpleResponse": {
                "textToSpeech": emoji_pattern.sub(r'', messages),
                "displayText": messages,
            }
        })
        possible_intents.append({
            "intent": "actions.intent.NEW_SURFACE",
            "inputValueData": {
                "@type": "type.googleapis.com/google.actions.v2.NewSurfaceValueSpec",
                "capabilities": [
                    "actions.capability.WEB_BROWSER"
                ],
                "context": emoji_pattern.sub(r'', messages),
                "notificationTitle": "Continue with We Will Fix Your PC here!"
            }
        })
    else:
        possible_intents.append({
            "intent": "actions.intent.TEXT",
        })
        responses.append({
            "simpleResponse": {
                "textToSpeech": emoji_pattern.sub(r'', messages),
                "displayText": messages,
            }
        })

        if last_output.card:
            card = json.loads(last_output.card)
            basic_card = {}

            if card.get("text"):
                basic_card["formattedText"] = card["text"]
            if card.get("title"):
                basic_card["title"] = card["title"]
            if card.get("button"):
                basic_card["buttons"] = [{
                    "title": card["button"].get("title"),
                    "openUrlAction": {
                        "url": card["button"].get("link")
                    }
                }]

            responses.append({
                "basicCard": basic_card
            })

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
        google.oauth2.id_token.verify_token(token, google_request, settings.GOOGLE_PROJECT_ID)
    except ValueError:
        return HttpResponseForbidden()

    logger.debug(f"Got event from actions on google webhook: {data}")

    user = data.get("user", {})
    inputs = data.get("inputs", [])
    is_guest_user = user.get("userVerificationStatus", "GUEST") != "VERIFIED"
    conversation_id = data.get("conversation", {}).get("conversationId", "")

    if not is_guest_user:
        user_id = user.get("userStorage", str(uuid.uuid4()))
    else:
        user_id = None
    conversation: Conversation = Conversation.get_or_create_conversation(Conversation.GOOGLE_ACTIONS, conversation_id)

    additional_conversation_data = {
        "surfaceCapabilities": data.get("surface", {}).get("capabilities", []),
        "availableSurfaces": data.get("availableSurfaces", [])
    }
    conversation.additional_conversation_data = json.dumps(additional_conversation_data)

    conversation.save()

    user_id_token = user.get("idToken")
    if user_id_token:
        try:
            user_id_token = \
                google.oauth2.id_token.verify_token(user_id_token, google_request)
        except ValueError:
            return HttpResponseForbidden()

        admin_client = keycloak_auth.clients.get_keycloak_admin_client()

        if not conversation.conversation_user_id:
            users = list(map(lambda u: admin_client.users.by_id(u.get("id")).get(), admin_client.users.all()))
            cont = True
            for user in users:
                google_identity = next(
                    filter(lambda i: i.get("identityProvider") == "google", user.get("federatedIdentities", [])),
                    None
                )
                if google_identity:
                    if user_id_token.get("sub") == google_identity.get("userId"):
                        conversation.conversation_user_id = user.get("id")
                        cont = False
                        break

            if not cont:
                for user in users:
                    if user.get("email") == user_id_token.get("email"):
                        conversation.customer_user_id = user.get("id")
                        user_o = admin_client.users.by_id(user.get("id"))
                        federated_identities = user.get("federatedIdentities")
                        federated_identities.append({
                            "identityProvider": "google",
                            "userId": user_id_token.get("sub"),
                            "userName": user_id_token.get("email")
                        })
                        user_o.update(federated_identities=federated_identities)
                        break

        if conversation.conversation_user_id:
            user = admin_client.users.by_id(conversation.conversation_user_id)
            user_data = user.get()
            attributes = user_data.get("attributes", {})
            federated_identities = user_data.get("federatedIdentities")

            google_identity = next(
                filter(
                    lambda i:
                    i.get("identityProvider") == "google" and
                    i.get("userId") == user_id_token.get("sub"),
                    user_data.get("federatedIdentities", [])
                ),
                None
            )
            if not google_identity:
                federated_identities.push({
                    "identityProvider": "google",
                    "userId": user_id_token.get("sub"),
                    "userName": user_id_token.get("email")
                })

            new_first_name = user_id_token.get("given_name")
            new_last_name = user_id_token.get("family_name")
            new_email = user_id_token.get("email")
            first_name = user_data.get("firstName")
            last_name = user_data.get("lastName")
            email = user_data.get("email")
            email_verified = user_data.get("emailVerified")

            if new_first_name and not first_name:
                first_name = new_first_name
            if new_last_name and not last_name:
                last_name = new_last_name
            if new_email and not email:
                email = new_email
                email_verified = True
            user.update(
                first_name=first_name,
                last_name=last_name,
                email=email,
                email_verified=email_verified,
                attributes=attributes,
                federated_identities=federated_identities
            )

        profile_pic = user_id_token.get("picture")
        if profile_pic:
            r = requests.get(profile_pic)
            if r.status_code == 200:
                file_name = os.path.basename(urllib.parse.urlparse(profile_pic).path)
                conversation.conversation_pic = \
                    InMemoryUploadedFile(file=BytesIO(r.content), size=len(r.content), charset=r.encoding,
                                         content_type=r.headers.get('content-type'), field_name=file_name,
                                         name=file_name)
        conversation.save()

    possible_intents, responses, last_output = \
        process_outputs(process_inputs(inputs, conversation), is_guest_user, user_id_token, conversation)

    response = {
        "items": responses,
        "suggestions": [{
            "title": s.suggested_response
        } for s in last_output.messagesuggestion_set.all()]
    }

    out_data = {
        "isInSandbox": data.get("isInSandbox", True),
    }
    if not last_output.end:
        out_data["expectUserResponse"] = True
        out_data["expectedInputs"] = [{
            "inputPrompt": {
                "richInitialPrompt": response,
            },
            "possibleIntents": possible_intents
        }]
    else:
        out_data["expectUserResponse"] = False
        out_data["finalResponse"] = {
            "richResponse": response
        }

    print(out_data)
    if not is_guest_user:
        out_data["userStorage"] = user_id
    return HttpResponse(json.dumps(out_data), content_type="application/json")
