import datetime
import uuid

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.staticfiles.templatetags.staticfiles import static

import operator_interface.models
import operator_interface.tasks


class OperatorConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None

    async def message(self, event):
        message = await self.get_message(event["mid"])
        await self.send_message(message)

    async def connect(self):
        self.user = self.scope["user"]
        print(self.user)

        if not self.user.is_authenticated:
            await self.close()
            return

        await self.accept()
        await self.channel_layer.group_add("operator_interface", self.channel_name)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("operator_interface", self.channel_name)

    async def send_message(self, message: operator_interface.models.Message):
        pic = static("operator_interface/img/default_profile_normal.png")
        if message.conversation.customer_pic:
            pic = message.conversation.customer_pic.url
        await self.send_json({
            "id": message.id,
            "direction": message.direction,
            "timestamp": int(message.timestamp.timestamp()),
            "text": message.text,
            "image": message.image,
            "read": message.read,
            "conversation": {
                "id": message.conversation.id,
                "agent_responding": message.conversation.agent_responding,
                "platform": message.conversation.platform,
                "customer_name": message.conversation.customer_name,
                "customer_username": message.conversation.customer_username,
                "customer_pic": pic,
            }
        })

    @database_sync_to_async
    def make_message(self, cid, text):
        conversation = operator_interface.models.Conversation.objects.get(id=cid)
        message = operator_interface.models.Message(conversation=conversation, text=text,
                                                    direction=operator_interface.models.Message.TO_CUSTOMER,
                                                    message_id=uuid.uuid4(), user=self.user)
        message.save()
        operator_interface.tasks.process_message.delay(message.id)

    @database_sync_to_async
    def get_messages(self, last_message):
        for conversation in operator_interface.models.Conversation.objects.all():
            for message in conversation.message_set.filter(timestamp__gt=last_message):
                yield message

    @database_sync_to_async
    def get_message(self, mid):
        return operator_interface.models.Message.objects.get(id=mid)

    async def receive_json(self, message, **kwargs):
        if message["type"] == "resyncReq":
            last_message = message["lastMessage"]
            last_message = datetime.datetime.fromtimestamp(last_message)
            for message in await self.get_messages(last_message):
                await self.send_message(message)
        elif message["type"] == "msg":
            text = message["text"]
            cid = message["cid"]
            await self.make_message(cid, text)
        elif message["type"] == "endConv":
            cid = message["cid"]
            operator_interface.tasks.process_event.delay(cid, "end")
        elif message["type"] == "finishConv":
            cid = message["cid"]
            operator_interface.tasks.hand_back.delay(cid)
