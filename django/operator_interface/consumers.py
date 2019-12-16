import datetime
import json
import uuid
import payment
import dateutil.parser

import django_keycloak_auth.users
import keycloak.exceptions
import phonenumbers
from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.staticfiles import finders
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

import operator_interface.models
import operator_interface.tasks
import fulfillment.models

channel_layer = get_channel_layer()


@receiver(post_save, sender=operator_interface.models.Conversation)
def conversation_saved(sender, instance: operator_interface.models.Conversation, **kwargs):
    transaction.on_commit(lambda: async_to_sync(channel_layer.group_send)(
        "operator_interface", {"type": "conversation_update", "cid": instance.id}
    ))


@receiver(post_save, sender=operator_interface.models.Message)
def message_saved(sender, instance: operator_interface.models.Message, **kwargs):
    transaction.on_commit(lambda: async_to_sync(channel_layer.group_send)(
        "operator_interface", {"type": "message_update", "mid": instance.id}
    ))


@receiver(post_save, sender=fulfillment.models.RepairBooking)
def repair_booking_saved(sender, instance: operator_interface.models.Message, **kwargs):
    transaction.on_commit(lambda: async_to_sync(channel_layer.group_send)(
        "operator_interface", {"type": "repair_booking_update", "bid": instance.id}
    ))

# TODO: Integrate with new system
# @receiver(post_save, sender=payment.models.Payment)
# def payment_saved(sender, instance: payment.models.Payment, **kwargs):
#     async_to_sync(channel_layer.group_send)(
#         "operator_interface", {"type": "payment_update", "pid": str(instance.id)}
#     )
#
#
# @receiver(post_save, sender=payment.models.PaymentItem)
# def payment_item_saved(sender, instance: payment.models.PaymentItem, **kwargs):
#     async_to_sync(channel_layer.group_send)(
#         "operator_interface", {"type": "payment_item_update", "pid": instance.id}
#     )


