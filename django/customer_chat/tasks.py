from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from pywebpush import webpush, WebPushException
from django.conf import settings
import sentry_sdk
import json
import operator_interface.models

channel_layer = get_channel_layer()


@shared_task
def send_message(mid: int) -> None:
    message = operator_interface.models.Message.objects.get(id=mid)
    async_to_sync(channel_layer.group_send)(
        f"customer_chat_{message.platform.id}", {"type": "message", "mid": mid}
    )

    try:
        data = (
            json.loads(message.platform.additional_platform_data)
            if message.platform.additional_platform_data
            else {}
        )
    except json.JSONDecodeError:
        data = {}

    push = data.get("push", [])

    for i, p in enumerate(push):
        try:
            webpush(
                subscription_info=p,
                data=json.dumps(
                    {
                        "type": "message",
                        "contents": message.text,
                        "timestamp": message.timestamp.timestamp(),
                    }
                ),
                vapid_private_key=settings.PUSH_PRIV_KEY,
                vapid_claims={"sub": "mailto:q@misell.cymru"},
            )
        except WebPushException as e:
            print(e, e.response)
            sentry_sdk.capture_exception(e)
            if e.response.status_code in [404, 410]:
                del push[i]

    data["push"] = push
    message.platform.additional_platform_data = json.dumps(data)
    message.platform.save()
