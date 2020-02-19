from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
import operator_interface.models

channel_layer = get_channel_layer()


@shared_task
def send_message(mid: int) -> None:
    message = operator_interface.models.Message.objects.get(id=mid)
    async_to_sync(channel_layer.group_send)(
        f"customer_chat_{message.platform.id}", {"type": "message", "mid": mid}
    )
