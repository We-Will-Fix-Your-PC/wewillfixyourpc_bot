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
from django.utils import html
from django.template.loader import render_to_string
from django.template.defaultfilters import linebreaksbr
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Header
import html2text


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
    if platform:
        user_id = attempt_get_user_id(msg_from)
        if user_id and str(platform.conversation.conversation_user_id) != user_id:
            platform.conversation.update_user_id(user_id)
    return platform


@shared_task
def handle_email(
    msg_headers: str,
    msg_text: str,
    msg_html: str,
    attachments_img: [str],
    attachments_other: [(str, str)],
):
    p = email.parser.Parser(policy=email.policy.default)
    try:
        msg_headers = p.parsestr(msg_headers, headersonly=True)
    except email.errors.HeaderParseError:
        return

    msg_to = msg_headers["to"]

    if msg_to.addresses[0].addr_spec != "hello@wewillfixyourpc.co.uk":
        return

    msg_from = msg_headers["from"]
    msg_id = msg_headers["message-id"]
    platform = get_platform(msg_from)

    if not msg_text:
        h = html2text.HTML2Text()
        h.ignore_emphasis = True
        msg_text = h.handle(msg_html)

    msg_lines = msg_text.split("\n")
    new_msg_lines = []
    for line in msg_lines:
        line = line.strip()
        if line == "--":
            break
        elif line.startswith("-----Original Message-----"):
            break
        elif line.startswith("________________________________"):
            break
        elif line.startswith("On ") and line.endswith(" wrote:"):
            break
        elif line.startswith("From: "):
            break
        elif line.startswith("Sent from my iPhone"):
            break
        else:
            new_msg_lines.append(line)
    msg_text = "\n".join(new_msg_lines)

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
            text=html.conditional_escape(msg_text),
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
    msg_attachments = []

    msg_id = f"<{message.message_id}@bot.cardifftec.uk>"
    previous_messages = message.platform.messages.order_by('-timestamp').all()
    last_message = previous_messages.filter(direction=Message.FROM_CUSTOMER).first()

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
        msg_attachments.append(message.image)

    message_content = render_to_string("emails/message.html", {
        "content": linebreaksbr(msg_content),
        "sender_name": message.user.first_name if message.user else None,
        "sender_pic": settings.EXTERNAL_URL_BASE + reverse("operator:profile_pic", args=[
            message.user.id
        ]) if message.user else None,
        "attachments": msg_attachments
    })

    email_msg = Mail(
        from_email='We Will Fix Your PC <hello@wewillfixyourpc.co.uk>',
        to_emails=message.platform.platform_id,
        subject=msg_subject,
        html_content=message_content
    )
    references = " ".join(map(
        lambda m: m.platform_message_id,
        filter(lambda m: m.platform_message_id is not None, previous_messages)
    ))
    email_msg.add_header(Header("References", references))
    email_msg.add_header(Header("In-Reply-To", last_message.platform_message_id))
    email_msg.add_header(Header("Message-Id", msg_id))
    try:
        sg.send(email_msg)
        message.state = Message.DELIVERED
        message.platform_message_id = msg_id
        message.save()
    except Exception:
        message.state = Message.FAILED
        message.save()
