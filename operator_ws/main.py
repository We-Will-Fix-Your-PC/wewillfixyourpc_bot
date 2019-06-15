import logging
import uuid
import tornado.websocket
import tornado.web
import tornado.ioloop
import pika
import os
import sys
import django
import json
import jwt.exceptions
import threading
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.conf import settings
from tornado.platform.asyncio import AsyncIOMainLoop
import sentry_sdk
from sentry_sdk.integrations.tornado import TornadoIntegration

sentry_sdk.init("https://efc22f89d34a46d0adffb302181ed3f9@sentry.io/1471674", integrations=[TornadoIntegration()], send_default_pii=True)

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wewillfixyourpc_bot.settings')
django.setup()

from django.contrib.auth.models import User
import operator_interface.models
import operator_interface.tasks

message_handlers = set()

def make_sure_mysql_usable():
    from django.db import connection, connections
    if connection.connection and not connection.is_usable():
        del connections._connections.default

class OperatorWebSocket(tornado.websocket.WebSocketHandler):
    loop: AsyncIOMainLoop
    user: User

    async def get(self, *args, **kwargs):
        headers = self.request.headers
        jws = headers["Sec-WebSocket-Protocol"]

        key = jwt.jwk.OctetJWK(settings.SECRET_KEY.encode())
        jwt_i = jwt.JWT()
        try:
            data = jwt_i.decode(jws, key, True)
        except (jwt.exceptions.JWSDecodeError, jwt.exceptions.JWTDecodeError):
            raise tornado.web.HTTPError(403)
        uid = data.get("sub")
        if uid is None:
            raise tornado.web.HTTPError(403)
        make_sure_mysql_usable()
        try:
            self.user = User.objects.get(id=uid)
        except User.DoesNotExist:
            raise tornado.web.HTTPError(403)

        await super().get(*args, **kwargs)

    def select_subprotocol(self, protocols):
        if len(protocols) == 0:
            return None
        else:
            return protocols[0]

    def open(self):
        self.loop = tornado.ioloop.IOLoop.current()
        message_handlers.add(self.handle_message)
        print("WebSocket opened")

    def on_message(self, message):
        make_sure_mysql_usable()
        message = json.loads(message)
        if message["type"] == "resyncReq":
            last_message = message["lastMessage"]
            for conversation in operator_interface.models.Conversation.objects.all():
                for message in conversation.message_set.all():
                    if int(message.timestamp.strftime("%s")) > last_message:
                        self.send_message(message)
        elif message["type"] == "msg":
            text = message["text"]
            cid = message["cid"]
            conversation = operator_interface.models.Conversation.objects.get(id=cid)
            message = operator_interface.models.Message(conversation=conversation, text=text,
                                                        direction=operator_interface.models.Message.TO_CUSTOMER,
                                                        message_id=uuid.uuid4(), user=self.user)
            message.save()
            operator_interface.tasks.process_message.delay(message.id)
        elif message["type"] == "endConv":
            cid = message["cid"]
            operator_interface.tasks.process_event.delay(cid, "end")
        elif message["type"] == "finishConv":
            cid = message["cid"]
            operator_interface.tasks.hand_back.delay(cid)

    def send_message(self, message: operator_interface.models.Message):
        make_sure_mysql_usable()
        pic = static("operator_interface/img/default_profile_normal.png")
        if message.conversation.customer_pic:
            pic = message.conversation.customer_pic.url
        message = {
            "id": message.id,
            "direction": message.direction,
            "timestamp": int(message.timestamp.strftime("%s")),
            "text": message.text,
            "conversation": {
                "id": message.conversation.id,
                "agent_responding": message.conversation.agent_responding,
                "platform": message.conversation.platform,
                "customer_name": message.conversation.customer_name,
                "customer_username": message.conversation.customer_username,
                "customer_pic": pic,
            }
        }
        self.write_message(json.dumps(message))

    def handle_message(self, message):
        self.loop.add_callback(self.send_message, message)

    def on_close(self):
        message_handlers.remove(self.handle_message)
        print("WebSocket closed")

    def check_origin(self, origin):
        return True


def rmq_callback(ch, method, properties, body):
    data = json.loads(body)
    mid = data.get("mid")
    if mid is not None:
        make_sure_mysql_usable()
        try:
            message = operator_interface.models.Message.objects.get(id=mid)
        except operator_interface.models.Message.DoesNotExist:
            return
        for h in message_handlers:
            h(message)


rmq = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost'))
channel = rmq.channel()
channel.exchange_declare(exchange='bot_messages', exchange_type='fanout')

result = channel.queue_declare('', exclusive=True)
queue_name = result.method.queue

channel.queue_bind(exchange='bot_messages', queue=queue_name)
channel.basic_consume(queue=queue_name, on_message_callback=rmq_callback, auto_ack=True)

application = tornado.web.Application([
    (r"/", OperatorWebSocket),
])
application.listen(8001)

logging.basicConfig(level=logging.INFO)

rmq_t = threading.Thread(target=channel.start_consuming, daemon=True)
rmq_t.start()

tornado.ioloop.IOLoop.current().start()
