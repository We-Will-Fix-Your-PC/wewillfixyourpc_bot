import json
import uuid

import django_keycloak_auth.clients
import django_keycloak_auth.users
import keycloak.exceptions
import phonenumbers
from django.conf import settings
from django.http import (
    HttpResponse,
    HttpResponseNotAllowed,
    HttpResponseBadRequest,
    Http404,
    HttpResponseForbidden,
)
from django.views.decorators.csrf import csrf_exempt

import operator_interface.tasks
from operator_interface.models import Message, Conversation, ConversationPlatform


@csrf_exempt
def send_message(request, customer_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(permitted_methods=["POST"])

    auth = request.META.get("HTTP_AUTHORIZATION")
    if not auth or not auth.startswith("Bearer "):
        return HttpResponseForbidden()

    try:
        claims = django_keycloak_auth.clients.verify_token(
            auth[len("Bearer "):].strip()
        )
    except keycloak.exceptions.KeycloakClientError:
        return HttpResponseForbidden()

    if "send-messages" not in claims.get("resource_access", {}).get(
            "bot-server", {}
    ).get("roles", []):
        return HttpResponseForbidden()

    try:
        customer = django_keycloak_auth.users.get_user_by_id(customer_id).user
    except keycloak.exceptions.KeycloakClientError:
        raise Http404()

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    text = data.get("text")
    tag = data.get("tag")

    if not text:
        return HttpResponseBadRequest()

    platform = None
    conv = None
    try:
        conv = Conversation.objects.get(conversation_user_id=customer_id)
        platform = conv.last_usable_platform(tag, True, text)
    except Conversation.DoesNotExist:
        pass

    if platform is None:
        mobile_numbers = []
        other_numbers = []
        for n in customer.get("attributes", {}).get("phone", []):
            try:
                n = phonenumbers.parse(n, settings.PHONENUMBER_DEFAULT_REGION)
            except phonenumbers.phonenumberutil.NumberParseException:
                continue
            if phonenumbers.is_valid_number(n):
                if (
                        phonenumbers.phonenumberutil.number_type(n)
                        == phonenumbers.PhoneNumberType.MOBILE
                ):
                    mobile_numbers.append(n)
                else:
                    other_numbers.append(n)
        if len(mobile_numbers) or len(other_numbers):
            for n in mobile_numbers:
                formatted_num = phonenumbers.format_number(
                    n, phonenumbers.PhoneNumberFormat.E164
                )
                try:
                    platform = ConversationPlatform.objects.get(
                        platform=ConversationPlatform.WHATSAPP,
                        platform_id=formatted_num,
                    )
                    if not platform.can_message(tag, True, text):
                        platform = None
                    else:
                        break
                except ConversationPlatform.DoesNotExist:
                    pass
                try:
                    platform = ConversationPlatform.objects.get(
                        platform=ConversationPlatform.AS207960,
                        platform_id=f"msisdn-messaging;{formatted_num}",
                    )
                    break
                except ConversationPlatform.DoesNotExist:
                    pass
                try:
                    platform = ConversationPlatform.objects.get(
                        platform=ConversationPlatform.SMS,
                        platform_id=formatted_num,
                    )
                    break
                except ConversationPlatform.DoesNotExist:
                    pass

            if not platform:
                for n in other_numbers:
                    formatted_num = phonenumbers.format_number(
                        n, phonenumbers.PhoneNumberFormat.E164
                    )
                    try:
                        platform = ConversationPlatform.objects.get(
                            platform=ConversationPlatform.WHATSAPP,
                            platform_id=formatted_num,
                        )
                        if not platform.can_message(tag, True, text):
                            platform = None
                        else:
                            break
                    except ConversationPlatform.DoesNotExist:
                        pass
                    try:
                        platform = ConversationPlatform.objects.get(
                            platform=ConversationPlatform.AS207960,
                            platform_id=f"msisdn-messaging;{formatted_num}",
                        )
                        break
                    except ConversationPlatform.DoesNotExist:
                        pass
                    try:
                        platform = ConversationPlatform.objects.get(
                            platform=ConversationPlatform.SMS,
                            platform_id=formatted_num
                        )
                        break
                    except ConversationPlatform.DoesNotExist:
                        pass

            if not platform:
                if not conv:
                    conv = Conversation(conversation_user_id=customer_id)
                    conv.save()

                formatted_num = phonenumbers.format_number(
                    mobile_numbers[0], phonenumbers.PhoneNumberFormat.E164
                ) if len(mobile_numbers) else phonenumbers.format_number(
                other_numbers[0], phonenumbers.PhoneNumberFormat.E164
                )

                if operator_interface.models.ConversationPlatform.is_whatsapp_template(text):
                    platform_id = operator_interface.models.ConversationPlatform.WHATSAPP
                    platform_rcpt_id = formatted_num
                else:
                    platform_id = operator_interface.models.ConversationPlatform.AS207960
                    platform_rcpt_id = f"msisdn-messaging;{formatted_num}"

                platform = ConversationPlatform(
                    conversation=conv,
                    platform=platform_id,
                    platform_id=platform_rcpt_id,
                    additional_platform_data=json.dumps({
                        "try_others": [phonenumbers.format_number(
                            n, phonenumbers.PhoneNumberFormat.E164
                        ) for n in mobile_numbers] + [phonenumbers.format_number(
                            n, phonenumbers.PhoneNumberFormat.E164
                        ) for n in other_numbers]
                    })
                )
                platform.save()
            else:
                platform.conversation.update_user_id(customer_id)
        else:
            return HttpResponse(
                json.dumps({"status": "no_platform_available"}),
                content_type="application/json",
            )

    message = Message(
        platform=platform,
        text=text,
        direction=Message.TO_CUSTOMER,
        message_id=uuid.uuid4(),
    )
    message.save()
    operator_interface.tasks.process_message.delay(message.id)

    return HttpResponse(json.dumps({"status": "ok"}), content_type="application/json")
