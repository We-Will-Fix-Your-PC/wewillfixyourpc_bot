from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseBadRequest, Http404, HttpResponseForbidden
import json
import phonenumbers
import django_keycloak_auth.users
import django_keycloak_auth.clients
import keycloak.exceptions
import uuid
import operator_interface.tasks
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from operator_interface.models import Message, Conversation, ConversationPlatform


@csrf_exempt
def send_message(request, customer_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(permitted_methods=["POST"])

    auth = request.META.get("HTTP_AUTHORIZATION")
    if not auth or not auth.startswith("Bearer "):
        return HttpResponseForbidden()

    try:
        claims = django_keycloak_auth.clients.verify_token(auth[len('Bearer '):].strip())
    except keycloak.exceptions.KeycloakClientError:
        return HttpResponseForbidden()

    if "send-messages" not in claims.get("resource_access", {}).get("bot-server", {}).get("roles", []):
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
    try:
        conv = Conversation.objects.get(conversation_user_id=customer_id)
        platform = conv.last_usable_platform(tag, True)
    except Conversation.DoesNotExist:
        mobile_numbers = []
        other_numbers = []
        for n in customer.get("attributes", {}).get("phone", []):
            try:
                n = phonenumbers.parse(n, settings.PHONENUMBER_DEFAULT_REGION)
            except phonenumbers.phonenumberutil.NumberParseException:
                continue
            if phonenumbers.is_valid_number(n):
                if phonenumbers.phonenumberutil.number_type(n) == phonenumbers.PhoneNumberType.MOBILE:
                    mobile_numbers.append(n)
                else:
                    other_numbers.append(n)
        if len(mobile_numbers) or len(other_numbers):
            for n in mobile_numbers:
                try:
                    platform = ConversationPlatform.objects.get(
                        platform=ConversationPlatform.SMS,
                        platform_id=phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)
                    )
                    break
                except ConversationPlatform.DoesNotExist:
                    pass

            if not platform:
                for n in other_numbers:
                    try:
                        platform = ConversationPlatform.objects.get(
                            platform=ConversationPlatform.SMS,
                            platform_id=phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)
                        )
                        break
                    except ConversationPlatform.DoesNotExist:
                        pass

            if not platform:
                conv = Conversation(conversation_user_id=customer_id)
                conv.save()

                platform = ConversationPlatform(
                    conversation=conv,
                    platform=ConversationPlatform.SMS,
                    platform_id=phonenumbers.format_number(mobile_numbers[0], phonenumbers.PhoneNumberFormat.E164)
                    if len(mobile_numbers) else
                    phonenumbers.format_number(other_numbers[0], phonenumbers.PhoneNumberFormat.E164)
                )
                platform.save()
            else:
                platform.conversation.update_user_id(customer_id)

    if platform is None:
        return HttpResponse(
            json.dumps({
                "status": "no_platform_available"
            }),
            content_type='application/json'
        )

    message = Message(
        platform=platform,
        text=text,
        direction=Message.TO_CUSTOMER,
        message_id=uuid.uuid4(),
    )
    message.save()
    operator_interface.tasks.process_message.delay(message.id)

    return HttpResponse(
        json.dumps({
            "status": "ok"
        }),
        content_type='application/json'
    )