class OperatorConsumer(JsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None

    def close(self, code=None):
        return super().close(code)

    def message(self, event):
        message = self.get_message(event["mid"])
        self.send_message(message)
        self.send_conversation(message.conversation)

    def message_update(self, event):
        message = self.get_message(event["mid"])
        self.send_message(message)

    def conversation_update(self, event):
        conversation = self.get_conversation(event["cid"])
        self.send_conversation(conversation)

    def repair_booking_update(self, event):
        booking = self.get_booking(event["bid"])
        self.send_booking(booking)

    # TODO: Integrate with new system
    # def payment_update(self, event):
    #     payment = self.get_payment(event["pid"])
    #     self.send_payment(payment)
    #
    # def payment_item_update(self, event):
    #     payment_item = self.get_payment_item(event["pid"])
    #     self.send_payment_item(payment_item)

    def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated or not self.user.is_staff:
            self.close()
            return

        self.accept()
        async_to_sync(self.channel_layer.group_add)("operator_interface", self.channel_name)

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("operator_interface", self.channel_name)

    def send_message(self, message: operator_interface.models.Message):
        self.send_json(
            {
                "type": "message",
                "id": message.id,
                "direction": message.direction,
                "timestamp": int(message.timestamp.timestamp()),
                "text": message.text,
                "image": message.image,
                "read": message.read,
                "delivered": message.delivered,
                "payment_request": str(message.payment_request) if message.payment_request else None,
                "payment_confirm": str(message.payment_confirm) if message.payment_confirm else None,
                "conversation_id": message.conversation.id,
                "request": message.request,
                "sent_by": message.user.first_name if message.user else None,
            }
        )

    def send_message_entities(self, message: operator_interface.models.Message):
        self.send_json(
            {
                "type": "message_entities",
                "id": message.id,
                "guessed_intent": message.guessed_intent,
                "entities": [{
                    "entity": e.entity,
                    "value": e.value,
                } for e in message.messageentity_set.all()]
            }
        )

    def send_error(self, error: str):
        self.send_json(
            {
                "type": "error",
                "msg": error
            }
        )

    def send_conversation(
            self, conversation: operator_interface.models.Conversation
    ):
        pic = settings.STATIC_URL + "operator_interface/img/default_profile_normal.png"
        if conversation.conversation_pic:
            pic = conversation.conversation_pic.url

        if conversation.conversation_user_id:
            bookings = fulfillment.models.RepairBooking.objects.filter(customer_id=conversation.conversation_user_id)
            try:
                user = django_keycloak_auth.users.get_user_by_id(str(conversation.conversation_user_id)).user
            except keycloak.exceptions.KeycloakClientError:
                user = {}
        else:
            user = {"name": conversation.conversation_name, "attributes": {"profile_picture": [pic]}}
            bookings = []

        first_name = user.get("firstName", "")
        last_name = user.get("lastName", "")
        attributes = user.get("attributes", {})
        timezone = next(iter(attributes.get("timezone", [])), None)
        phone_number = next(iter(attributes.get("phone", [])), None)
        locale = next(iter(attributes.get("locale", [])), None)
        gender = next(iter(attributes.get("gender", [])), None)
        pic = next(iter(attributes.get("profile_picture", [])), pic)

        messages = conversation.messages.all()
        payments = []
        for m in messages:
            if m.payment_request and str(m.payment_request) not in payments:
                payments.append(str(m.payment_request))
            if m.payment_confirm and str(m.payment_confirm) not in payments:
                payments.append(str(m.payment_confirm))

        self.send_json(
            {
                "type": "conversation",
                "id": conversation.id,
                "agent_responding": conversation.agent_responding,
                "current_user_responding": conversation.current_agent.id == self.user.id
                if conversation.current_agent else False,
                "platform": conversation.platform,
                "customer_name": user.get("name", f"{first_name} {last_name}"),
                "customer_first_name": first_name,
                "customer_last_name": last_name,
                "customer_username": user.get("username"),
                "customer_pic": pic,
                "timezone": timezone,
                "customer_email": user.get("email"),
                "customer_phone": phone_number,
                "customer_locale": locale,
                "customer_gender": gender,
                "messages": [m.id for m in messages],
                "repair_bookings": [b.id for b in bookings],
                "payments": payments,
            }
        )

    def send_payment(self, payment: payment.Payment):
        self.send_json(
            {
                "type": "payment",
                "id": str(payment.id),
                "timestamp": payment.timestamp.timestamp(),
                "state": payment.state,
                "payment_method": payment.payment_method,
                "total": str(payment.total),
                "items": [{
                    "item_type": payment_item.item_type,
                    "item_data": payment_item.item_data,
                    "title": payment_item.title,
                    "quantity": payment_item.quantity,
                    "price": str(payment_item.price),
                } for payment_item in payment.items],
            }
        )

    def send_booking(self, booking: fulfillment.models.RepairBooking):
        self.send_json(
            {
                "type": "booking",
                "id": str(booking.id),
                "time": str(booking.time.isoformat()),
                "repair": {
                    "id": booking.repair.id,
                    "time": booking.repair.repair_time,
                    "price": str(booking.repair.price),
                    "repair": {
                        "id": booking.repair.repair.id,
                        "name": booking.repair.repair.name,
                        "display_name": booking.repair.repair.display_name
                    },
                    "device": {
                        "id": booking.repair.device.id,
                        "name": booking.repair.device.name,
                        "display_name": booking.repair.device.display_name,
                        "brand": {
                            "id": booking.repair.device.brand.id,
                            "name": booking.repair.device.brand.name,
                            "display_name": booking.repair.device.brand.display_name,
                        }
                    }
                }
            }
        )

    def make_message(self, cid, text):
        conversation = self.get_conversation(cid)
        message = operator_interface.models.Message(
            conversation=conversation,
            text=text,
            direction=operator_interface.models.Message.TO_CUSTOMER,
            message_id=uuid.uuid4(),
            user=self.user,
        )
        self.save_object(message)
        operator_interface.tasks.process_message.delay(message.id)

    def get_messages(self, last_message):
        for conversation in operator_interface.models.Conversation.objects.all():
            for message in conversation.messages.filter(timestamp__gt=last_message):
                yield message

    def get_message(self, mid):
        return operator_interface.models.Message.objects.get(id=mid)

    def get_message_entity(self, eid):
        return operator_interface.models.MessageEntity.objects.get(id=eid)

    def get_conversation(self, cid):
        return operator_interface.models.Conversation.objects.get(id=cid)

    def get_booking(self, bid):
        return fulfillment.models.RepairBooking.objects.get(id=bid)

    def save_object(self, obj):
        obj.save()

    def make_payment_request(self, cid, items):
        conversation = self.get_conversation(cid)

        try:
            payment_id = payment.create_payment(
                settings.DEFAULT_PAYMENT_ENVIRONMENT,
                conversation.conversation_user_id,
                [payment.PaymentItem(
                    item_type=item["item_type"],
                    item_data=item["item_data"],
                    title=item["title"],
                    quantity=item["quantity"],
                    price=item["price"],
                ) for item in items]
            )
        except payment.PaymentException:
            self.send_error("There was an error creating the payment")
            return

        message = operator_interface.models.Message(
            conversation=conversation,
            direction=operator_interface.models.Message.TO_CUSTOMER,
            message_id=uuid.uuid4(),
            user=self.user,
            text="To complete payment follow this link 💸",
            payment_request=payment_id,
        )
        self.save_object(message)
        operator_interface.tasks.process_message.delay(message.id)

    def book_repair(self, cid, rid, time):
        conversation = self.get_conversation(cid)
        time = dateutil.parser.isoparse(time)
        print(time)

        m = fulfillment.models.RepairBooking(
            customer_id=conversation.conversation_user_id,
            repair_id=rid,
            time=time
        )
        self.save_object(m)

    def decode_attribute(self, attribute: str, value):
        if attribute == "phone-number":
            value = value.get("value")
            try:
                phone = phonenumbers.parse(value, settings.PHONENUMBER_DEFAULT_REGION)
            except phonenumbers.phonenumberutil.NumberParseException:
                self.send_error("Invalid phone number")
                return None

            if not phonenumbers.is_valid_number(phone):
                self.send_error("Invalid phone number")
                return None
            else:
                phone = phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)
                return {"phone": phone}
        elif attribute == "first-name":
            return {"first_name": value.get("value")}
        elif attribute == "last-name":
            return {"last_name": value.get("value")}
        elif attribute == "email":
            return value.get("value")

    def attribute_update(self, conversation: operator_interface.models.Conversation, attribute: str, value: str):
        value = json.loads(value)
        if conversation.conversation_user_id:
            attr = self.decode_attribute(attribute, value)
            if attr:
                django_keycloak_auth.users.update_user(conversation.conversation_user_id, force_update=True, **attr)
                self.send_conversation(conversation)
        elif attribute != "email":
            self.send_error("No user account is currently associated with this conversation, "
                                  "please set an email first")
        else:
            attr = self.decode_attribute(attribute, value)
            user = django_keycloak_auth.users.get_or_create_user(
                email=attr,
                first_name=conversation.conversation_name,
                required_actions=["UPDATE_PASSWORD", "UPDATE_PROFILE", "VERIFY_EMAIL"]
            )

            if user.get("new"):
                conversation.conversation_user_id = user.get("id")
                self.save_object(conversation)
            else:
                message = operator_interface.models.Message(
                    conversation=conversation,
                    text="An account is already associated with that email address. Please log in.",
                    direction=operator_interface.models.Message.TO_CUSTOMER,
                    message_id=uuid.uuid4(),
                    user=self.user,
                    request="sign_in",
                )
                self.save_object(message)
                operator_interface.tasks.process_message.delay(message.id)

    def receive_json(self, message, **kwargs):
        if message["type"] == "resyncReq":
            last_message = message["lastMessage"]
            last_message = datetime.datetime.fromtimestamp(last_message)
            conversations = set()
            for message in self.get_messages(last_message):
                if message.conversation not in conversations:
                    conversations.add(message.conversation)
            for conversation in conversations:
                self.send_conversation(conversation)
        elif message["type"] == "getMessage":
            msg_id = message["id"]
            try:
                msg = self.get_message(msg_id)
                self.send_message(msg)
            except operator_interface.models.Message.DoesNotExist:
                pass
        elif message["type"] == "getMessageEntities":
            mid = message["id"]
            try:
                msg = self.get_message(mid)
                self.send_message_entities(msg)
            except operator_interface.models.Message.DoesNotExist:
                pass
        elif message["type"] == "getConversation":
            conv_id = message["id"]
            try:
                conv = self.get_conversation(conv_id)
                self.send_conversation(conv)
            except operator_interface.models.Conversation.DoesNotExist:
                pass
        elif message["type"] == "getPayment":
            payment_id = message["id"]
            try:
                payment_o = payment.get_payment(payment_id)
                self.send_payment(payment_o)
            except payment.PaymentException:
                pass
        elif message["type"] == "getBooking":
            booking_id = message["id"]
            try:
                booking_o = self.get_booking(booking_id)
                self.send_booking(booking_o)
            except fulfillment.models.RepairBooking.DoesNotExist:
                pass
        # elif message["type"] == "getPaymentItem":
        #     payment_item_id = message["id"]
        #     try:
        #         payment_item = self.get_payment_item(payment_item_id)
        #         self.send_payment_item(payment_item)
        #     except payment.models.PaymentItem.DoesNotExist:
        #         pass
        elif message["type"] == "msg":
            text = message["text"]
            cid = message["cid"]
            self.make_message(cid, text)
        elif message["type"] == "endConv":
            cid = message["cid"]
            operator_interface.tasks.end_conversation.delay(cid)
        elif message["type"] == "finishConv":
            cid = message["cid"]
            operator_interface.tasks.hand_back.delay(cid)
        elif message["type"] == "takeOver":
            cid = message["cid"]
            operator_interface.tasks.take_over.delay(cid, self.user.id)
        elif message["type"] == "attribute_update":
            cid = message["cid"]
            try:
                conv = self.get_conversation(cid)
                self.attribute_update(conv, message["attribute"], message["value"])
            except operator_interface.models.Conversation.DoesNotExist:
                pass
        elif message["type"] == "requestPayment":
            cid = message["cid"]
            self.make_payment_request(cid, message["items"])
        elif message["type"] == "bookRepair":
            cid = message["cid"]
            self.book_repair(cid, message["rid"], message["time"])
