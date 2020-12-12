import logging
import requests
from celery import shared_task
from django.conf import settings
import mimetypes
import django_keycloak_auth.clients
import operator_interface.models
import operator_interface.consumers
import operator_interface.tasks
from operator_interface.models import ConversationPlatform, Message
from django.contrib.auth.models import User
from django.utils import html

oauth_client = django_keycloak_auth.clients.get_keycloak_client().open_id_connect(
    settings.AS207960_OIDC_CLIENT_ID, settings.AS207960_OIDC_CLIENT_SECRET
)


def send_as207960_request(mid, to: str, media_type: str, contents, representative=None):
    platform, conv_id = to.split(";", 1)
    data = {
        "platform": platform,
        "platform_conversation_id": conv_id,
        "client_message_id": None,
        "media_type": media_type,
        "content": contents,
        "representative": representative
    }
    if mid:
        data["client_message_id"] = str(mid)
    return requests.post(
        f"https://messaging.as207960.net/api/brands/{settings.AS207960_BRAND_ID}/messages/",
        headers={"Authorization": f"X-AS207960-PAT {settings.AS207960_KEY}"},
        json=data,
    )


def get_message_persona(user=None):
    persona_id = None
    if user is not None:
        try:
            if user.userprofile.as207960_persona_id is None:
                profile = user.userprofile  # type: operator_interface.models.UserProfile
                persona_r = requests.post(
                    f"https://messaging.as207960.net/api/brands/{settings.AS207960_BRAND_ID}/representatives/",
                    headers={
                        "Authorization": f"X-AS207960-PAT {settings.AS207960_KEY}",
                        "Accept": "application/json"
                    },
                    data={
                        "name": user.first_name,
                        "is_bot": False,
                    },
                    files={
                        "avatar": open(profile.picture.path, "rb")
                    } if profile.picture else {}
                )
                if persona_r.status_code == 201:
                    persona_json = persona_r.json()
                    user.userprofile.as207960_persona_id = persona_json["id"]
                    user.userprofile.save()
                    persona_id = persona_json["id"]
            else:
                persona_id = user.userprofile.as207960_persona_id
        except User.userprofile.RelatedObjectDoesNotExist:
            pass

    return persona_id


def get_platform(platform, conv_id, metadata):
    msg_from = f"{platform};{conv_id}"
    platform: ConversationPlatform = ConversationPlatform.exists(
        ConversationPlatform.AS207960, msg_from
    )
    if not platform:
        platform = ConversationPlatform.create(
            ConversationPlatform.AS207960, msg_from, customer_user_id=None
        )

    if not platform.conversation.conversation_name:
        platform.conversation.conversation_name = metadata.get("user_name")
        platform.conversation.save()

    return platform


@shared_task
def handle_as207960_text(msg_id, msg_platform, msg_conv_id, metadata, content):
    platform = get_platform(msg_platform, msg_conv_id, metadata)
    platform.is_typing = False
    platform.save()
    if not Message.message_exits(platform, msg_id):
        if content:
            message_m: Message = Message(
                platform=platform,
                platform_message_id=msg_id,
                text=html.conditional_escape(content),
                direction=Message.FROM_CUSTOMER,
                state=Message.DELIVERED,
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)


@shared_task
def handle_as207960_file(msg_id, msg_platform, msg_conv_id, metadata, content):
    platform = get_platform(msg_platform, msg_conv_id, metadata)
    platform.is_typing = False
    platform.save()
    if not Message.message_exits(platform, msg_id):
        if content.get("media_type", "").startswith("image/"):
            message_m: Message = Message(
                platform=platform,
                platform_message_id=msg_id,
                image=content.get("url"),
                direction=Message.FROM_CUSTOMER,
                state=Message.DELIVERED,
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)
        else:
            message_m: Message = Message(
                platform=platform,
                platform_message_id=msg_id,
                text=content.get("url"),
                direction=Message.FROM_CUSTOMER,
                state=Message.DELIVERED,
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)


@shared_task
def handle_as207960_chatstate(msg_id, msg_platform, msg_conv_id, metadata, content):
    platform = get_platform(msg_platform, msg_conv_id, metadata)
    platform.is_typing = False
    platform.save()
    state = content.get("state")
    if state == "composing":
        platform.is_typing = True
        platform.save()
    elif state == "paused":
        platform.is_typing = False
        platform.save()
    elif state == "request_live_agent":
        platform.is_typing = False
        platform.save()
        m = Message(
            platform=platform,
            platform_message_id=msg_id,
            request_live_agent=True,
            direction=Message.FROM_CUSTOMER,
            state=Message.DELIVERED
        )
        m.save()
        operator_interface.tasks.send_message_to_interface.delay(m.id)


@shared_task
def handle_as207960_oauth_code(msg_id, msg_platform, msg_conv_id, metadata, content):
    platform = get_platform(msg_platform, msg_conv_id, metadata)
    token_response = oauth_client.authorization_code(
        code=content, redirect_uri="https://messaging.as207960.net/brand_oauth/redirect/"
    )
    token_data = oauth_client.decode_token(
        token_response["id_token"],
        key=oauth_client.certs()["keys"][0],
        algorithms=oauth_client.well_known["id_token_signing_alg_values_supported"],
        issuer=oauth_client.well_known["issuer"],
        access_token=token_response["access_token"],
    )
    platform.conversation.update_user_id(token_data["sub"])
    message = Message(
        platform=platform,
        text="Login complete, thanks!",
        direction=Message.TO_CUSTOMER,
    )
    message.save()
    operator_interface.tasks.process_message.delay(message.id)


@shared_task
def handle_as207960_typing_on(pid: int):
    platform = ConversationPlatform.objects.get(id=pid)
    persona_id = get_message_persona(platform.conversation.current_agent)
    r = send_as207960_request(None, platform.platform_id, "chat_state", {
        "state": "composing"
    }, representative=persona_id)
    if r.status_code != 201:
        logging.error(f"Error sending AS207960 typing on: {r.status_code} {r.text}")


@shared_task
def handle_as207960_typing_off(pid: int):
    platform = ConversationPlatform.objects.get(id=pid)
    persona_id = get_message_persona(platform.conversation.current_agent)
    r = send_as207960_request(None, platform.platform_id, "chat_state", {
        "state": "paused"
    }, representative=persona_id)
    if r.status_code != 201:
        logging.error(f"Error sending AS207960 typing on: {r.status_code} {r.text}")


@shared_task
def send_message(mid: int):
    message = Message.objects.get(id=mid)
    persona_id = get_message_persona(message.user)
    messages = []

    if message.request == "sign_in":
        messages.append((message.message_id, "select", {
            "content": message.text,
            "media_type": "text",
            "options": [{
                "content": None,
                "media_type": "login"
            }]
        }))
    elif message.image:
        messages.append((message.message_id, "file", {
            "uri": message.image,
            "media_type": mimetypes.guess_type(message.image)
        }))
    elif message.text:
        messages.append((message.message_id, "text", message.text))
    else:
        return

    for msg_data in messages:
        r = send_as207960_request(
            msg_data[0], message.platform.platform_id, msg_data[1], msg_data[2],
            representative=persona_id
        )
        if r.status_code != 201:
            logging.error(f"Error sending AS207960 message: {r.status_code} {r.text}")
            message.state = Message.FAILED
            message.save()
        else:
            message.state = Message.DELIVERED
            message.save()
