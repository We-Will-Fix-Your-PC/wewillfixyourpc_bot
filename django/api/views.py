from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseBadRequest, Http404
import json
import phonenumbers
import django_keycloak_auth.users
import keycloak.exceptions
import uuid
import operator_interface.tasks
from django.conf import settings
from operator_interface.models import Message, Conversation, ConversationPlatform


def send_message(request, customer_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(permitted_methods=["POST"])

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
        platform = conv.last_usable_platform(tag)
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
            conv = Conversation(customer_user_id=customer_id)
            conv.save()

            platform = ConversationPlatform(
                conversation=conv,
                platform=ConversationPlatform.SMS,
                platform_id=mobile_numbers[0] if len(mobile_numbers) else other_numbers[0]
            )
            platform.save()

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
