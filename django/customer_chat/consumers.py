from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from channels.layers import get_channel_layer
from django.conf import settings
from django.shortcuts import reverse
import typing
import json
import re
import operator_interface.models
import operator_interface.tasks

channel_layer = get_channel_layer()


class ChatConsumer(JsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.platform = None  # type: typing.Union[operator_interface.models.ConversationPlatform, None]

    def close(self, code=None):
        return super().close(code)

    def message(self, event):
        message: operator_interface.models.Message = operator_interface.models.Message.objects.get(id=event.get("mid"))
        self.send_message(message)
        self.send_conversation(message.platform)
        message.state = operator_interface.models.Message.DELIVERED
        message.save()

    def disconnect(self, close_code):
        if self.platform:
            async_to_sync(self.channel_layer.group_discard)(
                f"customer_chat_{self.platform.id}", self.channel_name
            )

    def send_message(self, message: operator_interface.models.Message):
        urls = re.findall(
            "(http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)",
            message.text,
        )

        buttons = []
        if len(urls):
            buttons.append({
                "text": "Open link",
                "type": "url",
                "url": urls[0]
            })

        self.send_json(
            {
                "type": "message",
                "id": message.id,
                "mid": str(message.message_id),
                "direction": message.direction,
                "timestamp": int(message.timestamp.timestamp()),
                "text": message.text,
                "image": message.image,
                "state": message.state,
                "request": message.request,
                "sent_by": message.user.first_name if message.user else None,
                "profile_picture_url": settings.EXTERNAL_URL_BASE + reverse(
                    "operator:profile_pic", args=[message.user.id]
                ) if message.user else None,
                "selection": message.selection,
                "card": message.card,
                "buttons": buttons
            }
        )

    def send_error(self, error: str):
        self.send_json({"type": "error", "msg": error})

    def send_conversation(self, platform: operator_interface.models.ConversationPlatform):
        conversation = platform.conversation
        self.send_json(
            {
                "type": "conversation",
                "current_agent": conversation.current_agent.first_name if conversation.current_agent else None,
                "messages": [m.id for m in platform.messages.all()]
            }
        )

    def recv_message(self, content, mid):
        message = operator_interface.models.Message(
            direction=operator_interface.models.Message.FROM_CUSTOMER,
            platform=self.platform,
            text=content,
            state=operator_interface.models.Message.DELIVERED,
            message_id=mid
        )
        message.save()
        operator_interface.tasks.process_message.delay(message.id)
        self.send_message(message)
        self.send_conversation(message.platform)

    def register_push(self, msg):
        if not (msg.get("endpoint") and msg.get("keys")):
            return

        try:
            data = json.loads(self.platform.additional_platform_data) if self.platform.additional_platform_data else {}
        except json.JSONDecodeError:
            data = {}
        push = data.get("push", [])

        new_push = True
        for i, p in enumerate(push):
            if p.get("endpoint") == msg.get("endpoint"):
                push[i] = msg
                new_push = False
        if new_push:
            push.append(msg)

        data["push"] = push
        self.platform.additional_platform_data = json.dumps(data)
        self.platform.save()

    def receive_json(self, message, **kwargs):
        msg_type = message.get("type")
        if self.platform is None and msg_type != "resyncReq":
            return

        if msg_type == "resyncReq":
            token = message["token"]

            try:
                platform = operator_interface.models.ConversationPlatform.objects.get(
                    platform=operator_interface.models.ConversationPlatform.CHAT,
                    platform_id=token
                )
            except operator_interface.models.ConversationPlatform.DoesNotExist:
                self.close()
                return
            self.platform = platform

            async_to_sync(self.channel_layer.group_add)(
                f"customer_chat_{platform.id}", self.channel_name
            )
            self.send_conversation(platform)
        elif msg_type == "sendMessage":
            content = message["content"]
            mid = message["id"]
            self.recv_message(content, mid)
        elif msg_type == "readMessage":
            msg_id = message["id"]
            try:
                msg = operator_interface.models.Message.objects.get(id=msg_id)
                if msg.direction == operator_interface.models.Message.TO_CUSTOMER and msg.platform_id == self.platform.id:
                    msg.state = operator_interface.models.Message.READ
                    msg.save()
            except operator_interface.models.Message.DoesNotExist:
                pass
        elif msg_type == "getMessage":
            msg_id = message["id"]
            try:
                msg = operator_interface.models.Message.objects.get(id=msg_id)
                if msg.platform_id == self.platform.id:
                    self.send_message(msg)
            except operator_interface.models.Message.DoesNotExist:
                pass
        elif msg_type == "pushSubscription":
            self.register_push(message["data"])
