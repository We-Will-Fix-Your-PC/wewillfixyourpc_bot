from django.conf import settings
from celery import shared_task
from operator_interface.models import ConversationPlatform, Message
import email.headerregistry
import typing
import email.parser
import email.policy
import django_keycloak_auth.users
import operator_interface.tasks
from . import models
from django.shortcuts import reverse
from django.template.loader import render_to_string
from django.template.defaultfilters import linebreaksbr
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


sg = SendGridAPIClient(settings.SENDGRID_KEY)


def attempt_get_user_id(
    msg_from: email.headerregistry.UniqueAddressHeader,
) -> typing.Optional[str]:
    def match_user(u):
        usr_email = u.user.get("email", "")
        for address in msg_from.addresses:
            if address.addr_spec == usr_email:
                return True

        return False

    user = next(filter(match_user, django_keycloak_auth.users.get_users()), None)
    return user.user.get("id") if user else None


def get_platform(msg_from: email.headerregistry.UniqueAddressHeader):
    platform: ConversationPlatform = ConversationPlatform.exists(
        ConversationPlatform.EMAIL, msg_from.addresses[0].addr_spec
    )
    if not platform:
        user_id = attempt_get_user_id(msg_from)
        platform = ConversationPlatform.create(
            ConversationPlatform.EMAIL,
            msg_from.addresses[0].addr_spec,
            customer_user_id=user_id,
        )
        platform.conversation.conversation_name = msg_from.addresses[0].display_name
        platform.conversation.save()
    return platform


@shared_task
def handle_email(
    msg_headers: str,
    msg_text: str,
    attachments_img: [str],
    attachments_other: [(str, str)],
):
    p = email.parser.Parser(policy=email.policy.default)
    try:
        msg_headers = p.parsestr(msg_headers, headersonly=True)
    except email.errors.HeaderParseError:
        return

    msg_from = msg_headers["from"]
    msg_id = msg_headers["message-id"]
    platform = get_platform(msg_from)

    if not platform.additional_platform_data:
        platform.additional_platform_data = str(msg_headers["subject"])
        platform.save()

    customer_name = msg_from.addresses[0].display_name.split(" ")

    if not platform.conversation.conversation_user_id:
        kc_user = django_keycloak_auth.users.get_or_create_user(
            email=msg_from.addresses[0].addr_spec,
            email_verifed=True,
            last_name=customer_name[-1],
            first_name=" ".join(customer_name[:-1]),
            required_actions=["UPDATE_PASSWORD", "UPDATE_PROFILE"],
        )
        if kc_user:
            django_keycloak_auth.users.link_roles_to_user(
                kc_user.get("id"), ["customer"]
            )
            platform.conversation.update_user_id(kc_user.get("id"))

    if platform.conversation.conversation_user_id:
        django_keycloak_auth.users.update_user(
            str(platform.conversation.conversation_user_id),
            last_name=customer_name[-1],
            first_name=" ".join(customer_name[:-1]),
            email_verified=True,
            email=msg_from.addresses[0].addr_spec,
        )

    if not Message.message_exits(platform, str(msg_id)):
        message_m: Message = Message(
            platform=platform,
            platform_message_id=str(msg_id),
            text=msg_text,
            direction=Message.FROM_CUSTOMER,
        )
        message_m.save()
        operator_interface.tasks.process_message.delay(message_m.id)

        for img in attachments_img:
            message_m: Message = Message(
                platform=platform,
                platform_message_id=str(msg_id),
                image=img,
                direction=Message.FROM_CUSTOMER,
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)

        for link in attachments_other:
            message_m: Message = Message(
                platform=platform,
                platform_message_id=str(msg_id),
                text=f'<a href="{link[0]}" target="_blank">{link[1]}</a>',
                direction=Message.FROM_CUSTOMER,
            )
            message_m.save()
            operator_interface.tasks.process_message.delay(message_m.id)


@shared_task
def send_message(mid: int):
    message = Message.objects.get(id=mid)

    msg_subject = f"Re: {message.platform.additional_platform_data}"
    msg_attachment = None

    if message.request == "sign_in":
        state = models.AccountLinkingState(conversation=message.platform)
        state.save()
        url = (
                settings.EXTERNAL_URL_BASE
                + reverse("sms:account_linking")
                + f"?state={state.id}"
        )
        msg_content = f'{message.text}\n\nSign in <a href="{url}">here</a>'
    elif message.text:
        msg_content = message.text
    else:
        return

    if message.image:
        msg_attachment = message.image

    message_content = render_to_string("emails/message.html", {
        "content": linebreaksbr(msg_content),
        "sender_name": message.user.first_name if message.user else None,
        "sender_id": message.user.id if message.user else None,
        "attachments": [msg_attachment]
    })

    email_msg = Mail(
        from_email='hello@wewillfixyourpc.co.uk',
        to_emails=message.platform.platform_id,
        subject=msg_subject,
        html_content=message_content
    )
    try:
        response = sg.send(email_msg)
        print(response.status_code)
        print(response.body)
        print(response.headers)
    except Exception:
        message.state = Message.FAILED
        message.save()
