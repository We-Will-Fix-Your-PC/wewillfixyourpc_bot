import datetime
import uuid

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.db.models.signals import post_save
from django.dispatch import receiver

import operator_interface.models
import operator_interface.tasks
import payment.models

channel_layer = get_channel_layer()


@receiver(post_save, sender=operator_interface.models.Conversation)
def conversation_saved(sender, instance: operator_interface.models.Conversation, **kwargs):
    async_to_sync(channel_layer.group_send)("operator_interface", {
        "type": "conversation_update",
        "cid": instance.id
    })


@receiver(post_save, sender=payment.models.Payment)
def payment_saved(sender, instance: payment.models.Payment, **kwargs):
    async_to_sync(channel_layer.group_send)("operator_interface", {
        "type": "payment_update",
        "pid": str(instance.id)
    })


@receiver(post_save, sender=payment.models.PaymentItem)
def payment_item_saved(sender, instance: payment.models.PaymentItem, **kwargs):
    async_to_sync(channel_layer.group_send)("operator_interface", {
        "type": "payment_item_update",
        "pid": instance.id
    })


class OperatorConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None

    async def message(self, event):
        message = await self.get_message(event["mid"])
        await self.send_message(message)

    async def conversation_update(self, event):
        conversation = await self.get_conversation(event["cid"])
        await self.send_conversation(conversation)

    async def payment_update(self, event):
        payment = await self.get_payment(event["pid"])
        await self.send_payment(payment)

    async def payment_item_update(self, event):
        payment_item = await self.get_payment_item(event["pid"])
        await self.send_payment_item(payment_item)

    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        await self.accept()
        await self.channel_layer.group_add("operator_interface", self.channel_name)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("operator_interface", self.channel_name)

    async def send_message(self, message: operator_interface.models.Message):
        await self.send_json({
            "type": "message",
            "id": message.id,
            "direction": message.direction,
            "timestamp": int(message.timestamp.timestamp()),
            "text": message.text,
            "image": message.image,
            "read": message.read,
            "conversation_id": message.conversation.id,
            "payment_request": message.payment_request.id if message.payment_request else None,
            "payment_confirm": message.payment_confirm.id if message.payment_confirm else None,
        })
        conversation = await self.get_conversation(message.conversation_id)
        await self.send_conversation(conversation)

    async def send_conversation(self, conversation: operator_interface.models.Conversation):
        pic = static("operator_interface/img/default_profile_normal.png")
        if conversation.customer_pic:
            pic = conversation.customer_pic.url
        await self.send_json({
            "type": "conversation",
            "id": conversation.id,
            "agent_responding": conversation.agent_responding,
            "platform": conversation.platform,
            "customer_name": conversation.customer_name,
            "customer_username": conversation.customer_username,
            "customer_pic": pic,
            "timezone": conversation.timezone,
            "customer_email": conversation.customer_email,
            "customer_phone": conversation.customer_phone.as_national if conversation.customer_phone else None,
            "customer_locale": conversation.customer_locale,
            "customer_gender": conversation.customer_gender,
        })

    async def send_payment(self, payment: payment.models.Payment):
        await self.send_json({
            "type": "payment",
            "id": payment.id,
            "timestamp": payment.timestamp.timestamp(),
            "state": payment.state,
            "payment_method": payment.payment_method,
            "total": str(payment.total),
            "items": [i.id for i in payment.paymentitem_set.all()]
        })

    async def send_payment_item(self, payment_item: payment.models.PaymentItem):
        await self.send_json({
            "type": "payment_item",
            "id": payment_item.id,
            "payment_id": payment_item.payment.id,
            "item_type": payment_item.item_type,
            "item_data": payment_item.item_data,
            "title": payment_item.title,
            "quantity": payment_item.quantity,
            "price": str(payment_item.price)
        })

    async def make_message(self, cid, text):
        conversation = await self.get_conversation(cid)
        message = operator_interface.models.Message(
            conversation=conversation, text=text, direction=operator_interface.models.Message.TO_CUSTOMER,
            message_id=uuid.uuid4(), user=self.user)
        await self.save_object(message)
        operator_interface.tasks.process_message.delay(message.id)

    @database_sync_to_async
    def get_messages(self, last_message):
        for conversation in operator_interface.models.Conversation.objects.all():
            for message in conversation.message_set.filter(timestamp__gt=last_message):
                yield message

    @database_sync_to_async
    def get_message(self, mid):
        return operator_interface.models.Message.objects.get(id=mid)

    @database_sync_to_async
    def get_conversation(self, cid):
        return operator_interface.models.Conversation.objects.get(id=cid)

    @database_sync_to_async
    def get_payment(self, pid):
        return payment.models.Payment.objects.get(id=pid)

    @database_sync_to_async
    def save_object(self, object):
        object.save()

    @database_sync_to_async
    def lookup_customer(self, email, phone, name):
        try:
            return payment.models.Customer.objects.get(email=email, phone=phone, name=name)
        except payment.models.Customer.DoesNotExist:
            return payment.models.Customer(email=email, phone=phone, name=name)

    @database_sync_to_async
    def get_payment_item(self, pid):
        return payment.models.PaymentItem.objects.get(id=pid)

    async def make_payment_request(self, cid, items):
        conversation = await self.get_conversation(cid)
        customer = await self.lookup_customer(email=conversation.customer_email, phone=conversation.customer_phone,
                                              name=conversation.customer_name) \
            if (conversation.customer_phone and conversation.customer_email) else None
        payment_o = payment.models.Payment(state=payment.models.Payment.STATE_OPEN, customer=customer)
        await self.save_object(payment_o)

        for item in items:
            payment_item = payment.models.PaymentItem(
                payment=payment_o, item_type=item["item_type"], item_data=item["item_data"], title=item["title"],
                quantity=item["quantity"], price=item["price"])
            await self.save_object(payment_item)

        message = operator_interface.models.Message(
            conversation=conversation, direction=operator_interface.models.Message.TO_CUSTOMER, message_id=uuid.uuid4(),
            user=self.user, text="To complete payment follow this link 💸", payment_request=payment_o)
        await self.save_object(message)
        operator_interface.tasks.process_message.delay(message.id)

    async def receive_json(self, message, **kwargs):
        if message["type"] == "resyncReq":
            last_message = message["lastMessage"]
            last_message = datetime.datetime.fromtimestamp(last_message)
            for message in await self.get_messages(last_message):
                await self.send_message(message)
        elif message["type"] == "getConversation":
            conv_id = message["id"]
            try:
                conv = await self.get_conversation(conv_id)
                await self.send_conversation(conv)
            except operator_interface.models.Conversation.DoesNotExist:
                pass
        elif message["type"] == "getPayment":
            payment_id = message["id"]
            try:
                payment_o = await self.get_payment(payment_id)
                await self.send_payment(payment_o)
            except payment.models.Payment.DoesNotExist:
                pass
        elif message["type"] == "getPaymentItem":
            payment_item_id = message["id"]
            try:
                payment_item = await self.get_payment_item(payment_item_id)
                await self.send_payment_item(payment_item)
            except payment.models.PaymentItem.DoesNotExist:
                pass
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
        elif message["type"] == "requestPayment":
            cid = message["cid"]
            await self.make_payment_request(cid, message["items"])
