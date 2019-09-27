import uuid

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

import operator_interface.models
import operator_interface.tasks
import operator_interface.consumers
import django_keycloak_auth.users
from . import models


@shared_task
def process_payment(pid):
    payment_o = models.Payment.objects.get(id=pid)
    user = django_keycloak_auth.users.get_user_by_id(payment_o.customer_id)

    email_items = "\n\n".join(
        [
            f"""- {item.quantity}x {item.title} @{item.price} GBP
- Item type: {item.item_type}
- Item data: {item.item_data}
"""
            for item in payment_o.paymentitem_set.all()
        ]
    )

    email_content = f"""New order
---
Order id: {payment_o.id}
Order date: {payment_o.timestamp.strftime("%c")}
Environment: {next(e[1] for e in models.Payment.ENVIRONMENTS if e[0] == payment_o.environment)}
Payment method: {payment_o.payment_method}
---
Customer name: {user.user.get("firstName")} {user.user.get("lastName")}
Customer email: {user.user.get("email")}
Customer phone: {next(user.user.get("attributes", {}).get("phone", []), "")}
---
Items:

{email_items}
"""

    send_mail(
        "New order notification",
        email_content,
        settings.ORDER_NOTIFICATION_FROM,
        [settings.ORDER_NOTIFICATION_EMAIL],
        fail_silently=False,
    )

    payment_o.state = payment_o.STATE_COMPLETE
    payment_o.save()
    operator_interface.consumers.payment_saved(None, payment_o)

    try:
        message = operator_interface.models.Message.objects.get(
            payment_request=payment_o.id
        )
        conversation = message.conversation

        message = operator_interface.models.Message(
            conversation=conversation,
            direction=operator_interface.models.Message.TO_CUSTOMER,
            message_id=uuid.uuid4(),
            payment_confirm=payment_o,
        )
        message.save()
        operator_interface.tasks.process_message.delay(message.id)
    except operator_interface.models.Message.DoesNotExist:
        pass
